"""尽力把客户 legacy 自由文本 region 回填成结构化 省/市/区县 + region_code。

设计为可安全反复运行：
  - 默认 dry-run，仅打印将要写入的内容，不落库。
  - 加 --commit 才真正写入。
  - 仅处理 province 为空且 region 有值的客户，已结构化的不动。
  - 采用「省优先」匹配，避免同名区县跨省歧义；匹配不到就跳过（保留原 region）。

用法（在 backend 目录下）：
  python -m scripts.backfill_customer_region                 # 预览（全部租户）
  python -m scripts.backfill_customer_region --commit        # 落库
  python -m scripts.backfill_customer_region --tenant <id>   # 限定租户
"""
import argparse
import asyncio
import json
import os
import sys

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory  # noqa: E402
from app.domains.customer.models import Customer  # noqa: E402

# 行政区划数据（含 code + name），与前端同一份数据源。
# 后端容器里可能没有 frontend/ 目录，因此按「显式参数 → 环境变量 → 若干候选路径」依次解析，
# 找不到时给出可操作的报错，避免在生产容器中直接 FileNotFoundError。
_REGION_CANDIDATES = [
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "..", "frontend", "src", "data", "china-regions.json")),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "china-regions.json"),
    os.path.join(os.getcwd(), "china-regions.json"),
]


def _resolve_region_json(explicit: str | None = None) -> str:
    candidates = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("REGION_DATA_PATH"):
        candidates.append(os.environ["REGION_DATA_PATH"])
    candidates += _REGION_CANDIDATES
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    raise FileNotFoundError(
        "找不到行政区划数据 china-regions.json。请用 --region-data <路径> 指定，"
        "或设置环境变量 REGION_DATA_PATH（可从 frontend/src/data/china-regions.json 拷贝）。\n已尝试：\n  "
        + "\n  ".join(candidates)
    )

_PROVINCE_SUFFIXES = ["维吾尔自治区", "壮族自治区", "回族自治区", "特别行政区", "自治区", "省", "市"]
_CITY_SUFFIXES = ["自治州", "地区", "盟", "市"]
# 占位「市级」节点：直辖市/省直辖县下的这些名字不会出现在自由文本里，展示时应跳过
_GENERIC_CITY = {"市辖区", "县", "省直辖县级行政区划", "自治区直辖县级行政区划"}


def _core(name: str, suffixes: list[str]) -> str:
    for s in suffixes:
        if name.endswith(s) and len(name) > len(s):
            return name[: -len(s)]
    return name


def _load_region_index(region_json: str):
    with open(region_json, encoding="utf-8") as f:
        data = json.load(f)
    provinces = []  # {name, core, code, cities:[...]}
    city_fullname_owner: dict[str, int] = {}  # 全名 -> 出现次数，用于判断唯一性
    for p in data:
        pnode = {"name": p["name"], "core": _core(p["name"], _PROVINCE_SUFFIXES), "code": p["code"], "cities": []}
        for c in p.get("children", []):
            cnode = {"name": c["name"], "core": _core(c["name"], _CITY_SUFFIXES), "code": c["code"],
                     "districts": [{"name": d["name"], "code": d["code"]} for d in c.get("children", [])]}
            pnode["cities"].append(cnode)
            city_fullname_owner[c["name"]] = city_fullname_owner.get(c["name"], 0) + 1
        provinces.append(pnode)
    # 越长的核心名越先匹配，避免「江」误命中
    provinces.sort(key=lambda x: len(x["core"]), reverse=True)
    return provinces, city_fullname_owner


def _find_province(region: str, provinces):
    """稳妥地匹配省份，避免「北京路/上海路/河南路」等街道名误撞省核心名。"""
    text = region.strip()
    # 全名匹配最稳（如「浙江省」「北京市」）
    prov = next((p for p in provinces if p["name"] in region), None)
    if prov:
        return prov
    # 仅核心名（如「江苏」「北京」）易与街道名误撞，需满足其一才接受：
    #   a) 文本本身就是该省名（如「江苏」「浙江」）；
    #   b) 同省的市/区县名也出现在文本里作为佐证。
    for p in provinces:
        if len(p["core"]) >= 2 and p["core"] in region:
            if text == p["core"] or text == p["name"]:
                return p
            corroborated = any(
                c["name"] not in _GENERIC_CITY
                and (c["name"] in region or (len(c["core"]) >= 2 and c["core"] in region))
                for c in p["cities"]
            ) or any(d["name"] in region for c in p["cities"] for d in c["districts"])
            if corroborated:
                return p
    return None


