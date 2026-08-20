# -*- coding: utf-8 -*-
"""简道云流程条件里的部门 MongoId → CRM departments.id（按名称对齐）。

系统从 JDY 导入的图纸/方案等流程，连线条件仍写着简道云部门 _id；
表单「部门」字段存的是 CRM UUID，不 remap 则分支永不命中，设计器也只能显示「未知部门」。
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.organization.models import Department

logger = logging.getLogger(__name__)

MONGO_ID_RE = re.compile(r"^[0-9a-f]{24}$")

# 条件里出现过、且现网/dump 能对上名称的 JDY 部门（离线兜底；UUID 仍按租户名反查）
JDY_DEPT_NAMES: dict[str, str] = {
    "56ca5b8af97e80434fc0611b": "总经办",
    "56ca5b8af97e80434fc06122": "中央研究院",
    "56ca5b8af97e80434fc06124": "精细筛分装备销售部",
    "56ca5b8af97e80434fc06126": "冶金矿山装备销售事业部",
    "56ca5b8af97e80434fc06128": "国际营销中心",
    "56ca5b8af97e80434fc06129": "计划采购部",
    "56ca5b8af97e80434fc06133": "国际贸易一部",
    "56ca5b8af97e80434fc06141": "新乡研发中心",
    "56ca5b8af97e80434fc06142": "精品砂石事业部",
    "56ca5b8af97e80434fc06143": "清欠办",
    "56ca5b8af97e80434fc0614a": "证券部",
    "56ca5b8af97e80434fc0614b": "郑州研发中心",
    "57ce1791b6eb93772163787d": "人工智能+营销支持部",
    "57f618b4cf0caf81d12d830b": "国际业务支持部",
    "59dc5c5f0b18743912395106": "新疆威猛工业智能装备有限公司",
    "5a9fa0ada21496c4066c2c4b": "市场支持中心",
    "5a9fa0ada21496c4066c2c4c": "（暂存）冶金装备销售事业部",
    "5aa37e54a21496c406944f49": "国际贸易二部",
    "5c500ac3a028fdc81b7a2ab9": "北京小威",
    "62c724bf70e58912be606334": "分布筛推广中心",
    "63bc58ffbf979e28e3c06a47": "（暂存）F事业部",
    "63efcac9bf979e28e32b666a": "矿山泥水事业部",
    "63efcac9bf979e28e32b6674": "城市泥水事业部",
    "65d397f47d6f29a2ffe03fe4": "营销部",
    "65d397f47d6f29a2ffe03fea": "迅焊公司",
}

# 仅对这些字段做部门 id 替换（人员字段另见 PERSON_COND_FIELDS）
# field：客户服务申请等「所属部门」生成 slug（非 department）
DEPT_COND_FIELDS = frozenset({
    "department", "offices", "offices_multi", "department_multi", "field",
})

# 流程条件里的人员字段（简道云 member MongoId → CRM users.id）
PERSON_COND_FIELDS = frozenset({
    "transfer_packaging_users", "design_assignees", "transfer_sw_lwt",
    "order_person", "applicant", "designer", "submitter",
    "sales_person", "salesperson", "owner_id",
})

# 方案/图纸流条件中出现过的 JDY 成员 id → 姓名（离线兜底）
JDY_PERSON_NAMES: dict[str, str] = {
    "56ca5bacf83c32e4699dd0bb": "樊磊",
    "56ca5bacf83c32e4699dd0bd": "丰芊",
    "56ca5bacf83c32e4699dd0c5": "刘松潮",
    "56ca5bacf83c32e4699dd0c7": "李兴玉",
    "56ca5bacf83c32e4699dd0c9": "吕芹",
    "56ca5bacf83c32e4699dd0e1": "周彦立",
    "57f618b6812fa23e8ffe45cc": "崔艳丽",
    "5912cb73c872010b38db842e": "荆焕民",
    "66b986a3daac8bf32617e233": "李海春",
    "6603dadbd23d27d4d03d8824": "郭椿",
}


def is_jdy_mongo_id(value: Any) -> bool:
    return isinstance(value, str) and bool(MONGO_ID_RE.match(value))


def _fetch_live_jdy_dept_names() -> dict[str, str]:
    """可选：从 jdy-wrapper 拉现网部门名（失败则忽略）。"""
    base = (os.environ.get("JDY_WRAPPER_BASE_URL") or "http://192.168.0.6:8015").rstrip("/")
    key = os.environ.get("JDY_WRAPPER_API_KEY") or os.environ.get("FORM_API_KEY") or ""
    if not key:
        return {}
    try:
        req = urllib.request.Request(
            f"{base}/api/sync/departments?limit=500",
            headers={"X-API-Key": key, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        out: dict[str, str] = {}
        for it in data.get("items") or []:
            i, n = it.get("_id") or it.get("id"), it.get("name")
            if i and n:
                out[str(i)] = str(n)
        return out
    except Exception as exc:  # pragma: no cover
        logger.info("jdy dept sync unavailable: %s", exc)
        return {}


def jdy_dept_id_to_name() -> dict[str, str]:
    """JDY 部门 id → 名称（静态表 + 可选现网）。"""
    return {**JDY_DEPT_NAMES, **_fetch_live_jdy_dept_names()}


def jdy_person_id_to_name() -> dict[str, str]:
    """JDY 成员 MongoId → 姓名（静态表；CRM 名匹配见 build_jdy_to_crm_user_map）。"""
    return dict(JDY_PERSON_NAMES)


def _dept_name_aliases(name: str) -> list[str]:
    """简道云名 ↔ CRM 名常见差异（暂存前缀等）。"""
    n = (name or "").strip()
    if not n:
        return []
    out = [n]
    for prefix in ("（暂存）", "(暂存)", "【暂存】"):
        if n.startswith(prefix):
            stripped = n[len(prefix):].strip()
            if stripped:
                out.append(stripped)
        else:
            out.append(f"{prefix}{n}")
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


async def build_jdy_to_crm_dept_map(db: AsyncSession, tenant_id: str) -> dict[str, str]:
    """JDY 部门 MongoId → 本租户 CRM department.id（按名称精确匹配，含暂存别名）。"""
    rows = (
        await db.execute(
            select(Department.id, Department.name).where(Department.tenant_id == tenant_id)
        )
    ).all()
    by_name: dict[str, str] = {}
    for did, name in rows:
        if not name:
            continue
        for alias in _dept_name_aliases(str(name)):
            if alias not in by_name:
                by_name[alias] = did
    out: dict[str, str] = {}
    for jid, jname in jdy_dept_id_to_name().items():
        cid = None
        for alias in _dept_name_aliases(jname):
            cid = by_name.get(alias)
            if cid:
                break
        if cid:
            out[jid] = cid
    return out


def _iter_cond_leaves(cond: Any) -> Iterable[dict]:
    if not isinstance(cond, dict):
        return
    nodes = cond.get("cond")
    if isinstance(nodes, list):
        for n in nodes:
            if isinstance(n, dict) and "cond" in n:
                yield from _iter_cond_leaves(n)
            elif isinstance(n, dict) and n.get("field"):
                yield n
    elif cond.get("field"):
        yield cond


def routes_have_jdy_dept_ids(routes: list | None, fields: frozenset[str] = DEPT_COND_FIELDS) -> bool:
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        for leaf in _iter_cond_leaves(r.get("condition")):
            if str(leaf.get("field") or "") not in fields:
                continue
            val = leaf.get("value")
            vals = val if isinstance(val, list) else ([val] if val is not None else [])
            if any(is_jdy_mongo_id(v) for v in vals):
                return True
    return False


def remap_dept_ids_in_value(value: Any, id_map: dict[str, str]) -> Any:
    if isinstance(value, list):
        out = []
        for v in value:
            s = str(v) if v is not None else ""
            out.append(id_map.get(s, v))
        return out
    if is_jdy_mongo_id(value):
        return id_map.get(str(value), value)
    return value


def remap_jdy_dept_ids_in_routes(
    routes: list | None,
    id_map: dict[str, str],
    fields: frozenset[str] = DEPT_COND_FIELDS,
) -> tuple[list, dict[str, int]]:
    """深拷贝 routes，把指定字段条件值里的 JDY 部门 id 换成 CRM id。"""
    if not routes:
        return [], {"replaced": 0, "leaves": 0}
    raw = json.loads(json.dumps(routes, ensure_ascii=False))
    replaced = 0
    leaves = 0
    for r in raw:
        if not isinstance(r, dict):
            continue
        for leaf in _iter_cond_leaves(r.get("condition")):
            if str(leaf.get("field") or "") not in fields:
                continue
            leaves += 1
            before = json.dumps(leaf.get("value"), ensure_ascii=False, sort_keys=True)
            leaf["value"] = remap_dept_ids_in_value(leaf.get("value"), id_map)
            after = json.dumps(leaf.get("value"), ensure_ascii=False, sort_keys=True)
            if before != after:
                replaced += 1
    return raw, {"replaced": replaced, "leaves": leaves}


async def remap_routes_for_tenant(
    db: AsyncSession, tenant_id: str, routes: list | None,
) -> tuple[list, dict[str, int]]:
    id_map = await build_jdy_to_crm_dept_map(db, tenant_id)
    if not id_map:
        return list(routes or []), {"replaced": 0, "leaves": 0, "map_size": 0}
    new_routes, stats = remap_jdy_dept_ids_in_routes(routes, id_map)
    stats["map_size"] = len(id_map)
    return new_routes, stats


def _clean_dept_cond_node(
    node: dict,
    valid_ids: set[str],
    fields: frozenset[str],
    removed: list[str],
) -> dict | None:
    """清理单条条件节点；值全无效时返回 None（表示删除该条）。"""
    if "cond" in node and isinstance(node.get("cond"), list):
        kept: list[dict] = []
        for child in node["cond"]:
            if not isinstance(child, dict):
                continue
            cleaned = _clean_dept_cond_node(child, valid_ids, fields, removed)
            if cleaned is not None:
                kept.append(cleaned)
        if not kept:
            return None
        out = dict(node)
        out["cond"] = kept
        return out

    field = str(node.get("field") or "")
    if field not in fields:
        return node

    # 空值判断不依赖 value，切勿当成「无效部门 id」删掉
    op = str(node.get("operator") or node.get("method") or "")
    if op in ("is_empty", "is_not_empty", "empty", "not_empty"):
        return node

    val = node.get("value")
    if isinstance(val, list):
        kept_vals = []
        for v in val:
            s = str(v) if v is not None else ""
            if s in valid_ids:
                kept_vals.append(v)
            elif s:
                removed.append(s)
        if not kept_vals:
            return None
        out = dict(node)
        out["value"] = kept_vals
        return out

    if val is None or val == "":
        return None
    s = str(val)
    if s in valid_ids:
        return node
    removed.append(s)
    return None


def clean_unknown_dept_ids_in_routes(
    routes: list | None,
    valid_dept_ids: set[str],
    fields: frozenset[str] = DEPT_COND_FIELDS,
) -> tuple[list, dict[str, Any]]:
    """从连线条件中移除不在 CRM 部门表里的部门 id（设计器显示为「未知部门」）。

    某条条件值被清空后删除该条；整段 condition 无剩余叶子则**删除该连线**
   （勿置 condition=null，否则互斥组会多出假 else，串行节点被并行激活）。
    """
    if not routes:
        return [], {"routes_touched": 0, "values_removed": 0, "removed_ids": [], "routes_dropped": 0}
    raw = json.loads(json.dumps(routes, ensure_ascii=False))
    removed: list[str] = []
    routes_touched = 0
    routes_dropped = 0
    kept: list = []
    for r in raw:
        if not isinstance(r, dict):
            kept.append(r)
            continue
        cond = r.get("condition")
        if not isinstance(cond, dict):
            kept.append(r)
            continue
        before = json.dumps(cond, ensure_ascii=False, sort_keys=True)
        cleaned = _clean_dept_cond_node(cond, valid_dept_ids, fields, removed)
        after = json.dumps(cleaned, ensure_ascii=False, sort_keys=True) if cleaned else "null"
        if before == after:
            kept.append(r)
            continue
        routes_touched += 1
        if cleaned is None:
            routes_dropped += 1
            continue
        r["condition"] = cleaned
        kept.append(r)
    # 去重保序
    seen: set[str] = set()
    uniq_removed: list[str] = []
    for i in removed:
        if i not in seen:
            seen.add(i)
            uniq_removed.append(i)
    return kept, {
        "routes_touched": routes_touched,
        "values_removed": len(removed),
        "removed_ids": uniq_removed,
        "routes_dropped": routes_dropped,
    }


async def clean_unknown_dept_routes_for_tenant(
    db: AsyncSession, tenant_id: str, routes: list | None,
) -> tuple[list, dict[str, Any]]:
    rows = (
        await db.execute(
            select(Department.id).where(Department.tenant_id == tenant_id)
        )
    ).scalars().all()
    valid = {str(i) for i in rows}
    return clean_unknown_dept_ids_in_routes(routes, valid)


async def build_jdy_to_crm_user_map(db: AsyncSession, tenant_id: str) -> dict[str, str]:
    """JDY 成员 MongoId → 本租户 CRM user.id（按真实姓名精确匹配，重名取先到的）。"""
    from app.domains.auth.models import User

    rows = (
        await db.execute(
            select(User.id, User.real_name).where(
                User.tenant_id == tenant_id, User.is_active == True,  # noqa: E712
            )
        )
    ).all()
    by_name: dict[str, str] = {}
    for uid, name in rows:
        if name and name not in by_name:
            by_name[name] = uid
    out: dict[str, str] = {}
    for jid, jname in JDY_PERSON_NAMES.items():
        cid = by_name.get(jname)
        if cid:
            out[jid] = cid
    return out


def routes_have_jdy_person_ids(
    routes: list | None, fields: frozenset[str] = PERSON_COND_FIELDS,
) -> bool:
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        for leaf in _iter_cond_leaves(r.get("condition")):
            if str(leaf.get("field") or "") not in fields:
                continue
            val = leaf.get("value")
            vals = val if isinstance(val, list) else ([val] if val is not None else [])
            if any(is_jdy_mongo_id(v) for v in vals):
                return True
    return False


def remap_jdy_person_ids_in_routes(
    routes: list | None,
    id_map: dict[str, str],
    fields: frozenset[str] = PERSON_COND_FIELDS,
) -> tuple[list, dict[str, int]]:
    if not routes:
        return [], {"replaced": 0, "leaves": 0}
    raw = json.loads(json.dumps(routes, ensure_ascii=False))
    replaced = 0
    leaves = 0
    for r in raw:
        if not isinstance(r, dict):
            continue
        for leaf in _iter_cond_leaves(r.get("condition")):
            if str(leaf.get("field") or "") not in fields:
                continue
            leaves += 1
            before = json.dumps(leaf.get("value"), ensure_ascii=False, sort_keys=True)
            leaf["value"] = remap_dept_ids_in_value(leaf.get("value"), id_map)
            after = json.dumps(leaf.get("value"), ensure_ascii=False, sort_keys=True)
            if before != after:
                replaced += 1
    return raw, {"replaced": replaced, "leaves": leaves}


async def remap_person_routes_for_tenant(
    db: AsyncSession, tenant_id: str, routes: list | None,
) -> tuple[list, dict[str, int]]:
    id_map = await build_jdy_to_crm_user_map(db, tenant_id)
    if not id_map:
        return list(routes or []), {"replaced": 0, "leaves": 0, "map_size": 0}
    new_routes, stats = remap_jdy_person_ids_in_routes(routes, id_map)
    stats["map_size"] = len(id_map)
    return new_routes, stats


def clean_unknown_person_ids_in_routes(
    routes: list | None,
    fields: frozenset[str] = PERSON_COND_FIELDS,
) -> tuple[list, dict[str, Any]]:
    """去掉人员条件里仍残留的简道云 MongoId（映射不上的已离职/未知成员）。

    整段 condition 清空后删除连线（同部门清理，避免假 else）。
    """
    if not routes:
        return [], {"routes_touched": 0, "values_removed": 0, "removed_ids": [], "routes_dropped": 0}
    raw = json.loads(json.dumps(routes, ensure_ascii=False))
    removed: list[str] = []
    routes_touched = 0
    routes_dropped = 0

    def clean_node(node: dict) -> dict | None:
        if "cond" in node and isinstance(node.get("cond"), list):
            kept_children: list[dict] = []
            for child in node["cond"]:
                if not isinstance(child, dict):
                    continue
                c = clean_node(child)
                if c is not None:
                    kept_children.append(c)
            if not kept_children:
                return None
            out = dict(node)
            out["cond"] = kept_children
            return out
        field = str(node.get("field") or "")
        if field not in fields:
            return node
        val = node.get("value")
        if isinstance(val, list):
            kept_vals = []
            for v in val:
                s = str(v) if v is not None else ""
                if is_jdy_mongo_id(s):
                    removed.append(s)
                elif s:
                    kept_vals.append(v)
            if not kept_vals:
                return None
            out = dict(node)
            out["value"] = kept_vals
            return out
        if val is None or val == "":
            return None
        s = str(val)
        if is_jdy_mongo_id(s):
            removed.append(s)
            return None
        return node

    kept: list = []
    for r in raw:
        if not isinstance(r, dict):
            kept.append(r)
            continue
        cond = r.get("condition")
        if not isinstance(cond, dict):
            kept.append(r)
            continue
        before = json.dumps(cond, ensure_ascii=False, sort_keys=True)
        cleaned = clean_node(cond)
        after = json.dumps(cleaned, ensure_ascii=False, sort_keys=True) if cleaned else "null"
        if before == after:
            kept.append(r)
            continue
        routes_touched += 1
        if cleaned is None:
            routes_dropped += 1
            continue
        r["condition"] = cleaned
        kept.append(r)
    uniq = list(dict.fromkeys(removed))
    return kept, {
        "routes_touched": routes_touched,
        "values_removed": len(removed),
        "removed_ids": uniq,
        "routes_dropped": routes_dropped,
    }


async def sanitize_route_ids_for_tenant(
    db: AsyncSession, tenant_id: str, routes: list | None,
) -> tuple[list, dict[str, Any]]:
    """部门/人员：JDY id→CRM，并清掉无法映射的残留 MongoId。"""
    routes, dept_remap = await remap_routes_for_tenant(db, tenant_id, routes)
    routes, person_remap = await remap_person_routes_for_tenant(db, tenant_id, routes)
    routes, dept_clean = await clean_unknown_dept_routes_for_tenant(db, tenant_id, routes)
    routes, person_clean = clean_unknown_person_ids_in_routes(routes)
    return routes, {
        "dept_remap": dept_remap,
        "person_remap": person_remap,
        "dept_clean": dept_clean,
        "person_clean": person_clean,
    }
