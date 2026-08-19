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
    "drawing_no", "opinion_exec",
})
# 合同评审：一等公民列
_REVIEW_NATIVE_KEYS = frozenset({"payment_term", "conclusion"})


def audit_resource_for_process(
    *,
    form_instance_id: str | None,
    biz_type: str | None,
    biz_id: str | None,
    process_instance_id: str,
) -> tuple[str, str]:
    """数据日志 resource：表单绑定流优先 form_instance，与前端 DataLog 对齐。"""
    if form_instance_id:
        return "form_instance", form_instance_id
    if biz_type and biz_id:
        return biz_type, biz_id
    return "wf_process_instance", process_instance_id

# 合同版本 → 合同 registration_json
_REG_JSON_KEYS = frozenset({
    "purchasers", "inspectors", "fill_code",
    "standard_delivery", "delivery_mode", "is_rotary_sieve",
    "industry", "is_export",
    "contract_type", "accept_method", "accept_materials", "accept_date",
})

# 技术协议评审：form_json / 原生列
_TAR_FORM_KEYS = frozenset({"design_approver_ids", "design_approver_2_ids"})
_TAR_NATIVE_KEYS = frozenset({"has_objection", "need_pricing", "has_smart", "owner_id", "department_id"})


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
    form_fields: list[dict] | None = None,
    form_rules: list[dict] | None = None,
    form_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """校验并过滤 field_updates；仅 approve 时强制 required / opinion_required。

    若传入 form_rules，按规则引擎显隐/条件必填判定：隐藏字段不强制必填。
    """
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
        field_by_id: dict[str, dict] = {}
        for fd in form_fields or []:
            if isinstance(fd, dict) and fd.get("id"):
                field_by_id[str(fd["id"])] = dict(fd)
        for fid in allowed:
            field_by_id.setdefault(fid, {"id": fid, "type": "text", "label": fid, "required": False})
        required_ids = {f for f, acc in allowed.items() if acc == "required"}
        if form_rules and required_ids:
            from app.domains.lowcode.rule_engine import compute_field_states

            fields = list(field_by_id.values())
            merged = {**(form_data or {}), **filtered}
            permissions = [
                {"fieldId": f, "access": "required" if acc == "required" else "editable"}
                for f, acc in allowed.items()
            ]
            states = compute_field_states(fields, merged, form_rules, permissions)
            missing = [
                f for f in required_ids
                if states.get(f, {}).get("visible", True)
                and states.get(f, {}).get("required", True)
                and _is_empty(filtered.get(f))
            ]
        else:
            missing = [
                f for f, acc in allowed.items()
                if acc == "required" and _is_empty(filtered.get(f))
            ]
        if missing:
            raise BusinessException(
                code=VALIDATION_ERROR,
                message=f"请填写必填项: {', '.join(missing)}",
            )
        # 明细表：审批节点可填列（fill_stage=approver）逐行校验
        for fid, acc in allowed.items():
            if acc not in ("editable", "required"):
                continue
            fd = field_by_id.get(fid)
            if not fd or fd.get("type") != "detail_table":
                continue
            rows = filtered.get(fid)
            if rows is None and form_data:
                rows = (form_data or {}).get(fid)
            approver_cols = [
                c for c in (fd.get("detail_table_columns") or [])
                if isinstance(c, dict)
                and c.get("fill_stage") == "approver"
                and c.get("required")
            ]
            if not approver_cols:
                continue
            if not isinstance(rows, list) or not rows:
                raise BusinessException(
                    code=VALIDATION_ERROR,
                    message=f"「{fd.get('label') or fid}」至少需要一行",
                )
            merged_rows = rows
            if filtered.get(fid) is not None and form_data and isinstance(form_data.get(fid), list):
                # 审批只 patch 了部分行时，以 form_data 为底、updates 覆盖
                base = [dict(r) if isinstance(r, dict) else {} for r in form_data[fid]]
                upd = filtered[fid]
                if isinstance(upd, list):
                    for i, row in enumerate(upd):
                        if i < len(base) and isinstance(row, dict):
                            base[i] = {**base[i], **row}
                        elif isinstance(row, dict):
                            base.append(row)
                    merged_rows = base
            for i, row in enumerate(merged_rows):
                row_map = row if isinstance(row, dict) else {}
                for c in approver_cols:
                    cid = c.get("id")
                    if _is_empty(row_map.get(cid)):
                        raise BusinessException(
                            code=VALIDATION_ERROR,
                            message=(
                                f"「{fd.get('label') or fid}」第 {i + 1} 行"
                                f"「{c.get('label') or cid}」为必填项"
                            ),
                        )
    return filtered


# 线索：审批节点可填的原生列
_LEAD_NATIVE_KEYS = frozenset({
    "customer_newness", "assess_remark", "reject_reason", "review_opinion",
    "has_internal_conflict", "conflict_note",
    "score", "industry", "customer_type", "category", "country_type",
})