def _match(region: str, provinces, city_unique):
    """返回 (province, city, district, region_code) 或 None。省优先，避免跨省同名区县歧义。"""
    if not region:
        return None
    # 1) 找省份（防街道名误撞，见 _find_province）
    prov = _find_province(region, provinces)
    if prov:
        cities = sorted(prov["cities"], key=lambda x: len(x["core"]), reverse=True)
        # 优先匹配「真实」地级市（跳过 市辖区 等占位）
        city = next((c for c in cities
                     if c["name"] not in _GENERIC_CITY
                     and (c["name"] in region or (len(c["core"]) >= 2 and c["core"] in region))), None)
        if city:
            dist = next((d for d in sorted(city["districts"], key=lambda x: len(x["name"]), reverse=True)
                         if d["name"] in region), None)
            if dist:
                return prov["name"], city["name"], dist["name"], dist["code"]
            return prov["name"], city["name"], None, city["code"]
        # 直辖市/省直辖：无真实地级市，跨全省找区县（展示跳过占位市级）
        for c in cities:
            for d in sorted(c["districts"], key=lambda x: len(x["name"]), reverse=True):
                if d["name"] in region:
                    display_city = None if c["name"] in _GENERIC_CITY else c["name"]
                    return prov["name"], display_city, d["name"], d["code"]
        return prov["name"], None, None, prov["code"]
    # 2) 文本无省份：尝试用「全局唯一的城市全名」反推省份，并尽量下钻到区县
    for p in provinces:
        for c in p["cities"]:
            if c["name"] not in _GENERIC_CITY and c["name"] in region and city_unique.get(c["name"], 0) == 1:
                dist = next((d for d in sorted(c["districts"], key=lambda x: len(x["name"]), reverse=True)
                             if d["name"] in region), None)
                if dist:
                    return p["name"], c["name"], dist["name"], dist["code"]
                return p["name"], c["name"], None, c["code"]
    return None


async def run(commit: bool, tenant_id: str | None, region_data: str | None = None):
    region_json = _resolve_region_json(region_data)
    print(f"使用行政区划数据：{region_json}")
    provinces, city_unique = _load_region_index(region_json)
    matched = skipped = 0
    async with async_session_factory() as db:
        q = select(Customer).where(
            Customer.is_deleted == False,  # noqa: E712
            Customer.province.is_(None),
            Customer.region.isnot(None),
            Customer.region != "",
        )
        if tenant_id:
            q = q.where(Customer.tenant_id == tenant_id)
        customers = (await db.execute(q)).scalars().all()
        for c in customers:
            res = _match(c.region, provinces, city_unique)
            if not res:
                skipped += 1
                continue
            prov, city, dist, code = res
            matched += 1
            label = " · ".join([x for x in (prov, city, dist) if x])
            print(f"[{'WRITE' if commit else 'DRY'}] {c.name!r}  region={c.region!r}  ->  {label}  code={code}")
            if commit:
                c.province, c.city, c.district, c.region_code = prov, city, dist, code
        if commit:
            await db.commit()
    print(f"\n汇总：命中 {matched}，跳过(无法匹配) {skipped}，共 {matched + skipped}。"
          f"{'（已写入）' if commit else '（预览，未写入；加 --commit 落库）'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="真正写入数据库（默认仅预览）")
    ap.add_argument("--tenant", default=None, help="仅处理指定租户 ID")
    ap.add_argument("--region-data", default=None,
                    help="china-regions.json 路径（默认自动查找/读 REGION_DATA_PATH 环境变量）")
    args = ap.parse_args()
    asyncio.run(run(args.commit, args.tenant, args.region_data))
