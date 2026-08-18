"""扩展平台 — 表单引擎服务(CRM 风格函数式服务)。

移植自 spt-lowcode 表单服务,适配 CRM: 显式 tenant_id、db.commit() 内聚、current_user dict(user["sub"])。
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re

from sqlalchemy import func, select, or_, and_, not_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, VALIDATION_ERROR, DUPLICATE_ENTRY, BUSINESS_ERROR
from app.database import generate_uuid
from app.domains.lowcode.models import (
    FormInstance, FormTemplate, FormTemplateVersion,
)
from app.domains.lowcode import schemas
from app.domains.lowcode.formula_engine import compute_formula_fields
from app.domains.lowcode.serial_number import generate_serials_for_submit
from app.domains.lowcode.field_permission import filter_read, sanitize_write
from app.domains.lowcode.rule_engine import validate_required_with_rules


def _now() -> datetime:
    return datetime.now(timezone.utc)


# 表单填报未传 title 时，从模板名 + 关键业务字段拼审批标题（对齐合同评审/线索「有意义的标题」）
_TITLE_FIELD_IDS = (
    "apply_reason", "apply_or_change", "apply_reason_star",
    "contract_no", "drawing_no", "company_name", "title", "reason",
    "applicant_name", "orderer_name", "remark",
)
_TITLE_LABEL_HINTS = (
    "申请事由", "*申请事由", "申请事由/修改事项",
    "合同号", "图纸编号", "标题", "事由", "备注",
)
# 报价等：单号 + 客户 + 业务员拼进审批标题（人员/客户存 UUID，需 id_labels）
_COMPOSITE_TITLE_FIELD_IDS = ("serial_no", "quote_no", "customer_name", "sales_person")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _title_snippet(val, id_labels: dict[str, str] | None = None) -> str:
    labels = id_labels or {}
    if val is None:
        return ""
    if isinstance(val, dict):
        named = str(val.get("name") or val.get("label") or "").strip()
        if named and named != "None":
            return named
        rid = val.get("id")
        if rid is not None:
            return labels.get(str(rid), "")
        return ""
    if isinstance(val, list):
        parts = [_title_snippet(x, labels) for x in val]
        return "、".join(p for p in parts if p)[:40]
    s = str(val).strip()
    if not s or s == "None":
        return ""
    if s in labels:
        return labels[s]
    # 人员/部门/客户字段常存 UUID，不当作标题片段（除非已解析到 labels）
    if len(s) >= 32 and s.count("-") >= 4:
        return ""
    return s


def is_weak_form_title(title: str | None, template_name: str | None = None) -> bool:
    """仅有模板/流程名、无业务片段的标题视为弱标题，可回写补齐。"""
    t = (title or "").strip()
    if not t:
        return True
    name = (template_name or "").strip()
    if name and t == name:
        return True
    # 「报价管理:」这类空片段
    if name and t in (f"{name}:", f"{name}："):
        return True
    return False


def _compose_multi_snippet_title(name: str, parts: list[str]) -> str:
    cleaned: list[str] = []
    for p in parts:
        s = (p or "").strip()
        if s and s not in cleaned:
            cleaned.append(s)
    if not cleaned:
        return name
    joined = " · ".join(cleaned)
    if len(joined) > 72:
        joined = joined[:71] + "…"
    return f"{name}: {joined}"


def _should_use_composite_title(
    template_name: str | None,
    form_data: dict,
    field_defs: list | None,
) -> bool:
    name = template_name or ""
    if "报价" in name:
        return True
    if any(form_data.get(fid) not in (None, "", []) for fid in _COMPOSITE_TITLE_FIELD_IDS):
        # 同时具备客户+业务员（或流水号）时，按组合标题拼，避免只抽到申请事由类字段
        has_customer = form_data.get("customer_name") not in (None, "", [])
        has_sales = form_data.get("sales_person") not in (None, "", [])
        has_no = form_data.get("serial_no") not in (None, "", []) or form_data.get("quote_no") not in (None, "", [])
        if has_customer or (has_sales and has_no) or (has_customer and has_sales):
            return True
    if field_defs:
        ids = {
            str(f.get("id"))
            for f in field_defs if isinstance(f, dict) and f.get("id")
        }
        if {"serial_no", "customer_name", "sales_person"}.issubset(ids):
            return True
    return False


def derive_form_instance_title(
    template_name: str | None,
    form_data: dict | None,
    field_defs: list | None = None,
    id_labels: dict[str, str] | None = None,
) -> str:
    """生成表单实例/流程标题，如「报价管理: 单号 · 客户 · 业务员」。"""
    name = (template_name or "表单申请").strip() or "表单申请"
    data = form_data or {}
    labels = id_labels or {}

    if _should_use_composite_title(name, data, field_defs):
        parts = [
            _title_snippet(data.get(fid), labels)
            for fid in _COMPOSITE_TITLE_FIELD_IDS
        ]
        composed = _compose_multi_snippet_title(name, parts)
        if composed != name:
            return composed

    snippet = ""
    for fid in _TITLE_FIELD_IDS:
        snippet = _title_snippet(data.get(fid), labels)
        if snippet:
            break
    if not snippet and field_defs:
        by_label = {
            str(f.get("label") or "").strip(): f.get("id")
            for f in field_defs if isinstance(f, dict) and f.get("id")
        }
        for hint in _TITLE_LABEL_HINTS:
            fid = by_label.get(hint)
            if not fid:
                continue
            snippet = _title_snippet(data.get(fid), labels)
            if snippet:
                break
    if snippet:
        if len(snippet) > 40:
            snippet = snippet[:39] + "…"
        return f"{name}: {snippet}"
    return name


def _collect_title_ref_ids(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        out: list[str] = []
        for x in value:
            out.extend(_collect_title_ref_ids(x))
        return out
    if isinstance(value, dict):
        rid = value.get("id")
        return [str(rid)] if rid else []
    s = str(value).strip()
    return [s] if s else []


async def resolve_form_title_labels(
    db: AsyncSession,
    tenant_id: str,
    form_data: dict | None,
    field_defs: list | None = None,
) -> dict[str, str]:
    """把标题相关人员/客户 UUID 解析成显示名。"""
    data = form_data or {}
    type_by_id: dict[str, str] = {}
    if field_defs:
        type_by_id = {
            str(f.get("id")): str(f.get("type") or "")
            for f in field_defs if isinstance(f, dict) and f.get("id")
        }
    # 无字段定义时仍按常见 id 解析
    for fid, ftype in (
        ("sales_person", "person"),
        ("customer_name", "customer"),
        ("purchaser", "person"),
    ):
        type_by_id.setdefault(fid, ftype)

    person_ids: set[str] = set()
    customer_ids: set[str] = set()
    for fid, ftype in type_by_id.items():
        if fid not in data and fid not in _COMPOSITE_TITLE_FIELD_IDS:
            continue
        ids = _collect_title_ref_ids(data.get(fid))
        if ftype in ("person", "person_multi", "user"):
            person_ids.update(i for i in ids if _UUID_RE.match(i))
        elif ftype == "customer":
            customer_ids.update(i for i in ids if _UUID_RE.match(i))
    # 组合标题字段即使类型未知也尝试解析
    for fid in ("sales_person", "customer_name"):
        for i in _collect_title_ref_ids(data.get(fid)):
            if not _UUID_RE.match(i):
                continue
            if fid == "customer_name":
                customer_ids.add(i)
            else:
                person_ids.add(i)

    labels: dict[str, str] = {}
    if person_ids:
        from app.domains.auth.models import User
        rows = (await db.execute(
            select(User.id, User.real_name, User.username).where(
                User.tenant_id == tenant_id,
                User.id.in_(person_ids),
            )
        )).all()
        for uid, real_name, username in rows:
            labels[str(uid)] = (real_name or username or "").strip() or str(uid)
    if customer_ids:
        from app.domains.customer.models import Customer
        rows = (await db.execute(
            select(Customer.id, Customer.name).where(
                Customer.tenant_id == tenant_id,
                Customer.id.in_(customer_ids),
            )
        )).all()
        for cid, cname in rows:
            if cname:
                labels[str(cid)] = str(cname).strip()
    return labels


async def derive_form_instance_title_resolved(
    db: AsyncSession,
    tenant_id: str,
    template_name: str | None,
    form_data: dict | None,
    field_defs: list | None = None,
) -> str:
    labels = await resolve_form_title_labels(db, tenant_id, form_data, field_defs)
    return derive_form_instance_title(template_name, form_data, field_defs, id_labels=labels)


# ==================== 模板 ====================

async def create_template(
    db: AsyncSession, tenant_id: str, data: schemas.FormTemplateCreate, user: dict
) -> FormTemplate:
    code = data.code or f"FORM_{generate_uuid()[:8].upper()}"
    existing = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.code == code,
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if existing:
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"表单模板编码 {code} 已存在")

    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=tenant_id,
        name=data.name, code=code, description=data.description,
        category=data.category, icon=data.icon, sort_order=data.sort_order,
        status="draft", current_version=0, created_by=user.get("sub"),
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def install_builtin_template(
    db: AsyncSession, tenant_id: str, key: str, user: dict
) -> FormTemplate:
    """从内置模板库安装一个模板为本租户草稿表单（含字段的 v1 草稿版本），返回新模板。"""
    from app.domains.lowcode.builtin_templates import get_builtin
    bt = get_builtin(key)
    if not bt:
        raise BusinessException(code=NOT_FOUND, message="内置模板不存在")
    # 保证 code 在租户内唯一(uq_lc_form_template_tenant_code),避免极小概率碰撞抛 IntegrityError。
    code = f"BLT_{key.upper()}_{generate_uuid()[:6].upper()}"
    for _ in range(5):
        dup = (await db.execute(select(FormTemplate.id).where(
            FormTemplate.tenant_id == tenant_id, FormTemplate.code == code,
        ).limit(1))).scalar_one_or_none()
        if not dup:
            break
        code = f"BLT_{key.upper()}_{generate_uuid()[:8].upper()}"
    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=tenant_id,
        name=bt["name"], code=code, description=bt.get("description"),
        category=bt.get("category"), icon=bt.get("icon"),
        status="draft", current_version=0, created_by=user.get("sub"),
    )
    db.add(tpl)
    await db.flush()
    from app.domains.lowcode.pickable_scope import strip_spt_scheme_pickable_scopes
    version = FormTemplateVersion(
        id=generate_uuid(), tenant_id=tenant_id, template_id=tpl.id,
        version_number=1,
        field_definitions=strip_spt_scheme_pickable_scopes(tenant_id, bt["field_definitions"]),
        layout_definition={}, rule_definitions=bt.get("rule_definitions", []),
        status="draft",
    )
    db.add(version)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def get_template_by_code(
    db: AsyncSession, tenant_id: str, code: str,
) -> FormTemplate | None:
    """按稳定 code 取模板（不含已删除）。"""
    if not code:
        return None
    return (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.code == code,
            FormTemplate.is_deleted == False,  # noqa: E712
        ).limit(1)
    )).scalar_one_or_none()


async def _ensure_builtin_form_flow(db: AsyncSession, tenant_id: str, key: str, form_id: str) -> None:
    """若该内置表单在 FORM_DEFAULT_SPECS 中，幂等创建并发布绑定表单的默认审批流。"""
    from app.domains.lowcode import workflow_service as wsvc
    spec = next((s for s in wsvc.FORM_DEFAULT_SPECS if s["form_code"] == key), None)
    if not spec:
        return
    try:
        await wsvc.ensure_default_form_definition(
            db, tenant_id,
            form_template_id=form_id,
            code=spec["code"],
            name=spec["name"],
            approver_rule=spec["approver_rule"],
            multi_mode=spec.get("multi_mode", "or_sign"),
            empty_strategy=spec.get("empty_strategy", "auto_approve"),
        )
    except Exception as e:
        import logging
        logging.getLogger("spt_crm.lowcode").warning(
            "ensure form flow for %s failed: %s", key, e,
        )


def _field_defs_fingerprint(defs: list | None) -> str:
    """字段 id/类型/选项/必填/标签/流水规则指纹，用于 sync_fields 幂等升级。"""
    items: list[tuple] = []
    for f in defs or []:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        cols = []
        for c in f.get("detail_table_columns") or []:
            if not isinstance(c, dict) or not c.get("id"):
                continue
            cols.append((
                str(c.get("id")),
                str(c.get("type") or ""),
                str(c.get("label") or ""),
                bool(c.get("required")),
                json.dumps(c.get("options") or [], sort_keys=True, ensure_ascii=False),
            ))
        items.append((
            str(f.get("id")),
            str(f.get("type") or ""),
            str(f.get("label") or ""),
            bool(f.get("required")),
            bool(f.get("available_on_create", True)),
            str(f.get("fill_stage") or ""),
            bool(f.get("form_editable", True)),
            json.dumps(f.get("options") or [], sort_keys=True, ensure_ascii=False),
            json.dumps(f.get("props") or {}, sort_keys=True, ensure_ascii=False),
            json.dumps(f.get("default_value"), ensure_ascii=False, default=str)
            if f.get("default_value") is not None else "",
            json.dumps(cols, ensure_ascii=False),
        ))
    return json.dumps(sorted(items), ensure_ascii=False)


def _rules_fingerprint(rules: list | None) -> str:
    """规则 id/type/target/condition/action 指纹，用于 sync_fields 与字段一并升级。"""
    items: list[tuple] = []
    for r in rules or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        items.append((
            str(r.get("id")),
            str(r.get("type") or ""),
            str(r.get("target_field_id") or ""),
            json.dumps(r.get("target_field_ids") or [], ensure_ascii=False),
            json.dumps(r.get("condition") or {}, sort_keys=True, ensure_ascii=False),
            json.dumps(r.get("action") or {}, sort_keys=True, ensure_ascii=False),
            bool(r.get("enabled", True)),
        ))
    return json.dumps(sorted(items), ensure_ascii=False)


async def sync_builtin_form_fields(
    db: AsyncSession, tenant_id: str, key: str, tpl: FormTemplate, user: dict,
) -> FormTemplate:
    """图纸等标记 sync_fields 的内置表：字段/规则与 builtin 不一致时发布新版本。"""
    from app.domains.lowcode.builtin_templates import get_builtin
    bt = get_builtin(key)
    if not bt or not bt.get("sync_fields"):
        return tpl
    want = bt.get("field_definitions") or []
    if not want:
        return tpl
    want_rules = bt.get("rule_definitions") or []
    published = await _get_published_version(db, tenant_id, tpl.id)
    current = (published.field_definitions if published else None) or []
    current_rules = (published.rule_definitions if published else None) or []
    # 合并：保留租户在设计器里配的阶段/必填/权限/标签，避免 ensure 覆盖页面配置
    want = _merge_builtin_field_defs(want, current)
    from app.domains.lowcode.pickable_scope import strip_spt_scheme_pickable_scopes
    want = strip_spt_scheme_pickable_scopes(tenant_id, want)
    # 客户服务部简道云副本：必填/只读/发起可见必须以 builtin 为准。
    # 否则租户首装旧版（仅客户名称必填）会经 _merge 永久盖住 allowBlank=false。
    if key.startswith("cs_"):
        raw_by = {
            f["id"]: f
            for f in (bt.get("field_definitions") or [])
            if isinstance(f, dict) and f.get("id")
        }
        for fd in want:
            if not isinstance(fd, dict):
                continue
            raw = raw_by.get(fd.get("id"))
            if not raw:
                continue
            for k in ("required", "form_editable", "available_on_create", "fill_stage"):
                if k in raw:
                    fd[k] = raw[k]
                elif k == "required":
                    fd["required"] = False
                elif k == "form_editable":
                    fd.pop("form_editable", None)
            raw_cols = {
                c["id"]: c
                for c in (raw.get("detail_table_columns") or [])
                if isinstance(c, dict) and c.get("id")
            }
            cols = fd.get("detail_table_columns") or []
            if raw_cols and cols:
                for col in cols:
                    if not isinstance(col, dict):
                        continue
                    rc = raw_cols.get(col.get("id"))
                    if not rc:
                        continue
                    if "required" in rc:
                        col["required"] = rc["required"]
                    else:
                        col["required"] = False
        # 长说明类字段：单行输入体验差，填报页用多行（简道云 widget 仍为 text）
        if key == "cs_service_request":
            for fd in want:
                if isinstance(fd, dict) and fd.get("id") in ("field_5", "field_6", "remark"):
                    fd["type"] = "textarea"
    if key == "prod_card_supplement":
        from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_contract_pick_fields
        apply_prod_card_contract_pick_fields(want)
    if key == "payment_registration":
        from app.domains.lowcode.payment_registration_fields import apply_payment_registration_fields
        apply_payment_registration_fields(want)
    if key == "invoice_application":
        from app.domains.lowcode.invoice_application_fields import apply_invoice_application_fields
        apply_invoice_application_fields(want)
    if key == "quote_management":
        from app.domains.lowcode.quote_management_fields import apply_quote_management_fields
        apply_quote_management_fields(want)
    if key == "drawing_requisition":
        from app.domains.lowcode.drawing_requisition_fields import (
            apply_drawing_requisition_fields,
        )
        # 创建/审批阶段以 builtin 为准，避免租户旧版把审批字段放回创建页
        raw_by = {
            f["id"]: f
            for f in (bt.get("field_definitions") or [])
            if isinstance(f, dict) and f.get("id")
        }
        for fd in want:
            if not isinstance(fd, dict):
                continue
            raw = raw_by.get(fd.get("id"))
            if raw:
                for k in ("available_on_create", "fill_stage", "required", "form_editable"):
                    if k in raw:
                        fd[k] = raw[k]
        apply_drawing_requisition_fields(want)
        want_rules = [
            r for r in want_rules
            if not (
                isinstance(r, dict)
                and (
                    r.get("target_field_id") in ("order_person_text", "designer_text", "need_decrypt_note")
                    or bool(
                        set(r.get("target_field_ids") or [])
                        & {"order_person_text", "designer_text", "need_decrypt_note"}
                    )
                )
            )
        ]
    if key == "install_drawing_notice":
        from app.domains.lowcode.base_lookups import remap_scheme_material_rule_triggers
        from app.domains.lowcode.dept_code import (
            apply_design_card_serial_rules,
            apply_install_drawing_serial_no_field,
        )
        from app.domains.lowcode.install_drawing_notice_fields import (
            apply_install_drawing_notice_fields,
        )
        apply_design_card_serial_rules(want)
        apply_install_drawing_serial_no_field(want)
        apply_install_drawing_notice_fields(want)
        want_rules = [
            r for r in want_rules
            if not (
                isinstance(r, dict)
                and (
                    r.get("target_field_id") == "order_person_text"
                    or "order_person_text" in set(r.get("target_field_ids") or [])
                )
            )
        ]
        remap_scheme_material_rule_triggers(want_rules)
    if key == "scheme_management":
        from app.domains.lowcode.base_lookups import (
            patch_scheme_material_columns, remap_scheme_material_rule_triggers,
        )
        from app.domains.lowcode.dept_code import (
            apply_design_card_serial_rules, apply_scheme_serial_no_field,
        )
        apply_design_card_serial_rules(want)
        apply_scheme_serial_no_field(want)
        patch_scheme_material_columns(want)
        remap_scheme_material_rule_triggers(want_rules)
        # 保证关联客户 + 公司名称回填语义不被旧租户版本带偏
        has_related_customer = any(
            isinstance(fd, dict) and fd.get("id") == "related_customer" for fd in want
        )
        if not has_related_customer:
            want.insert(2, {
                "id": "related_customer",
                "type": "customer",
                "label": "关联客户",
                "required": False,
                "description": "从客户管理中选择；可不选商机只选客户。",
                "available_on_create": True,
                "fill_stage": "initiator",
            })
        for fd in want:
            if not isinstance(fd, dict):
                continue
            if fd.get("id") == "customer_name":
                fd["type"] = "text"
                fd["label"] = fd.get("label") or "公司名称"
                fd["description"] = "由关联商机 / 关联客户自动回填。"
                props = dict(fd.get("props") or {})
                props["read_only"] = True
                props.pop("from_project_field", None)
                fd["props"] = props
            if fd.get("id") == "related_customer":
                fd["type"] = "customer"
                fd["label"] = fd.get("label") or "关联客户"
            if fd.get("id") == "contract_no":
                fd["type"] = "contract"
                fd["label"] = "合同号"
                fd["description"] = "从合同管理中选择；按图纸编号搜索，选项以图纸编号显示。"
            if fd.get("id") == "apply_or_change":
                fd["type"] = "textarea"
                fd["label"] = "申请事由/修改事项(如表述不完，请填至备注)"
                fd["description"] = ""
                fd["available_on_create"] = True
                fd["fill_stage"] = "initiator"
            if fd.get("id") in ("scheme_detail", "install_env", "scheme_material"):
                props = dict(fd.get("props") or {})
                props["ensure_min_rows"] = 1
                fd["props"] = props
            if fd.get("id") == "transfer_packaging_users":
                fd["type"] = "person_multi"
            # 科室多选（有合同号 offices / 无合同号 offices_multi）
            if fd.get("id") in ("offices", "offices_multi"):
                fd["type"] = "department_multi"
                fd["label"] = "科室"
            if fd.get("id") in (
                "apply_datetime", "order_date", "card_date",
                "require_draw_date",
            ):
                fd["type"] = "date"
                props = dict(fd.get("props") or {})
                props["show_time"] = False
                props["date_only"] = True
                if fd.get("id") == "order_date":
                    props["default_today"] = True
                fd["props"] = props
        # 确保下图类型四选项完整（避免旧租户版本被裁过选项后合并不回来）
        for fd in want:
            if isinstance(fd, dict) and fd.get("id") == "drawing_issue_type":
                fd["options"] = [
                    {"label": "出方案图", "value": "出方案图"},
                    {"label": "出测绘图", "value": "出测绘图"},
                    {"label": "修改方案", "value": "修改方案"},
                    {"label": "领图", "value": "领图"},
                ]
                break
        # 方案管理已去掉的字段（明细 + 是否上交图纸 + 业务打分）
        _scheme_drop_ids = {
            "change_scheme", "non_scheme_material", "need_submit_drawing",
            "score_attitude", "score_progress", "score_skill",
            "score_total", "score_date",
        }
        want = [
            fd for fd in want
            if not (isinstance(fd, dict) and fd.get("id") in _scheme_drop_ids)
        ]
        want_rules = [
            r for r in want_rules
            if not (
                isinstance(r, dict)
                and (
                    (
                        r.get("type") == "visibility"
                        and (
                            r.get("target_field_id") == "apply_or_change"
                            or "apply_or_change" in (r.get("target_field_ids") or [])
                            or r.get("target_field_id") == "need_gm_approval"
                            or "need_gm_approval" in (r.get("target_field_ids") or [])
                        )
                    )
                    or (
                        r.get("target_field_id") in _scheme_drop_ids
                        or bool(set(r.get("target_field_ids") or []) & _scheme_drop_ids)
                    )
                )
            )
        ]
        # 条件必填字段：禁止租户旧版把 static required=True 盖回来
        cond_required_ids: set[str] = set()
        for r in want_rules:
            if not isinstance(r, dict) or r.get("type") != "required":
                continue
            if r.get("target_field_id"):
                cond_required_ids.add(str(r["target_field_id"]))
            for tid in r.get("target_field_ids") or []:
                cond_required_ids.add(str(tid))
        for fd in want:
            if isinstance(fd, dict) and fd.get("id") in cond_required_ids:
                fd["required"] = False
        # 附件类 + 备注：只做显隐，强制非必填（对齐业务预期，避免规则「显示」与提交「必填」打架）
        attach_optional = {
            "attachment_name", "attachment_names", "attachments", "attachments_no_image", "images",
            "remark",
        }
        for fd in want:
            if isinstance(fd, dict) and fd.get("id") in attach_optional:
                fd["required"] = False
        want_rules = [
            r for r in want_rules
            if not (
                isinstance(r, dict)
                and r.get("type") == "required"
                and (
                    r.get("target_field_id") in attach_optional
                    or any(t in attach_optional for t in (r.get("target_field_ids") or []))
                )
            )
        ]
    if key == "pricing_checklist_hjqd":
        from app.domains.lowcode.pricing_checklist_fields import apply_pricing_checklist_fields
        apply_pricing_checklist_fields(want)
        # 核价清单附件仅财务可打开；ensure/sync 强制回写，避免旧版本缺配置
        for fd in want:
            if isinstance(fd, dict) and fd.get("id") in ("attachments", "images"):
                fd["download_roles"] = ["finance", "finance_manager"]
    same_fields = _field_defs_fingerprint(current) == _field_defs_fingerprint(want)
    same_rules = _rules_fingerprint(current_rules) == _rules_fingerprint(want_rules)
    if same_fields and same_rules:
        return tpl
    latest = await _get_latest_version(db, tenant_id, tpl.id)
    if latest and latest.status == "draft":
        latest.field_definitions = want
        latest.rule_definitions = want_rules
        await db.commit()
    else:
        next_version = (latest.version_number + 1) if latest else 1
        db.add(FormTemplateVersion(
            id=generate_uuid(), tenant_id=tenant_id, template_id=tpl.id,
            version_number=next_version, field_definitions=want,
            layout_definition=(latest.layout_definition if latest else {}) or {},
            rule_definitions=want_rules,
            status="draft",
        ))
        await db.commit()
    await publish(db, tenant_id, tpl.id, user.get("sub") or "")
    await db.refresh(tpl)
    return tpl


_FIELD_TENANT_OVERRIDE_KEYS = (
    "available_on_create", "fill_stage", "required", "form_editable",
    "visible_roles", "unmask_roles", "edit_roles",
    "label", "placeholder", "description", "span",
)


def _merge_field_props(want_props: dict | None, cur_props: dict | None) -> dict | None:
    """合并 props：builtin 有的键优先；租户已配的 pickable_scope 在 builtin 未声明时保留。

    避免 ensure/sync 用无范围的 builtin 字段把「转新乡、工艺包装」等已配范围冲掉，
    导致审批选人又变成全员。
    """
    w = dict(want_props or {}) if isinstance(want_props, dict) else {}
    c = dict(cur_props or {}) if isinstance(cur_props, dict) else {}
    if not w and not c:
        return None
    out = dict(c)
    out.update(w)
    want_scope = w.get("pickable_scope") if isinstance(w.get("pickable_scope"), dict) else None
    cur_scope = c.get("pickable_scope") if isinstance(c.get("pickable_scope"), dict) else None
    if cur_scope and not (want_scope and want_scope.get("scope_code")):
        out["pickable_scope"] = cur_scope
    elif want_scope:
        out["pickable_scope"] = want_scope
    return out or None


def _merge_builtin_field_defs(want: list, current: list) -> list:
    """builtin 结构为准，租户阶段/必填/权限/文案覆盖同 id 字段。"""
    cur_by_id = {
        f.get("id"): f for f in (current or [])
        if isinstance(f, dict) and f.get("id")
    }
    out: list = []
    seen: set[str] = set()
    for f in want or []:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        fid = f["id"]
        seen.add(fid)
        c = cur_by_id.get(fid)
        if not c:
            out.append(dict(f))
            continue
        merged = dict(f)
        for k in _FIELD_TENANT_OVERRIDE_KEYS:
            if k in c:
                merged[k] = c[k]
        merged_props = _merge_field_props(
            f.get("props") if isinstance(f.get("props"), dict) else None,
            c.get("props") if isinstance(c.get("props"), dict) else None,
        )
        if merged_props is not None:
            merged["props"] = merged_props
        elif "props" in merged and not merged.get("props"):
            merged.pop("props", None)
        # 明细列：按列 id 保留必填等
        want_cols = merged.get("detail_table_columns") or []
        cur_cols = {
            col.get("id"): col for col in (c.get("detail_table_columns") or [])
            if isinstance(col, dict) and col.get("id")
        }
        if want_cols and cur_cols:
            new_cols = []
            for col in want_cols:
                if not isinstance(col, dict) or not col.get("id"):
                    continue
                cc = cur_cols.get(col["id"])
                if not cc:
                    new_cols.append(dict(col))
                    continue
                mc = dict(col)
                for k in ("required", "label", "placeholder"):
                    if k in cc:
                        mc[k] = cc[k]
                new_cols.append(mc)
            merged["detail_table_columns"] = new_cols
        out.append(merged)
    # sync_fields 内置表以 builtin 字段列表为准：不再把「当前有、builtin 已删」的字段
    # 当租户扩展保留，否则删字段（如 order_person_text）永远删不掉。
    return out


async def ensure_builtin_form(
    db: AsyncSession, tenant_id: str, key: str, user: dict,
) -> FormTemplate:
    """侧栏模块用：按固定 code=key 确保内置表单已安装并发布。

    - 已存在：sync_fields 表按 builtin 幂等升级字段；否则不覆盖租户定制。
    - 不存在：以 code=key 安装 v1 并立即 publish。
    - 图纸等已配置默认流的模块：同时幂等创建/升级绑定该表单的审批流程。
    """
    from app.domains.lowcode.builtin_templates import get_builtin
    bt = get_builtin(key)
    if not bt:
        raise BusinessException(code=NOT_FOUND, message="内置模板不存在")

    existing = await get_template_by_code(db, tenant_id, key)
    if existing:
        # 内置业务表展示名与侧栏/表单中心对齐（code 固定，可安全同步）
        if existing.name != bt["name"]:
            existing.name = bt["name"]
            await db.flush()
        published = await _get_published_version(db, tenant_id, existing.id)
        if not published:
            latest = await _get_latest_version(db, tenant_id, existing.id)
            if latest and latest.status == "draft":
                await publish(db, tenant_id, existing.id, user.get("sub") or "")
                await db.refresh(existing)
        existing = await sync_builtin_form_fields(db, tenant_id, key, existing, user)
        await _ensure_builtin_form_flow(db, tenant_id, key, existing.id)
        if key == "department_code_base":
            from app.domains.lowcode.dept_code import seed_department_codes_if_empty
            await seed_department_codes_if_empty(db, tenant_id, existing.id, user)
            await db.commit()
        if key == "salesperson_region_map":
            from app.domains.lowcode.salesperson_region import seed_salesperson_region_if_empty
            await seed_salesperson_region_if_empty(db, tenant_id, existing.id, user)
            await db.commit()
        if key == "quote_management":
            from app.domains.organization.pickable_scope_service import ensure_preset_scopes
            await ensure_preset_scopes(db, tenant_id)
            await db.commit()
        await db.commit()
        return existing

    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=tenant_id,
        name=bt["name"], code=key, description=bt.get("description"),
        category=bt.get("category"), icon=bt.get("icon"),
        status="draft", current_version=0, created_by=user.get("sub"),
    )
    db.add(tpl)
    await db.flush()
    from app.domains.lowcode.pickable_scope import strip_spt_scheme_pickable_scopes
    install_defs = strip_spt_scheme_pickable_scopes(tenant_id, bt["field_definitions"])
    db.add(FormTemplateVersion(
        id=generate_uuid(), tenant_id=tenant_id, template_id=tpl.id,
        version_number=1, field_definitions=install_defs,
        layout_definition={}, rule_definitions=bt.get("rule_definitions", []),
        status="draft",
    ))
    await db.commit()
    await publish(db, tenant_id, tpl.id, user.get("sub") or "")
    await db.refresh(tpl)
    await _ensure_builtin_form_flow(db, tenant_id, key, tpl.id)
    if key == "department_code_base":
        from app.domains.lowcode.dept_code import seed_department_codes_if_empty
        await seed_department_codes_if_empty(db, tenant_id, tpl.id, user)
        await db.commit()
    if key == "salesperson_region_map":
        from app.domains.lowcode.salesperson_region import seed_salesperson_region_if_empty
        await seed_salesperson_region_if_empty(db, tenant_id, tpl.id, user)
        await db.commit()
    if key == "quote_management":
        from app.domains.organization.pickable_scope_service import ensure_preset_scopes
        await ensure_preset_scopes(db, tenant_id)
        await db.commit()
    return tpl


async def get_template(db: AsyncSession, tenant_id: str, template_id: str) -> FormTemplate:
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id,
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not tpl:
        raise BusinessException(code=NOT_FOUND, message="表单模板不存在")
    return tpl


async def list_templates(
    db: AsyncSession, tenant_id: str, page_no: int, page_size: int,
    name: str | None = None, published_only: bool = False,
    category: str | None = None,
) -> tuple[list[FormTemplate], int]:
    # 排除实体扩展字段的系统模板(is_system)：它们只用于定义业务实体表单的扩展字段，
    # 由「字段管理」维护，不应作为独立表单出现在表单中心/被独立填报。
    conds = [FormTemplate.tenant_id == tenant_id, FormTemplate.is_deleted == False,  # noqa: E712
             FormTemplate.is_system == False]  # noqa: E712
    if name:
        conds.append(or_(
            FormTemplate.name.ilike(f"%{name}%"),
            FormTemplate.code.ilike(f"%{name}%"),
        ))
    if category:
        conds.append(FormTemplate.category == category)
    if published_only:
        conds.append(FormTemplate.status == "published")

    total = (await db.execute(
        select(func.count()).select_from(FormTemplate).where(*conds)
    )).scalar_one()
    rows = (await db.execute(
        select(FormTemplate).where(*conds)
        .order_by(FormTemplate.sort_order.asc(), FormTemplate.created_at.desc())
        .offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(rows), total


async def update_template(
    db: AsyncSession, tenant_id: str, template_id: str, data: schemas.FormTemplateUpdate
) -> FormTemplate:
    tpl = await get_template(db, tenant_id, template_id)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(tpl, k, v)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def delete_template(db: AsyncSession, tenant_id: str, template_id: str) -> None:
    tpl = await get_template(db, tenant_id, template_id)
    if tpl.is_system:
        raise BusinessException(code=VALIDATION_ERROR, message="系统内置表单不可删除")
    tpl.is_deleted = True
    await db.commit()


# ==================== 版本 / 设计 / 发布 ====================

async def _get_latest_version(
    db: AsyncSession, tenant_id: str, template_id: str
) -> FormTemplateVersion | None:
    return (await db.execute(
        select(FormTemplateVersion).where(
            FormTemplateVersion.tenant_id == tenant_id,
            FormTemplateVersion.template_id == template_id,
        ).order_by(FormTemplateVersion.version_number.desc()).limit(1)
    )).scalar_one_or_none()


async def _get_published_version(
    db: AsyncSession, tenant_id: str, template_id: str
) -> FormTemplateVersion | None:
    return (await db.execute(
        select(FormTemplateVersion).where(
            FormTemplateVersion.tenant_id == tenant_id,
            FormTemplateVersion.template_id == template_id,
            FormTemplateVersion.status == "published",
        ).order_by(FormTemplateVersion.version_number.desc()).limit(1)
    )).scalar_one_or_none()


async def save_design(
    db: AsyncSession, tenant_id: str, template_id: str,
    data: schemas.SaveDesignRequest, user_id: str,
) -> FormTemplateVersion:
    """保存表单设计: 更新现有草稿版本,或基于最新版本新建草稿。"""
    await get_template(db, tenant_id, template_id)
    latest = await _get_latest_version(db, tenant_id, template_id)

    # exclude_unset：避免 FieldDefinition 默认值（如 available_on_create=True）
    # 在「只改 required」的局部保存里写进库，进而 merge 时盖掉目录里的 False
    # （工单「解决方案」等仅编辑可见字段会被误拦新建）。
    new_defs = [fd.model_dump(exclude_unset=True) for fd in data.field_definitions]
    # 系统规则（__sys_*）允许落库作租户覆盖；运行时用 merge_system_rules 与目录默认合并。
    rule_defs = [rd.model_dump(exclude_unset=True) for rd in data.rule_definitions]

    if latest and latest.status == "draft":
        latest.field_definitions = new_defs
        latest.layout_definition = data.layout_definition
        latest.rule_definitions = rule_defs
        await db.commit()
        await db.refresh(latest)
        return latest

    next_version = (latest.version_number + 1) if latest else 1
    version = FormTemplateVersion(
        id=generate_uuid(), tenant_id=tenant_id, template_id=template_id,
        version_number=next_version, field_definitions=new_defs,
        layout_definition=data.layout_definition, rule_definitions=rule_defs,
        status="draft",
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


async def publish(
    db: AsyncSession, tenant_id: str, template_id: str, user_id: str
) -> FormTemplateVersion:
    """发布: 最新草稿版本设为 published,旧 published 设为 deprecated。"""
    tpl = await get_template(db, tenant_id, template_id)
    latest = await _get_latest_version(db, tenant_id, template_id)
    if not latest or latest.status != "draft":
        raise BusinessException(code=BUSINESS_ERROR, message="没有可发布的草稿版本")

    old_published = await _get_published_version(db, tenant_id, template_id)
    if old_published:
        old_published.status = "deprecated"

    latest.status = "published"
    latest.published_at = _now()
    latest.published_by = user_id
    tpl.status = "published"
    tpl.current_version = latest.version_number
    await db.commit()
    await db.refresh(latest)
    # 实体扩展字段模板发布后，清高级搜索的字段定义缓存，使新字段立即可筛选/显示。
    if tpl.is_system and tpl.entity_type:
        from app.common.search import invalidate_custom_fields
        invalidate_custom_fields(tenant_id, tpl.entity_type)
        invalidate_entity_schema_cache(db, tpl.entity_type)  # 同请求内后续读取取到新版本
    return latest


async def get_versions(
    db: AsyncSession, tenant_id: str, template_id: str
) -> list[FormTemplateVersion]:
    rows = (await db.execute(
        select(FormTemplateVersion).where(
            FormTemplateVersion.tenant_id == tenant_id,
            FormTemplateVersion.template_id == template_id,
        ).order_by(FormTemplateVersion.version_number.desc())
    )).scalars().all()
    return list(rows)


async def get_published_version(
    db: AsyncSession, tenant_id: str, template_id: str
) -> FormTemplateVersion:
    v = await _get_published_version(db, tenant_id, template_id)
    if not v:
        raise BusinessException(code=NOT_FOUND, message="该模板尚未发布")
    return v


async def get_design(
    db: AsyncSession, tenant_id: str, template_id: str
) -> FormTemplateVersion | None:
    """设计器加载: 优先最新草稿,否则最新版本(用于继续编辑)。"""
    return await _get_latest_version(db, tenant_id, template_id)


# ==================== 实体扩展字段(统一自定义字段到表单引擎) ====================
# 每个既有业务实体(customer/lead/order/...)的自定义字段 = 一张系统表单模板(is_system, entity_type),
# 用同一套表单设计器设计、同一套 FormRenderer 渲染,值仍存业务表的 custom_fields_json。

async def get_or_create_entity_template(
    db: AsyncSession, tenant_id: str, entity_type: str, user: dict
) -> FormTemplate:
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.entity_type == entity_type,
            FormTemplate.is_system == True,  # noqa: E712
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if tpl:
        return tpl
    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=tenant_id,
        name=f"{entity_type} 扩展字段", code=f"__entity_{entity_type}",
        status="draft", current_version=0, is_system=True, entity_type=entity_type,
        created_by=user.get("sub"),
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def get_entity_schema(db: AsyncSession, tenant_id: str, entity_type: str) -> dict:
    """该实体已发布版本里「原样存下」的字段定义 + 规则；未设计则均为空。

    field_definitions 里混有两类条目：扩展字段，以及原生字段的租户覆盖项(native=True)。
    多数调用方要的是前者，请走 get_entity_fields()；要完整表单 schema 走 get_entity_form_schema()。

    规则(rule_definitions)必须与字段一起返回：条件显隐/条件必填/条件只读都靠它，
    早前只返回 field_definitions，导致设计器里配好的规则在业务页面上一条都不生效。

    结果按 session 缓存：一次写入会经 sanitize / validate / enforce 多条路径反复取同一份
    schema，不缓存的话每个请求要多打好几轮 template+version 查询。session 生命周期 = 请求
    生命周期，且本函数只读已发布版本，因此请求内复用是安全的；设计器发布走的是另一个
    session，不会读到过期缓存。
    """
    cache = db.info.setdefault("_lc_entity_schema", {})
    if entity_type in cache:
        return cache[entity_type]

    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.entity_type == entity_type,
            FormTemplate.is_system == True,  # noqa: E712
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    ver = await _get_published_version(db, tenant_id, tpl.id) if tpl else None
    result = {
        "field_definitions": (ver.field_definitions or []) if ver else [],
        "rule_definitions": (ver.rule_definitions or []) if ver else [],
    }
    cache[entity_type] = result
    return result


def invalidate_entity_schema_cache(db: AsyncSession, entity_type: str | None = None) -> None:
    """发布/保存设计后清掉本 session 的 schema 缓存，避免同一请求内读到旧版本。"""
    cache = db.info.get("_lc_entity_schema")
    if not cache:
        return
    if entity_type is None:
        cache.clear()
    else:
        cache.pop(entity_type, None)


async def get_entity_fields(db: AsyncSession, tenant_id: str, entity_type: str) -> list[dict]:
    """只要「扩展」字段定义的便捷入口(字段级权限裁剪、高级搜索列构建等场景用)。

    刻意剔除原生字段(及其覆盖项)：这两处都按字段 id 去 custom_fields_json 里取值，混入
    原生字段会造出指向不存在 JSON 键的 cf_* 搜索列。
    """
    stored = (await get_entity_schema(db, tenant_id, entity_type))["field_definitions"]
    return [fd for fd in stored if not (isinstance(fd, dict) and fd.get("native"))]


async def get_entity_form_schema(db: AsyncSession, tenant_id: str, entity_type: str) -> dict:
    """业务表单渲染/校验用的完整 schema：原生字段 + 扩展字段 + 规则。

    原生字段由 native_field_catalog 重建后叠加租户覆盖项，因此 id/type 永远可信；
    扩展字段原样取用。规则可同时引用两类字段（跨原生/扩展的条件显隐正是靠这一点）。
    """
    from app.domains.lowcode.native_field_catalog import merge_native_overrides, merge_system_rules

    schema = await get_entity_schema(db, tenant_id, entity_type)
    stored = schema["field_definitions"]
    native = merge_native_overrides(entity_type, stored)
    custom = [fd for fd in stored if not (isinstance(fd, dict) and fd.get("native"))]
    return {
        "native_fields": native,
        "field_definitions": custom,
        # 内置规则（含租户覆盖）排在前面，其后是纯租户规则
        "rule_definitions": merge_system_rules(entity_type, schema["rule_definitions"]),
    }


# ==================== 校验 ====================

def _is_empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def role_field_permissions(field_defs: list[dict], user_roles) -> list[dict]:
    """由 visible_roles/unmask_roles/edit_roles + 当前用户角色推导规则引擎可用的字段权限。

    与前端 FormRenderer.deriveRolePerms 同口径：空/缺省 = 不限制；隐藏 > 脱敏 > 只读。
    """
    from app.domains.lowcode.field_permission import SYSTEM_ROLE
    roles = set(user_roles or [])
    if SYSTEM_ROLE in roles:
        return []  # 系统主体：无用户角色可评，不施加任何字段级限制
    out: list[dict] = []
    for fd in field_defs or []:
        vr = fd.get("visible_roles")
        if vr and not (roles & set(vr)):
            out.append({"fieldId": fd.get("id"), "access": "hidden"})
            continue
        ur = fd.get("unmask_roles")
        if ur and not (roles & set(ur)):
            # 脱敏即隐含只读：看不到明文的人不该覆盖真实值
            out.append({"fieldId": fd.get("id"), "access": "masked"})
            continue
        er = fd.get("edit_roles")
        if er and not (roles & set(er)):
            out.append({"fieldId": fd.get("id"), "access": "readonly"})
    return out


def validate_required(
    field_defs: list[dict], form_data: dict,
    rules: list[dict] | None = None, permissions: list[dict] | None = None,
) -> str | None:
    """服务端必填校验(顶层字段 + 明细子表必填列)。返回首个错误提示或 None。

    传入 rules 后会先算显隐/条件必填再校验：既让条件必填无法被绕过，也避免「字段被规则
    隐藏、前端不校验、后端仍拦」的死锁。语义与前端 RuleEngine 一致（见 rule_engine.py）。
    """
    return validate_required_with_rules(field_defs, form_data, rules, permissions)


def _extract_amount(form_data: dict, field_defs: list[dict]) -> Decimal | None:
    for fd in field_defs or []:
        if fd.get("type") == "amount" and fd.get("is_indexed"):
            value = form_data.get(fd.get("id"))
            if value is not None:
                try:
                    return Decimal(str(value))
                except (InvalidOperation, ValueError, TypeError):
                    pass
    return None


def _pick_business_no(form_data: dict | None, field_defs: list[dict] | None) -> str | None:
    """业务编号：只用流水号类字段，不用设计卡号（二者规则不同）。"""
    data = form_data or {}
    for fid in ("serial_no", "drawing_no", "quote_no", "business_no", "payment_no"):
        v = data.get(fid)
        if v is not None and str(v).strip() != "":
            return str(v).strip()[:64]
    for fd in field_defs or []:
        if not isinstance(fd, dict) or fd.get("type") != "auto_number":
            continue
        fid = fd.get("id")
        if not fid or fid == "design_card_no":
            continue
        lab = str(fd.get("label") or "")
        if "设计卡" in lab:
            continue
        v = data.get(fid)
        if v is not None and str(v).strip() != "":
            return str(v).strip()[:64]
    return None


# ==================== 实例(填报) ====================

async def create_instance(
    db: AsyncSession, tenant_id: str, data: schemas.FormInstanceCreate, user: dict
) -> FormInstance:
    tpl = await get_template(db, tenant_id, data.template_id)
    if tpl.is_system:
        # 实体扩展字段模板只用于业务实体表单的扩展字段，不能作为独立表单填报(否则产生孤立数据)。
        raise BusinessException(code=BUSINESS_ERROR, message="实体扩展字段模板仅用于业务表单，不能独立填报")
    published = await _get_published_version(db, tenant_id, data.template_id)
    if not published:
        raise BusinessException(code=VALIDATION_ERROR, message="该表单模板尚未发布，无法填报")

    field_defs = published.field_definitions or []
    user_name = user.get("real_name") or user.get("username") or ""
    # 字段级权限：丢弃用户对不可编辑/隐藏字段的写入（后端权威边界）
    raw = sanitize_write(data.form_data, None, field_defs, user.get("roles"), is_creator=True)
    form_data = compute_formula_fields(dict(raw or {}), field_defs, user_name)
    from app.domains.lowcode.dept_code import fill_dept_code_in_form_data
    form_data = await fill_dept_code_in_form_data(db, tenant_id, form_data, field_defs, user)

    if not data.as_draft:
        err = validate_required(field_defs, form_data, published.rule_definitions or [],
                                role_field_permissions(field_defs, user.get("roles")))
        if err:
            raise BusinessException(code=VALIDATION_ERROR, message=err)
        form_data = await generate_serials_for_submit(db, tenant_id, data.template_id, field_defs, form_data)

    title = (data.title or "").strip() or None
    if not title or is_weak_form_title(title, tpl.name):
        title = await derive_form_instance_title_resolved(
            db, tenant_id, tpl.name, form_data, field_defs,
        )

    inst = FormInstance(
        id=generate_uuid(), tenant_id=tenant_id,
        template_id=data.template_id, template_version_id=published.id,
        title=title, remark=data.remark,
        status="draft" if data.as_draft else "submitted",
        initiator_id=user.get("sub"), initiator_dept_id=user.get("dept_id"),
        amount=_extract_amount(form_data, field_defs),
        business_no=_pick_business_no(form_data, field_defs),
        form_data=form_data, field_definitions=field_defs,
        created_by=user.get("sub"),
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)

    # 表单绑定了已发布流程 → 提交即起审批(草稿不触发)。流程状态回写到实例(running/completed/rejected)。
    if not data.as_draft:
        from app.domains.lowcode import workflow_service as wsvc
        pinst = await wsvc.maybe_start_for_form(db, tenant_id, data.template_id, inst, user, form_data)
        if pinst is not None:
            inst.status = pinst.status
            inst.process_instance_id = pinst.id
            await db.commit()
            await db.refresh(inst)
    return inst


async def get_instance(db: AsyncSession, tenant_id: str, instance_id: str, user: dict | None = None) -> dict:
    inst = (await db.execute(
        select(FormInstance).where(
            FormInstance.id == instance_id,
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="表单数据不存在")

    field_defs = inst.field_definitions or []
    rule_defs: list = []
    # 草稿跟最新已发布 schema（必填/显隐），避免旧快照 required 与当前规则打架
    if inst.status == "draft":
        published = await _get_published_version(db, tenant_id, inst.template_id)
        if published:
            field_defs = published.field_definitions or field_defs
            rule_defs = published.rule_definitions or []
        else:
            version = await db.get(FormTemplateVersion, inst.template_version_id)
            if version:
                if not field_defs:
                    field_defs = version.field_definitions or []
                rule_defs = version.rule_definitions or []
    else:
        version = await db.get(FormTemplateVersion, inst.template_version_id)
        if not version:
            version = await _get_published_version(db, tenant_id, inst.template_id)
        if version:
            if not field_defs:
                field_defs = version.field_definitions or []
            rule_defs = version.rule_definitions or []

    out = schemas.FormInstanceOut.model_validate(inst).model_dump()
    # 字段级权限：按查看者角色剔除隐藏字段(定义+值)，不可编辑字段标记 readonly；
    # 附件 download_roles 以已发布模板为准（避免提交快照缺配置被绕过）。
    is_creator = bool(user and inst.created_by and user.get("sub") == inst.created_by)
    published_acl = await _get_published_version(db, tenant_id, inst.template_id)
    if published_acl and published_acl.field_definitions:
        field_defs = _overlay_download_acl(field_defs, published_acl.field_definitions)
    field_defs, out["form_data"] = filter_read(
        field_defs, out.get("form_data"), (user or {}).get("roles"),
        is_creator=is_creator,
    )
    out["field_definitions"] = field_defs
    out["rule_definitions"] = rule_defs
    return out


def _overlay_download_acl(snapshot: list, published: list) -> list:
    """把已发布模板上的 download_roles 叠到实例字段快照上。"""
    from app.domains.lowcode.field_permission import _overlay_download_roles
    return _overlay_download_roles(snapshot, published)

_FIELD_ID_RE = re.compile(r"^[a-zA-Z0-9_]{1,64}$")
_FILTER_OPS = frozenset({
    "eq", "ne", "contains", "not_contains",
    "in", "between", "gt", "gte", "lt", "lte",
    "before", "after", "is_empty", "is_not_empty",
})
_EMPTY_OPS = frozenset({"is_empty", "is_not_empty"})
_MAX_FILTER_RULES = 10


def _parse_filters_payload(filters: list | dict | str | None) -> tuple[str, list]:
    """解析 filters：支持旧版数组，或 {match, rules}。返回 (match, raw_rules)。"""
    raw = filters
    if isinstance(raw, str):
        if not raw.strip():
            return "all", []
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return "all", []
    if isinstance(raw, dict):
        match = raw.get("match") if raw.get("match") in ("all", "any") else "all"
        rules = raw.get("rules") if isinstance(raw.get("rules"), list) else []
        return str(match), rules
    if isinstance(raw, list):
        return "all", raw
    return "all", []


def _normalize_instance_filters(filters: list | dict | str | None) -> tuple[str, list[dict]]:
    """解析 list/export 的 filters：最多 10 条规则。非法项静默丢弃。"""
    match, rules = _parse_filters_payload(filters)
    out: list[dict] = []
    for item in rules[:_MAX_FILTER_RULES]:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        op = str(item.get("op") or "contains").strip()
        value = item.get("value")
        if not isinstance(field, str) or not _FIELD_ID_RE.match(field):
            continue
        if op not in _FILTER_OPS:
            continue
        if op not in _EMPTY_OPS:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, list) and not value:
                continue
        out.append({"field": field, "op": op, "value": value})
    return match, out


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_REF_FILTER_TYPES = frozenset({
    "department", "department_multi", "person", "person_multi",
    "contract", "customer", "project",
})


def _form_data_filter_clause(rule: dict):
    """单条规则 → SQL 条件（form_data->>field 文本语义）。"""
    field = rule["field"]
    op = rule["op"]
    value = rule.get("value")
    txt = FormInstance.form_data.op("->>")(field)
    empty = or_(txt.is_(None), txt == "", txt == "null", txt == "[]", txt == "{}")

    if op == "is_empty":
        return empty
    if op == "is_not_empty":
        return not_(empty)
    if op == "eq":
        return txt == str(value)
    if op == "ne":
        return or_(txt.is_(None), txt != str(value))
    if op == "contains":
        return txt.ilike(f"%{value}%")
    if op == "not_contains":
        return or_(txt.is_(None), not_(txt.ilike(f"%{value}%")))
    if op == "in":
        vals = value if isinstance(value, list) else [value]
        parts = [txt == str(v) for v in vals if v is not None and str(v) != ""]
        # 人员/对象字段可能以 JSON 文本存储，额外做包含匹配
        parts += [txt.ilike(f"%{v}%") for v in vals if v is not None and str(v) != ""]
        return or_(*parts) if parts else False
    if op == "between":
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return True
        a, b = value[0], value[1]
        if a is None or b is None or a == "":
            return True
        end = str(b)
        # 仅日期时扩到当天末，避免漏掉带时间的值
        if len(end) == 10 and end[4] == "-" and end[7] == "-":
            end = end + "T23:59:59"
        return and_(txt >= str(a), txt <= end)
    if op in ("gt", "after"):
        return and_(txt.isnot(None), txt > str(value))
    if op == "gte":
        return and_(txt.isnot(None), txt >= str(value))
    if op in ("lt", "before"):
        return and_(txt.isnot(None), txt < str(value))
    if op == "lte":
        return and_(txt.isnot(None), txt <= str(value))
    return txt.ilike(f"%{value}%")


def _form_data_ids_match_clause(field: str, ids: list[str]):
    """form_data 字段命中任一 id（纯字符串 / {id} / JSON 文本含 id）。"""
    parts = []
    txt = FormInstance.form_data.op("->>")(field)
    obj_id = FormInstance.form_data.op("->")(field).op("->>")("id")
    for raw in ids:
        sid = str(raw or "").strip()
        if not sid:
            continue
        parts.append(txt == sid)
        parts.append(obj_id == sid)
        parts.append(txt.ilike(f"%{sid}%"))
    return or_(*parts) if parts else False


def _form_data_person_in_owner_ids(field: str, owner_ids: list[str]):
    """form_data 人员字段命中数据范围（字符串 id / {id} / JSON 文本含 id）。"""
    return _form_data_ids_match_clause(field, owner_ids or [])


async def _template_field_type_map(
    db: AsyncSession, tenant_id: str, template_id: str,
) -> dict[str, str]:
    ver = await _get_published_version(db, tenant_id, template_id)
    if not ver:
        ver = await _get_latest_version(db, tenant_id, template_id)
    out: dict[str, str] = {}
    for f in (ver.field_definitions if ver else []) or []:
        if isinstance(f, dict) and f.get("id") and f.get("type"):
            out[str(f["id"])] = str(f["type"])
    return out


async def _lookup_ref_ids_by_name(
    db: AsyncSession, tenant_id: str, *, kind: str, value: str, exact: bool,
) -> list[str]:
    """按显示名解析引用字段 id；value 已是 UUID 则原样返回。

    合同字段列表展示图纸编号（无则合同号），筛选需按 contract_no / drawing_no 反查。
    """
    from sqlalchemy import text as sql_text

    needle = (value or "").strip()
    if not needle:
        return []
    if _UUID_RE.match(needle):
        return [needle]

    like = needle if exact else f"%{needle}%"
    op = "=" if exact else "ILIKE"

    if kind.startswith("department"):
        rows = (await db.execute(sql_text(
            f"SELECT id FROM departments WHERE tenant_id = :t AND name {op} :n LIMIT 200"
        ), {"t": tenant_id, "n": like})).fetchall()
        return [str(r[0]) for r in rows]
    if kind.startswith("person"):
        rows = (await db.execute(sql_text(
            f"SELECT id FROM users WHERE tenant_id = :t "
            f"AND (real_name {op} :n OR username {op} :n) LIMIT 200"
        ), {"t": tenant_id, "n": like})).fetchall()
        return [str(r[0]) for r in rows]
    if kind == "contract":
        rows = (await db.execute(sql_text(
            f"SELECT id FROM contracts WHERE tenant_id = :t "
            f"AND (contract_no {op} :n OR drawing_no {op} :n "
            f"OR peer_contract_no {op} :n) LIMIT 200"
        ), {"t": tenant_id, "n": like})).fetchall()
        return [str(r[0]) for r in rows]
    if kind == "customer":
        rows = (await db.execute(sql_text(
            f"SELECT id FROM customers WHERE tenant_id = :t "
            f"AND (name {op} :n OR COALESCE(short_name,'') {op} :n "
            f"OR COALESCE(customer_code,'') {op} :n) LIMIT 200"
        ), {"t": tenant_id, "n": like})).fetchall()
        return [str(r[0]) for r in rows]
    if kind == "project":
        rows = (await db.execute(sql_text(
            f"SELECT id FROM opportunity_projects WHERE tenant_id = :t "
            f"AND COALESCE(is_deleted, false) = false "
            f"AND (name {op} :n OR project_code {op} :n) LIMIT 200"
        ), {"t": tenant_id, "n": like})).fetchall()
        return [str(r[0]) for r in rows]
    return []


def _flatten_filter_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for v in value:
            out.extend(_flatten_filter_values(v))
        return out
    s = str(value).strip()
    return [s] if s else []


async def _form_data_filter_clause_resolved(
    db: AsyncSession, tenant_id: str, rule: dict, field_type: str | None,
):
    """部门/人员等引用字段：按名称解析成 id 再匹配（含「包含 砂石」）。"""
    op = rule["op"]
    field = rule["field"]
    ftype = (field_type or "").strip()
    if ftype not in _REF_FILTER_TYPES or op in _EMPTY_OPS:
        return _form_data_filter_clause(rule)

    values = _flatten_filter_values(rule.get("value"))
    if not values:
        return False

    # contains / not_contains：名称模糊；eq / ne / in：精确名或 UUID
    exact = op in ("eq", "ne", "in")
    resolved: list[str] = []
    for v in values:
        resolved.extend(
            await _lookup_ref_ids_by_name(
                db, tenant_id, kind=ftype, value=v, exact=exact,
            )
        )

    seen: set[str] = set()
    ids: list[str] = []
    for i in resolved:
        if i not in seen:
            seen.add(i)
            ids.append(i)

    txt = FormInstance.form_data.op("->>")(field)
    id_hit = _form_data_ids_match_clause(field, ids) if ids else False
    # 名称也可能嵌在 JSON 文本里（{id,name}），保留原文包含
    name_hit = or_(*[txt.ilike(f"%{v}%") for v in values]) if values else False

    if op == "contains":
        return or_(id_hit, name_hit)
    if op == "not_contains":
        miss = not_(id_hit) if ids else True
        return and_(miss, or_(txt.is_(None), not_(name_hit)))
    if op == "eq":
        return or_(id_hit, name_hit)
    if op == "ne":
        miss = not_(id_hit) if ids else True
        return and_(miss, or_(txt.is_(None), not_(name_hit)))
    if op == "in":
        return or_(id_hit, name_hit)
    return _form_data_filter_clause(rule)


def _instance_list_conds(
    tenant_id: str, template_id: str,
    keyword: str | None = None, status: str | None = None,
    owner_ids: list[str] | None = None,
    filters: list | dict | str | None = None,
    owner_person_fields: list[str] | None = None,
    filter_clauses: list | None = None,
    template_code: str | None = None,
    form_dept_scope_ids: list[str] | None = None,
    form_dept_name_literals: list[str] | None = None,
) -> list:
    conds = [
        FormInstance.tenant_id == tenant_id,
        FormInstance.template_id == template_id,
        FormInstance.is_deleted == False,  # noqa: E712
    ]
    if keyword:
        like = f"%{keyword}%"
        conds.append(or_(
            FormInstance.title.ilike(like),
            FormInstance.business_no.ilike(like),
            cast(FormInstance.form_data, String).ilike(like),
        ))
    if status:
        conds.append(FormInstance.status == status)
    if owner_ids is not None:  # 数据范围: 发起人；开票/核价等可并入业务员/部门字段
        owner_clause = FormInstance.initiator_id.in_(owner_ids or ["__none__"])
        for pf in owner_person_fields or []:
            owner_clause = or_(owner_clause, _form_data_person_in_owner_ids(pf, owner_ids or []))
        code = template_code or ""
        if form_dept_scope_ids:
            for df in _FORM_DEPT_FIELDS_BY_TEMPLATE.get(code, []):
                owner_clause = or_(
                    owner_clause,
                    _form_data_ids_match_clause(df, form_dept_scope_ids),
                )
        if form_dept_name_literals:
            for nf in _FORM_DEPT_NAME_FIELDS_BY_TEMPLATE.get(code, []):
                owner_clause = or_(
                    owner_clause,
                    _form_data_text_in_literals(nf, form_dept_name_literals),
                )
        conds.append(owner_clause)
    if filter_clauses is not None:
        if filter_clauses:
            # match 已在外层折叠进 filter_clauses 单条 or/and
            conds.append(filter_clauses[0] if len(filter_clauses) == 1 else and_(*filter_clauses))
        return conds
    match, rules = _normalize_instance_filters(filters)
    if rules:
        clauses = [_form_data_filter_clause(r) for r in rules]
        conds.append(or_(*clauses) if match == "any" else and_(*clauses))
    return conds


async def _instance_list_filter_bundle(
    db: AsyncSession, tenant_id: str, template_id: str,
    filters: list | dict | str | None,
) -> list | None:
    """解析 filters；引用字段按名称解析。返回 [combined_clause] 或 None（无筛选）。"""
    match, rules = _normalize_instance_filters(filters)
    if not rules:
        return None
    field_types = await _template_field_type_map(db, tenant_id, template_id)
    clauses = [
        await _form_data_filter_clause_resolved(
            db, tenant_id, r, field_types.get(r["field"]),
        )
        for r in rules
    ]
    combined = or_(*clauses) if match == "any" else and_(*clauses)
    return [combined]


# 列表/导出：除发起人外，按表单人员/部门字段纳入数据范围
_OWNER_PERSON_FIELD_BY_TEMPLATE = {
    "invoice_application": "sales_person",
    "quote_management": "sales_person",
}

_OWNER_PERSON_FIELDS_BY_TEMPLATE: dict[str, list[str]] = {
    "invoice_application": ["sales_person"],
    "quote_management": ["sales_person"],
    "pricing_checklist_hjqd": [
        "install_applicant", "req_applicant", "cs_applicant",
        "coop_applicant", "coop_order_person",
    ],
}

# 部门档：form_data 部门控件 id 落在组织/负责业务部门子树内即可见（对齐线索 department_id）
_FORM_DEPT_FIELDS_BY_TEMPLATE: dict[str, list[str]] = {
    "pricing_checklist_hjqd": [
        "install_department", "req_department", "cs_department", "coop_order_dept",
    ],
}

# 部门档：业务部门等文本字段按部门名称匹配
_FORM_DEPT_NAME_FIELDS_BY_TEMPLATE: dict[str, list[str]] = {
    "pricing_checklist_hjqd": ["business_dept"],
}


def _form_data_text_in_literals(field: str, literals: list[str]):
    parts = []
    txt = FormInstance.form_data.op("->>")(field)
    for lit in literals:
        s = str(lit or "").strip()
        if not s:
            continue
        parts.append(txt == s)
        parts.append(txt.ilike(f"%{s}%"))
    return or_(*parts) if parts else False


async def _template_code_for(db: AsyncSession, tenant_id: str, template_id: str) -> str | None:
    return (await db.execute(
        select(FormTemplate.code).where(
            FormTemplate.id == template_id,
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()


async def _form_list_scope_extras(
    db: AsyncSession,
    tenant_id: str,
    user: dict | None,
    template_code: str | None,
    owner_ids: list[str] | None,
) -> tuple[list[str], list[str] | None, list[str] | None]:
    """部门档表单列表：除发起人/业务员外，按单据部门字段与负责业务部门匹配。"""
    if owner_ids is None or not template_code or not user:
        return [], None, None
    person_fields = list(_OWNER_PERSON_FIELDS_BY_TEMPLATE.get(template_code) or [])
    dept_fields = _FORM_DEPT_FIELDS_BY_TEMPLATE.get(template_code) or []
    name_fields = _FORM_DEPT_NAME_FIELDS_BY_TEMPLATE.get(template_code) or []
    if not dept_fields and not name_fields:
        return person_fields, None, None

    from app.common.data_scope import managed_department_ids, org_department_subtree_ids

    uid = user.get("sub")
    org = await org_department_subtree_ids(db, tenant_id, uid)
    managed = await managed_department_ids(db, tenant_id, uid)
    dept_ids = list({*org, *managed})
    if not dept_ids:
        return person_fields, None, None

    name_literals: list[str] = []
    if name_fields:
        from app.domains.organization.models import Department

        names = list((await db.execute(
            select(Department.name).where(
                Department.tenant_id == tenant_id,
                Department.id.in_(dept_ids),
            )
        )).scalars().all())
        name_literals = [str(n).strip() for n in names if n and str(n).strip()]

    return (
        person_fields,
        dept_ids if dept_fields else None,
        name_literals if name_fields and name_literals else None,
    )


async def _owner_person_fields_for_template(
    db: AsyncSession, tenant_id: str, template_id: str,
) -> list[str]:
    code = await _template_code_for(db, tenant_id, template_id)
    if not code:
        return []
    fields = list(_OWNER_PERSON_FIELDS_BY_TEMPLATE.get(code) or [])
    if not fields:
        single = _OWNER_PERSON_FIELD_BY_TEMPLATE.get(code)
        if single:
            fields = [single]
    return fields


async def _owner_person_field_for_template(
    db: AsyncSession, tenant_id: str, template_id: str,
) -> str | None:
    fields = await _owner_person_fields_for_template(db, tenant_id, template_id)
    return fields[0] if fields else None


async def list_instances(
    db: AsyncSession, tenant_id: str, template_id: str,
    page_no: int, page_size: int,
    keyword: str | None = None, status: str | None = None,
    owner_ids: list[str] | None = None,
    filters: list | dict | str | None = None,
    user: dict | None = None,
) -> tuple[list[FormInstance], int]:
    template_code = await _template_code_for(db, tenant_id, template_id)
    owner_person_fields: list[str] = []
    form_dept_scope_ids: list[str] | None = None
    form_dept_name_literals: list[str] | None = None
    if owner_ids is not None:
        owner_person_fields, form_dept_scope_ids, form_dept_name_literals = (
            await _form_list_scope_extras(db, tenant_id, user, template_code, owner_ids)
        )
        if not owner_person_fields:
            owner_person_fields = await _owner_person_fields_for_template(
                db, tenant_id, template_id,
            )
    filter_bundle = await _instance_list_filter_bundle(db, tenant_id, template_id, filters)
    conds = _instance_list_conds(
        tenant_id, template_id, keyword=keyword, status=status,
        owner_ids=owner_ids, filters=None if filter_bundle is not None else filters,
        owner_person_fields=owner_person_fields,
        filter_clauses=filter_bundle,
        template_code=template_code,
        form_dept_scope_ids=form_dept_scope_ids,
        form_dept_name_literals=form_dept_name_literals,
    )

    total = (await db.execute(
        select(func.count()).select_from(FormInstance).where(*conds)
    )).scalar_one()
    rows = (await db.execute(
        select(FormInstance).where(*conds)
        .order_by(FormInstance.created_at.desc())
        .offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(rows), total


async def export_instances(
    db: AsyncSession, tenant_id: str, template_id: str,
    keyword: str | None = None, status: str | None = None,
    owner_ids: list[str] | None = None, limit: int = 10000,
    filters: list | dict | str | None = None,
    user: dict | None = None,
) -> tuple[FormTemplate | None, list[dict], list[FormInstance]]:
    """导出表单数据: 返回(模板, 列定义 field_defs, 数据行)。
    列定义优先取已发布版本,否则最新版本(草稿态也可导出)。"""
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id, FormTemplate.tenant_id == tenant_id,
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    ver = await _get_published_version(db, tenant_id, template_id)
    if not ver:
        ver = await _get_latest_version(db, tenant_id, template_id)
    field_defs = (ver.field_definitions if ver else []) or []

    template_code = (tpl.code if tpl else None) or await _template_code_for(
        db, tenant_id, template_id,
    )
    owner_person_fields: list[str] = []
    form_dept_scope_ids: list[str] | None = None
    form_dept_name_literals: list[str] | None = None
    if owner_ids is not None:
        owner_person_fields, form_dept_scope_ids, form_dept_name_literals = (
            await _form_list_scope_extras(db, tenant_id, user, template_code, owner_ids)
        )
        if not owner_person_fields:
            owner_person_fields = await _owner_person_fields_for_template(
                db, tenant_id, template_id,
            )
    filter_bundle = await _instance_list_filter_bundle(db, tenant_id, template_id, filters)
    conds = _instance_list_conds(
        tenant_id, template_id, keyword=keyword, status=status,
        owner_ids=owner_ids, filters=None if filter_bundle is not None else filters,
        owner_person_fields=owner_person_fields,
        filter_clauses=filter_bundle,
        template_code=template_code,
        form_dept_scope_ids=form_dept_scope_ids,
        form_dept_name_literals=form_dept_name_literals,
    )
    rows = (await db.execute(
        select(FormInstance).where(*conds)
        .order_by(FormInstance.created_at.desc())
        .limit(max(1, min(int(limit or 10000), 50000)))
    )).scalars().all()
    return tpl, field_defs, list(rows)


async def update_instance(
    db: AsyncSession, tenant_id: str, instance_id: str,
    data: schemas.FormInstanceUpdate, user: dict,
) -> FormInstance:
    inst = (await db.execute(
        select(FormInstance).where(
            FormInstance.id == instance_id,
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="表单数据不存在")

    if data.title is not None:
        inst.title = data.title
    if data.remark is not None:
        inst.remark = data.remark
    if data.form_data is not None:
        from app.domains.lowcode.edit_lock import assert_form_instance_editable
        await assert_form_instance_editable(db, tenant_id, inst.id, inst.status)
        version = await db.get(FormTemplateVersion, inst.template_version_id)
        field_defs = (version.field_definitions if version else inst.field_definitions) or []
        user_name = user.get("real_name") or user.get("username") or ""
        # 字段级权限：不可编辑字段保留原值，忽略用户改动（后端权威边界）
        raw = sanitize_write(
            data.form_data, inst.form_data, field_defs, user.get("roles"),
            is_creator=bool(inst.created_by and user.get("sub") == inst.created_by),
        )
        form_data = compute_formula_fields(dict(raw), field_defs, user_name)
        from app.domains.lowcode.dept_code import fill_dept_code_in_form_data
        form_data = await fill_dept_code_in_form_data(db, tenant_id, form_data, field_defs, user)
        if inst.status != "draft":
            err = validate_required(field_defs, form_data,
                                    (version.rule_definitions if version else []) or [],
                                    role_field_permissions(field_defs, user.get("roles")))
            if err:
                raise BusinessException(code=VALIDATION_ERROR, message=err)
        inst.form_data = form_data
        inst.amount = _extract_amount(form_data, field_defs)
        biz = _pick_business_no(form_data, field_defs)
        if biz:
            inst.business_no = biz

    await db.commit()
    await db.refresh(inst)
    return inst


async def submit_instance(
    db: AsyncSession, tenant_id: str, instance_id: str,
    data: schemas.FormInstanceSubmit, user: dict,
) -> FormInstance:
    """草稿 → 正式提交：校验必填、取流水号、启动绑定流程。"""
    inst = (await db.execute(
        select(FormInstance).where(
            FormInstance.id == instance_id,
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="表单数据不存在")
    if inst.status not in ("draft", "rejected"):
        raise BusinessException(code=VALIDATION_ERROR, message="仅草稿或已驳回可提交审批")

    # 提交时按最新已发布版本校验并定稿，与设计器当前规则对齐
    published = await _get_published_version(db, tenant_id, inst.template_id)
    version = published or await db.get(FormTemplateVersion, inst.template_version_id)
    field_defs = (version.field_definitions if version else inst.field_definitions) or []
    rule_defs = (version.rule_definitions if version else []) or []
    user_name = user.get("real_name") or user.get("username") or ""

    raw_in = data.form_data if data.form_data is not None else (inst.form_data or {})
    raw = sanitize_write(
        raw_in, inst.form_data, field_defs, user.get("roles"),
        is_creator=bool(inst.created_by and user.get("sub") == inst.created_by),
    )
    form_data = compute_formula_fields(dict(raw or {}), field_defs, user_name)
    from app.domains.lowcode.dept_code import fill_dept_code_in_form_data
    form_data = await fill_dept_code_in_form_data(db, tenant_id, form_data, field_defs, user)

    err = validate_required(field_defs, form_data, rule_defs,
                            role_field_permissions(field_defs, user.get("roles")))
    if err:
        raise BusinessException(code=VALIDATION_ERROR, message=err)
    form_data = await generate_serials_for_submit(db, tenant_id, inst.template_id, field_defs, form_data)

    tpl = await get_template(db, tenant_id, inst.template_id)
    # 报价等：流水号生成后再拼「单号 · 客户 · 业务员」，覆盖草稿阶段弱/不完整标题
    if _should_use_composite_title(tpl.name, form_data, field_defs):
        inst.title = await derive_form_instance_title_resolved(
            db, tenant_id, tpl.name, form_data, field_defs,
        )
    elif data.title is not None:
        title = (data.title or "").strip() or None
        if title:
            inst.title = title
        elif not inst.title or is_weak_form_title(inst.title, tpl.name):
            inst.title = await derive_form_instance_title_resolved(
                db, tenant_id, tpl.name, form_data, field_defs,
            )
    elif not inst.title or is_weak_form_title(inst.title, tpl.name):
        inst.title = await derive_form_instance_title_resolved(
            db, tenant_id, tpl.name, form_data, field_defs,
        )

    inst.form_data = form_data
    inst.amount = _extract_amount(form_data, field_defs)
    biz = _pick_business_no(form_data, field_defs)
    if biz:
        inst.business_no = biz
    inst.field_definitions = field_defs
    if published:
        inst.template_version_id = published.id
    inst.status = "submitted"
    await db.commit()
    await db.refresh(inst)

    from app.domains.lowcode import workflow_service as wsvc
    pinst = await wsvc.maybe_start_for_form(db, tenant_id, inst.template_id, inst, user, form_data)
    if pinst is not None:
        inst.status = pinst.status
        inst.process_instance_id = pinst.id
        await db.commit()
        await db.refresh(inst)
    return inst


async def delete_instance(db: AsyncSession, tenant_id: str, instance_id: str, user: dict) -> None:
    inst = (await db.execute(
        select(FormInstance).where(
            FormInstance.id == instance_id,
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="表单数据不存在")
    from app.domains.lowcode.workflow_service import (
        STARTED_FLOW_DELETE_MSG, assert_no_started_process,
    )
    if inst.process_instance_id:
        raise BusinessException(code=BUSINESS_ERROR, message=STARTED_FLOW_DELETE_MSG)
    await assert_no_started_process(db, tenant_id, form_instance_id=inst.id)
    inst.is_deleted = True
    inst.deleted_at = _now()
    inst.deleted_by = user.get("sub")
    await db.commit()