_LEAD_REACT_FIELD_KEYS = frozenset({
    "project_recent", "follow_progress", "site_visit", "report_project_status",
})


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

    if biz_type == "lead":
        from app.domains.lead.models import Lead
        row = (await db.execute(select(Lead).where(
            Lead.id == biz_id, Lead.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        if not row:
            return values
        for f in fields:
            if f in _LEAD_NATIVE_KEYS or hasattr(row, f):
                values[f] = getattr(row, f, None)
        return values

    if biz_type == "lead_reactivation":
        from app.domains.lead.models import Lead
        row = (await db.execute(select(Lead).where(
            Lead.id == biz_id, Lead.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        if not row:
            return values
        allowed = _LEAD_NATIVE_KEYS | _LEAD_REACT_FIELD_KEYS
        for f in fields:
            if f in allowed or hasattr(row, f):
                values[f] = getattr(row, f, None)
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

    if biz_type == "tech_agreement_review":
        from app.domains.tech_agreement_review.models import TechAgreementReview
        row = (await db.execute(select(TechAgreementReview).where(
            TechAgreementReview.id == biz_id, TechAgreementReview.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        if not row:
            return values
        fj = row.form_json if isinstance(row.form_json, dict) else {}
        for f in fields:
            if f in _TAR_NATIVE_KEYS:
                values[f] = getattr(row, f, None)
            elif f in _TAR_FORM_KEYS or f in fj:
                values[f] = fj.get(f)
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


async def preview_field_update_changes(
    db: AsyncSession, tenant_id: str, *,
    biz_type: str | None, biz_id: str | None, form_instance_id: str | None,
    updates: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """审批写回前预览字段 diff（供数据日志）。"""
    from app.common.audit_diff import compute_dict_changes, serialize_value
    if not updates:
        return {}

    if form_instance_id:
        from app.domains.lowcode.models import FormInstance
        fi = await db.get(FormInstance, form_instance_id)
        if fi and fi.tenant_id == tenant_id:
            return compute_dict_changes(dict(fi.form_data or {}), {**(fi.form_data or {}), **updates})

    if biz_type == "contract_review" and biz_id:
        from app.domains.contract_review.models import ContractReview
        row = (await db.execute(select(ContractReview).where(
            ContractReview.id == biz_id, ContractReview.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        if not row:
            return {}
        rj = dict(row.review_json) if isinstance(row.review_json, dict) else {}
        changes: dict[str, dict[str, Any]] = {}
        for k, v in updates.items():
            if k in _REVIEW_NATIVE_KEYS:
                old = getattr(row, k, None)
                if serialize_value(old) != serialize_value(v):
                    changes[k] = {"old": serialize_value(old), "new": serialize_value(v)}
            elif k in _REVIEW_JSON_KEYS:
                old = rj.get(k)
                if serialize_value(old) != serialize_value(v):
                    changes[f"review_json.{k}"] = {"old": serialize_value(old), "new": serialize_value(v)}
        return changes

    if biz_type in ("lead", "lead_reactivation") and biz_id:
        from app.domains.lead.models import Lead
        row = (await db.execute(select(Lead).where(
            Lead.id == biz_id, Lead.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        if not row:
            return {}
        changes = {}
        for k, v in updates.items():
            if hasattr(row, k):
                old = getattr(row, k, None)
                if serialize_value(old) != serialize_value(v):
                    changes[k] = {"old": serialize_value(old), "new": serialize_value(v)}
        return changes

    return {}


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
            # 回写后重算公式（如总分 = 三项分数之和）
            try:
                from app.domains.lowcode.formula_engine import compute_formula_fields
                data = compute_formula_fields(data, fi.field_definitions or [], "")
            except Exception:
                pass
            fi.form_data = data
            flag_modified(fi, "form_data")
            await db.flush()
            return

    if biz_type in ("lead", "lead_reactivation") and biz_id:
        await _patch_lead(db, tenant_id, biz_id, updates, biz_type=biz_type)
        return
    if biz_type == "contract_review" and biz_id:
        await _patch_contract_review(db, tenant_id, biz_id, updates)
        return
    if biz_type == "tech_agreement_review" and biz_id:
        await _patch_tech_agreement_review(db, tenant_id, biz_id, updates)
        return
    if biz_type == "contract_version" and biz_id:
        await _patch_contract_registration(db, tenant_id, biz_id, updates)
        return


async def _patch_lead(
    db: AsyncSession, tenant_id: str, lead_id: str, updates: dict[str, Any],
    *, biz_type: str = "lead",
) -> None:
    from app.domains.lead.models import Lead
    row = (await db.execute(select(Lead).where(
        Lead.id == lead_id, Lead.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not row:
        return
    allowed = (
        (_LEAD_NATIVE_KEYS | _LEAD_REACT_FIELD_KEYS)
        if biz_type == "lead_reactivation"
        else _LEAD_NATIVE_KEYS
    )
    for k, v in updates.items():
        if k in allowed and hasattr(row, k):
            setattr(row, k, v)
    await db.flush()


async def _patch_tech_agreement_review(
    db: AsyncSession, tenant_id: str, rid: str, updates: dict[str, Any],
) -> None:
    from app.domains.tech_agreement_review.models import TechAgreementReview
    row = (await db.execute(select(TechAgreementReview).where(
        TechAgreementReview.id == rid, TechAgreementReview.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not row:
        raise BusinessException(code=VALIDATION_ERROR, message="技术协议评审不存在，无法写回字段")
    fj = dict(row.form_json) if isinstance(row.form_json, dict) else {}
    dirty_json = False
    for k, v in updates.items():
        if k in _TAR_NATIVE_KEYS:
            setattr(row, k, v)
        elif k in _TAR_FORM_KEYS:
            fj[k] = v
            dirty_json = True
        else:
            raise BusinessException(code=VALIDATION_ERROR, message=f"技术协议评审不支持写回字段: {k}")
    if dirty_json:
        row.form_json = fj
        flag_modified(row, "form_json")
    await db.flush()


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
