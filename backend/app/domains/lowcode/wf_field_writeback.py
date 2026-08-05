"""审批节点字段写回：按节点 field_perms 白名单更新业务单据 / 表单实例。

与终态状态回写 wf_biz_writeback 分离：本模块在「通过」当时落字段，供后续条件边使用。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.common.error_codes import VALIDATION_ERROR
from app.common.exceptions import BusinessException

# 合同评审：落 review_json 的键
_REVIEW_JSON_KEYS = frozenset({
    "legal_risk", "legal_risk_desc", "tech_risk", "tech_risk_desc",
    "biz_risk", "biz_risk_desc", "finance_risk", "finance_risk_desc",
    "purchase_risk", "purchase_risk_desc", "export_risk", "export_risk_desc",
    "clause_opinion", "need_feedback", "feedback_members",
    "credit_level", "past_biz_desc", "pricing_supplement", "industry",
})
# 合同评审：一等公民列
_REVIEW_NATIVE_KEYS = frozenset({"payment_term", "conclusion"})

# 合同版本 → 合同 registration_json
_REG_JSON_KEYS = frozenset({
    "purchasers", "inspectors", "fill_code",
    "standard_delivery", "delivery_mode", "is_rotary_sieve",
    "industry", "is_export",
    "contract_type", "accept_method", "accept_materials", "accept_date",
})


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def parse_field_perms(node: dict | None) -> list[dict[str, str]]:
    """规范化节点 field_perms → [{field, access}]，access in editable|required。"""
    out: list[dict[str, str]] = []
    for raw in (node or {}).get("field_perms") or []:
        if not isinstance(raw, dict):
            continue
        field = raw.get("field") or raw.get("id")
        if not field:
            continue
        access = raw.get("access") or "editable"
        if access not in ("editable", "required"):
            access = "editable"
        out.append({"field": str(field), "access": access})
    return out


def validate_field_updates(
    field_perms: list[dict[str, str]],
    updates: dict[str, Any] | None,
    *,
    opinion: str | None = None,
    opinion_required: bool = False,
    action: str = "approve",
) -> dict[str, Any]:
    """校验并过滤 field_updates；仅 approve 时强制 required / opinion_required。"""
    allowed = {p["field"]: p["access"] for p in field_perms}
    raw = updates if isinstance(updates, dict) else {}
    unknown = [k for k in raw if k not in allowed]
    if unknown:
        raise BusinessException(
            code=VALIDATION_ERROR,
            message=f"本节点不可填写字段: {', '.join(unknown)}",
        )
    filtered = {k: raw[k] for k in raw if k in allowed}

    if action == "approve":
        if opinion_required and _is_empty(opinion):
            raise BusinessException(code=VALIDATION_ERROR, message="请填写审批意见")
        missing = [
            f for f, acc in allowed.items()
            if acc == "required" and _is_empty(filtered.get(f))
        ]
        if missing:
            raise BusinessException(
                code=VALIDATION_ERROR,
                message=f"请填写必填项: {', '.join(missing)}",
            )
    return filtered


async def load_field_values(
    db: AsyncSession, tenant_id: str, biz_type: str | None, biz_id: str | None,
    form_instance_id: str | None, fields: list[str],
) -> dict[str, Any]:
    """读取可填字段当前值（供审批抽屉回显）。"""
    if not fields:
        return {}
    values: dict[str, Any] = {}
    if form_instance_id:
        from app.domains.lowcode.models import FormInstance
        fi = await db.get(FormInstance, form_instance_id)
        if fi and fi.tenant_id == tenant_id:
            data = fi.form_data if isinstance(fi.form_data, dict) else {}
            for f in fields:
                if f in data:
                    values[f] = data[f]
            return values

    if not biz_type or not biz_id:
        return values

    if biz_type == "contract_review":
        from app.domains.contract_review.models import ContractReview
        row = (await db.execute(select(ContractReview).where(
            ContractReview.id == biz_id, ContractReview.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        if not row:
            return values
        rj = row.review_json if isinstance(row.review_json, dict) else {}
        for f in fields:
            if f in _REVIEW_NATIVE_KEYS:
                values[f] = getattr(row, f, None)
            elif f in rj:
                values[f] = rj.get(f)
        return values

    if biz_type == "contract_version":
        from app.domains.contract.models import Contract, ContractVersion
        ver = (await db.execute(select(ContractVersion).where(
            ContractVersion.id == biz_id, ContractVersion.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        if not ver:
            return values
        c = (await db.execute(select(Contract).where(
            Contract.id == ver.contract_id, Contract.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        if not c:
            return values
        reg = c.registration_json if isinstance(c.registration_json, dict) else {}
        for f in fields:
            if f in reg:
                values[f] = reg.get(f)
        return values

    # 通用：条件上下文里能拿到的标量
    try:
        from app.domains.approval.service import _build_policy_context
        ctx = await _build_policy_context(db, tenant_id, biz_type, biz_id) or {}
        for f in fields:
            if f in ctx:
                values[f] = ctx[f]
    except Exception:
        pass
    return values


async def apply_field_updates(
    db: AsyncSession, tenant_id: str, *,
    biz_type: str | None, biz_id: str | None, form_instance_id: str | None,
    updates: dict[str, Any],
) -> None:
    """按业务类型白名单写回。未知 biz 且无表单时忽略。"""
    if not updates:
        return

    if form_instance_id:
        from app.domains.lowcode.models import FormInstance
        fi = await db.get(FormInstance, form_instance_id)
        if fi and fi.tenant_id == tenant_id:
            data = dict(fi.form_data or {})
            data.update(updates)
            fi.form_data = data
            flag_modified(fi, "form_data")
            await db.flush()
            return

    if biz_type == "contract_review" and biz_id:
        await _patch_contract_review(db, tenant_id, biz_id, updates)
        return
    if biz_type == "contract_version" and biz_id:
        await _patch_contract_registration(db, tenant_id, biz_id, updates)
        return


async def _patch_contract_review(
    db: AsyncSession, tenant_id: str, rid: str, updates: dict[str, Any],
) -> None:
    from app.domains.contract_review.models import ContractReview
    row = (await db.execute(select(ContractReview).where(
        ContractReview.id == rid, ContractReview.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not row:
        raise BusinessException(code=VALIDATION_ERROR, message="合同评审不存在，无法写回字段")
    rj = dict(row.review_json) if isinstance(row.review_json, dict) else {}
    dirty_json = False
    for k, v in updates.items():
        if k in _REVIEW_NATIVE_KEYS:
            setattr(row, k, v)
        elif k in _REVIEW_JSON_KEYS:
            rj[k] = v
            dirty_json = True
        else:
            raise BusinessException(code=VALIDATION_ERROR, message=f"合同评审不支持写回字段: {k}")
    if dirty_json:
        row.review_json = rj
        flag_modified(row, "review_json")
    await db.flush()


async def _patch_contract_registration(
    db: AsyncSession, tenant_id: str, version_id: str, updates: dict[str, Any],
) -> None:
    from app.domains.contract.models import Contract, ContractVersion
    ver = (await db.execute(select(ContractVersion).where(
        ContractVersion.id == version_id, ContractVersion.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not ver:
        raise BusinessException(code=VALIDATION_ERROR, message="合同版本不存在，无法写回字段")
    c = (await db.execute(select(Contract).where(
        Contract.id == ver.contract_id, Contract.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not c:
        raise BusinessException(code=VALIDATION_ERROR, message="合同不存在，无法写回字段")
    reg = dict(c.registration_json) if isinstance(c.registration_json, dict) else {}
    for k, v in updates.items():
        if k not in _REG_JSON_KEYS:
            raise BusinessException(code=VALIDATION_ERROR, message=f"合同登记不支持写回字段: {k}")
        reg[k] = v
    c.registration_json = reg
    flag_modified(c, "registration_json")
    await db.flush()
