"""基础资料表选项查找（应用领域 / 应用物料 / 物料名称等）。

供合同登记、方案管理等表单远程下拉共用。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.error_codes import BUSINESS_ERROR
from app.common.exceptions import BusinessException

# form_code -> (builtin_key, name_field)
BASE_LOOKUP_FORMS: dict[str, tuple[str, str]] = {
    "application_field": ("application_field", "name"),
    "application_material": ("application_material", "name"),
    "material_name": ("material_name", "name"),
}


async def list_base_form_lookups(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    form_code: str,
    keyword: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """从内置基础表实例取选项（名称）。"""
    meta = BASE_LOOKUP_FORMS.get(form_code)
    if not meta:
        raise BusinessException(code=BUSINESS_ERROR, message=f"不支持的基础表: {form_code}")
    builtin_key, name_field = meta
    from app.domains.lowcode import service as lc_svc

    tpl = await lc_svc.ensure_builtin_form(db, tenant_id, builtin_key, user)
    page_size = min(max(limit, 1), 200)
    items, _ = await lc_svc.list_instances(
        db, tenant_id, tpl.id, 1, page_size,
        keyword=keyword or None, status=None, owner_ids=None,
    )
    out: list[dict] = []
    seen: set[str] = set()
    q = (keyword or "").strip().lower()
    for inst in items:
        if inst.status == "draft":
            continue
        fd = inst.form_data if isinstance(inst.form_data, dict) else {}
        name = str(fd.get(name_field) or "").strip()
        if not name or name in seen:
            continue
        if q and q not in name.lower():
            continue
        seen.add(name)
        out.append({"id": inst.id, "name": name, "label": name})
        if len(out) >= limit:
            break
    return out


def patch_scheme_material_columns(defs: list) -> None:
    """出方案图物料特性明细：绑基础资料多选；去掉与 *_star / 可多选 重复的文本列。"""
    for fd in defs or []:
        if not isinstance(fd, dict):
            continue
        if fd.get("type") == "detail_table":
            cols = [c for c in (fd.get("detail_table_columns") or []) if isinstance(c, dict)]
            ids = {c.get("id") for c in cols}
            has_multi = "material_names" in ids
            # 有 industry_star 则删 industry；有 bulk_density_star 则删 bulk_density …
            drop_plain = {
                cid[:-5]  # strip "_star"
                for cid in ids
                if isinstance(cid, str) and cid.endswith("_star") and cid[:-5]
            }
            cleaned: list = []
            for c in cols:
                cid = c.get("id")
                if has_multi and cid == "material_name":
                    continue
                if cid in drop_plain:
                    continue
                if cid == "material_names":
                    c["type"] = "multi_select"
                    c["options_source"] = "form:material_name:name"
                    c["placeholder"] = c.get("placeholder") or "请选择物料名称"
                # 列标题去掉尾部 *，必填仍由 required / 规则控制
                lab = str(c.get("label") or "")
                if lab.endswith("*") or lab.startswith("*"):
                    c["label"] = lab.strip("*").strip()
                cleaned.append(c)
            fd["detail_table_columns"] = cleaned
            patch_scheme_material_columns(cleaned)
        nested = fd.get("fields")
        if isinstance(nested, list):
            patch_scheme_material_columns(nested)


# 兼容旧调用名
patch_material_names_lookup = patch_scheme_material_columns
