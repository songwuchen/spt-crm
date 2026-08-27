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


def audit_labels_for_biz(
    biz_type: str | None,
    form_fields: list[dict] | None,
) -> dict[str, str]:
    """审批写回数据日志：业务模块字段 label。"""
    from app.common.audit_diff import labels_from_field_defs
    if biz_type == "tech_agreement_review":
        from app.domains.tech_agreement_review.field_labels import tar_field_labels
        return tar_field_labels()
    return labels_from_field_defs(form_fields)


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
    from app.domains.lowcode.prod_card_contract_fill import (
        PROD_CARD_LEGACY_HIDDEN_FIELDS,
        filter_prod_card_legacy_field_perms,
    )
    field_perms = filter_prod_card_legacy_field_perms(field_perms)
    allowed = {p["field"]: p["access"] for p in field_perms}
    raw = updates if isinstance(updates, dict) else {}
    raw = {k: v for k, v in raw.items() if k not in PROD_CARD_LEGACY_HIDDEN_FIELDS}
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
        # 明细表审批列：仅当本节点把明细标为 required 时强制
        # （editable 只表示可改行，如物流中心可看/改退回明细，但不强制「仓库判定」）
        for fid, acc in allowed.items():
            if acc != "required":
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

    if biz_type == "tech_agreement_review" and biz_id:
        from app.domains.tech_agreement_review.models import TechAgreementReview
        row = (await db.execute(select(TechAgreementReview).where(
            TechAgreementReview.id == biz_id, TechAgreementReview.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        if not row:
            return {}
        fj = dict(row.form_json) if isinstance(row.form_json, dict) else {}
        changes: dict[str, dict[str, Any]] = {}
        for k, v in updates.items():
            if k in _TAR_NATIVE_KEYS:
                old = getattr(row, k, None)
                if serialize_value(old) != serialize_value(v):
                    changes[k] = {"old": serialize_value(old), "new": serialize_value(v)}
            elif k in _TAR_FORM_KEYS:
                old = fj.get(k)
                if serialize_value(old) != serialize_value(v):
                    changes[f"form_json.{k}"] = {"old": serialize_value(old), "new": serialize_value(v)}
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


def _merge_field_perm_lists(perms_list: list[list[dict[str, str]]]) -> list[dict[str, str]]:
    """合并多节点 field_perms；同字段 required 优先于 editable。"""
    merged: dict[str, str] = {}
    nodes: dict[str, str] = {}
    for perms in perms_list:
        for p in perms:
            fid = p.get("field")
            if not fid:
                continue
            acc = p.get("access") or "editable"
            if fid not in merged or (merged[fid] != "required" and acc == "required"):
                merged[fid] = acc
            nodes.setdefault(fid, p.get("node_name") or "")
    return [
        {"field": fid, "access": acc, "node_name": nodes.get(fid, "")}
        for fid, acc in merged.items()
    ]


async def _node_defs_for_process(
    db: AsyncSession, tenant_id: str, process_instance_id: str,
) -> tuple[dict[str, dict], dict[str, dict], str | None]:
    """返回 (by_id, by_name, process_definition_id)。"""
    from app.domains.lowcode.workflow_models import WfProcessInstance, WfProcessDefinitionVersion

    inst = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.id == process_instance_id,
            WfProcessInstance.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if not inst:
        return {}, {}, None
    version = await db.get(WfProcessDefinitionVersion, inst.process_version_id)
    nodes = [n for n in (version.node_definitions if version else []) if isinstance(n, dict)]
    by_id = {str(n.get("id")): n for n in nodes if n.get("id")}
    by_name = {str(n.get("name")): n for n in nodes if n.get("name")}
    return by_id, by_name, inst.process_definition_id


async def _latest_published_node_defs(
    db: AsyncSession, tenant_id: str, process_definition_id: str | None,
) -> tuple[dict[str, dict], dict[str, dict]]:
    if not process_definition_id:
        return {}, {}
    from app.domains.lowcode.workflow_models import WfProcessDefinitionVersion

    pub = (await db.execute(
        select(WfProcessDefinitionVersion)
        .where(
            WfProcessDefinitionVersion.process_definition_id == process_definition_id,
            WfProcessDefinitionVersion.tenant_id == tenant_id,
            WfProcessDefinitionVersion.status == "published",
        )
        .order_by(WfProcessDefinitionVersion.version_number.desc())
        .limit(1)
    )).scalar_one_or_none()
    nodes = [n for n in (pub.node_definitions if pub else []) if isinstance(n, dict)]
    by_id = {str(n.get("id")): n for n in nodes if n.get("id")}
    by_name = {str(n.get("name")): n for n in nodes if n.get("name")}
    return by_id, by_name


def user_can_retroactive_edit(
    user: dict | None,
    inst_status: str | None,
    *,
    template_code: str | None = None,
) -> bool:
    """有 form_data:edit 且实例状态允许编辑 → 可补改已办节点字段。"""
    if not user:
        return False
    if "form_data:edit" not in (user.get("permissions") or []):
        return False
    from app.domains.lowcode.edit_lock import is_status_editable

    return is_status_editable(
        "form_instance", inst_status or "", template_code=template_code,
    )


async def collect_retroactive_field_perms(
    db: AsyncSession,
    tenant_id: str,
    process_instance_id: str | None,
    *,
    can_edit: bool = False,
) -> list[dict[str, str]]:
    """有编辑权限的用户：可补改流程中所有已办审批节点曾可填字段。"""
    if not process_instance_id or not can_edit:
        return []
    from app.domains.lowcode.workflow_models import WfNodeInstance, WfProcessInstance

    inst_row = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.id == process_instance_id,
            WfProcessInstance.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if not inst_row or inst_row.status not in ("running", "completed"):
        return []

    from app.domains.lowcode.prod_card_contract_fill import filter_prod_card_legacy_field_perms

    by_id, by_name, def_id = await _node_defs_for_process(db, tenant_id, process_instance_id)
    pub_by_id, pub_by_name = await _latest_published_node_defs(db, tenant_id, def_id)

    node_instances = (await db.execute(
        select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == process_instance_id,
            WfNodeInstance.status == "completed",
        )
    )).scalars().all()

    perms_batches: list[list[dict[str, str]]] = []
    for ni in node_instances:
        if ni.node_type in ("revise", "start", "end", "condition", "parallel", "cc"):
            continue
        if ni.node_def_id == "__initiator_revise__":
            continue
        node = by_id.get(ni.node_def_id or "") or by_name.get(ni.node_name or "") or {}
        node_type = node.get("type") or ni.node_type
        if node_type not in (None, "approval"):
            continue
        perms = parse_field_perms(node)
        if pub_by_id or pub_by_name:
            latest = pub_by_id.get(ni.node_def_id or "") or pub_by_name.get(ni.node_name or "")
            if latest:
                perms = parse_field_perms(latest)
        perms = filter_prod_card_legacy_field_perms(perms)
        if not perms:
            continue
        perms_batches.append([
            {**p, "node_name": ni.node_name or node.get("name") or ""} for p in perms
        ])
    return _merge_field_perm_lists(perms_batches)


async def collect_user_retroactive_field_perms(
    db: AsyncSession,
    tenant_id: str,
    process_instance_id: str | None,
    user_id: str | None,
    *,
    can_edit: bool | None = None,
) -> list[dict[str, str]]:
    """兼容旧调用；can_edit 为真时按「所有已办节点」收集 field_perms。"""
    del user_id  # 不再限定原节点处理人
    return await collect_retroactive_field_perms(
        db, tenant_id, process_instance_id,
        can_edit=bool(can_edit),
    )


def retroactive_change_summary(
    changes: dict[str, dict[str, Any]],
    retroactive_perms: list[dict[str, str]] | None,
    field_defs: list[dict[str, Any]] | None,
) -> str:
    """补改已办节点字段的数据日志摘要（含字段名与来源节点）。"""
    from app.common.audit_diff import labels_from_field_defs

    if not changes:
        return "补改已办节点字段"
    labels = labels_from_field_defs(field_defs)
    perm_by_field = {p["field"]: p for p in (retroactive_perms or []) if p.get("field")}
    parts: list[str] = []
    for fid in changes:
        label = labels.get(fid) or fid
        node = (perm_by_field.get(fid) or {}).get("node_name")
        parts.append(f"{label}({node})" if node else str(label))
    head = "、".join(parts[:10])
    if len(parts) > 10:
        head += f" 等{len(parts)}项"
    return f"补改已办节点字段: {head}"


def merge_retroactive_form_writes(
    sanitized: dict[str, Any],
    raw_incoming: dict[str, Any] | None,
    retroactive_perms: list[dict[str, str]] | None,
) -> dict[str, Any]:
    """整单保存：允许有编辑权限的用户覆盖已办节点 field_perms 内字段。"""
    from app.domains.lowcode.prod_card_contract_fill import PROD_CARD_LEGACY_HIDDEN_FIELDS

    if not retroactive_perms:
        return sanitized
    allowed = {
        p["field"] for p in retroactive_perms
        if p.get("access") in ("editable", "required") and p.get("field")
    }
    allowed -= PROD_CARD_LEGACY_HIDDEN_FIELDS
    if not allowed:
        return sanitized
    out = dict(sanitized or {})
    raw = raw_incoming if isinstance(raw_incoming, dict) else {}
    for fid in allowed:
        if fid in raw:
            out[fid] = raw[fid]
    return out
