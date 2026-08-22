import logging
from datetime import datetime, timezone, date as date_type

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR, DUPLICATE_ENTRY
from app.domains.contract.models import Contract, ContractVersion
from app.domains.contract.schemas import ContractCreate, ContractUpdate, ContractVersionUpdate
from app.domains.audit.service import log_action

logger = logging.getLogger("spt_crm.contract")


async def _alloc_draft_contract_no(db: AsyncSession, tenant_id: str) -> str:
    """生成唯一 DRAFT- 占位合同号。"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    base = f"DRAFT-{ts}"
    suffix = 0
    while True:
        candidate = base if suffix == 0 else f"{base}-{suffix}"
        exists = (await db.execute(
            select(Contract.id).where(
                Contract.tenant_id == tenant_id,
                Contract.contract_no == candidate,
            ).limit(1)
        )).scalar_one_or_none()
        if not exists:
            return candidate
        suffix += 1


async def _resolve_create_contract_no(
    db: AsyncSession, tenant_id: str, requested: str | None,
    *, allow_draft: bool = False,
) -> str:
    """合同号由业务手填；草稿未填时可生成 DRAFT- 占位号。已填则无论草稿/提交均校验唯一并提示。"""
    no = (requested or "").strip()
    if not no:
        if allow_draft:
            return await _alloc_draft_contract_no(db, tenant_id)
        raise BusinessException(code=BUSINESS_ERROR, message="请填写合同号")
    exists = (await db.execute(
        select(Contract.id).where(
            Contract.tenant_id == tenant_id,
            Contract.contract_no == no,
        ).limit(1)
    )).scalar_one_or_none()
    if exists:
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"合同号「{no}」已存在，请更换后再保存")
    return no


def normalize_number_attr(raw: str | None) -> str:
    """编号属性：仅 WMGF / SY（对齐合同图纸对应表）。"""
    s = str(raw or "").strip().upper()
    return s if s in ("WMGF", "SY") else "WMGF"


def drawing_no_apply_date_today() -> date_type:
    """图纸编号年月/年段用「取号当天」，与订货日无关。"""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai")).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _coerce_drawing_apply_date(apply_date: str | date_type | None) -> str:
    """取号用日期：显式传入则用；否则取号当天（不再回落到订货日）。"""
    if isinstance(apply_date, date_type):
        return apply_date.isoformat()
    s = str(apply_date).strip() if apply_date else ""
    return s or drawing_no_apply_date_today().isoformat()


def drawing_no_matches_attr(drawing_no: str | None, number_attr: str | None) -> bool:
    no = (drawing_no or "").strip().upper()
    attr = normalize_number_attr(number_attr)
    return bool(no) and no.startswith(attr)


async def _resolve_create_drawing_no(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    requested: str | None,
    *,
    apply_date: str | date_type | None = None,
    number_attr: str | None = None,
    trust_requested: bool = False,
    allow_empty: bool = False,
) -> str:
    """图纸编号：须从合同图纸对应表选用；不再按 WMGF/SY 规则自动生成。

    trust_requested=True（开放平台）：仍校验唯一，可不强制对应表存在。
    allow_empty=True（存草稿）：允许暂不选号。
    """
    from app.domains.lowcode import service as lc_svc
    from app.domains.lowcode.drawing_no_pool import (
        drawing_no_exists_in_map,
        is_drawing_no_taken_by_contract,
    )

    attr = normalize_number_attr(number_attr)
    no = (requested or "").strip()
    if not no:
        if allow_empty:
            return ""
        raise BusinessException(
            code=BUSINESS_ERROR,
            message="请从合同图纸对应表选择图纸编号",
        )
    if not drawing_no_matches_attr(no, attr):
        # 前缀与编号属性不一致时，按号前缀纠正属性（前端选号后会同步）
        if no.upper().startswith("SY"):
            attr = "SY"
        elif no.upper().startswith("WMGF"):
            attr = "WMGF"

    tpl = await lc_svc.ensure_builtin_form(db, tenant_id, "contract_drawing_map", user)
    if not trust_requested:
        if not await drawing_no_exists_in_map(db, tenant_id, no, map_template_id=tpl.id):
            raise BusinessException(
                code=BUSINESS_ERROR,
                message=f"图纸编号「{no}」不在合同图纸对应表中，请从对应表选择",
            )
    if await is_drawing_no_taken_by_contract(db, tenant_id, no):
        raise BusinessException(
            code=DUPLICATE_ENTRY,
            message=f"图纸编号「{no}」已用于其他合同登记，请更换",
        )
    return no


# 保留 peek/allocate 供开放平台或运维脚本；合同登记 UI 不再调用自动取号
async def peek_create_drawing_no(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    *,
    apply_date: str | date_type | None = None,
    number_attr: str | None = None,
    consume: bool = False,
) -> str:
    """预览/生成合同登记图纸编号（与合同图纸对应表同规则；WMGF 月序 / SY 年序）。

    apply_date 为取号日（写入编号中的年月/年段），默认今天；与订货日无关。
    """
    from app.domains.lowcode import service as lc_svc
    from app.domains.lowcode.builtin_templates import get_builtin
    from app.domains.lowcode.drawing_no_pool import (
        is_drawing_no_taken,
        peek_drawing_no_skipping_taken,
    )
    from app.domains.lowcode.serial_number import generate_serial_value

    tpl = await lc_svc.ensure_builtin_form(db, tenant_id, "contract_drawing_map", user)
    bt = get_builtin("contract_drawing_map") or {}
    field_defs = list(bt.get("field_definitions") or [])
    drawing_fd = next((f for f in field_defs if f.get("id") == "drawing_no"), None)
    if not drawing_fd:
        raise BusinessException(code=BUSINESS_ERROR, message="图纸编号规则未配置")

    apply_s = _coerce_drawing_apply_date(apply_date)

    form_data = {"number_attr": normalize_number_attr(number_attr), "apply_date": apply_s}
    if consume:
        # 正式取号：跳过合同登记 + 图纸对应表已占用
        last = ""
        for _ in range(50):
            last = await generate_serial_value(
                db, tenant_id, tpl.id, drawing_fd, form_data, field_defs,
            )
            if not await is_drawing_no_taken(db, tenant_id, last, map_template_id=tpl.id):
                return last
        raise BusinessException(code=BUSINESS_ERROR, message="无法分配唯一图纸编号，请稍后重试")
    return await peek_drawing_no_skipping_taken(
        db, tenant_id, tpl.id, drawing_fd, form_data, field_defs,
        map_template_id=tpl.id,
    )


async def allocate_create_drawing_no(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    *,
    current: str | None = None,
    apply_date: str | date_type | None = None,
    number_attr: str | None = None,
) -> str:
    """新建合同登记「重新取号」：当前号仍可用则保留，否则占号并跳过已占用。"""
    from app.domains.lowcode import service as lc_svc
    from app.domains.lowcode.builtin_templates import get_builtin
    from app.domains.lowcode.drawing_no_pool import is_drawing_no_taken
    from app.domains.lowcode.serial_number import allocate_unique_serials

    tpl = await lc_svc.ensure_builtin_form(db, tenant_id, "contract_drawing_map", user)
    bt = get_builtin("contract_drawing_map") or {}
    field_defs = list(bt.get("field_definitions") or [])
    drawing_fd = next((f for f in field_defs if f.get("id") == "drawing_no"), None)
    if not drawing_fd:
        raise BusinessException(code=BUSINESS_ERROR, message="图纸编号规则未配置")

    apply_s = _coerce_drawing_apply_date(apply_date)

    attr = normalize_number_attr(number_attr)
    cur = (current or "").strip()
    # 切换编号属性后旧号前缀不匹配，必须重新取号
    if cur and not drawing_no_matches_attr(cur, attr):
        cur = ""
    form_data: dict = {"number_attr": attr, "apply_date": apply_s}
    if cur:
        form_data["drawing_no"] = cur

    async def is_taken(_fid: str, value: str) -> bool:
        return await is_drawing_no_taken(db, tenant_id, value, map_template_id=tpl.id)

    try:
        out = await allocate_unique_serials(
            db, tenant_id, tpl.id, field_defs, form_data,
            field_ids=["drawing_no"],
            is_taken=is_taken,
        )
    except ValueError as e:
        raise BusinessException(code=BUSINESS_ERROR, message=str(e)) from e
    return out.get("drawing_no") or ""


async def _lookup_map_contract_no(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    drawing_no: str,
) -> str:
    """按图纸编号取合同图纸对应表中的合同号。"""
    from app.domains.lowcode import service as lc_svc
    from app.domains.lowcode.models import FormInstance

    no = (drawing_no or "").strip()
    if not no:
        return ""
    tpl = await lc_svc.ensure_builtin_form(db, tenant_id, "contract_drawing_map", user)
    row = (
        await db.execute(
            select(FormInstance.form_data).where(
                FormInstance.tenant_id == tenant_id,
                FormInstance.template_id == tpl.id,
                FormInstance.is_deleted == False,  # noqa: E712
                FormInstance.form_data["drawing_no"].astext == no,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if not isinstance(row, dict):
        return ""
    return str(row.get("contract_no") or "").strip()


async def list_drawing_map_lookups(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    keyword: str | None = None,
    limit: int = 50,
    *,
    exclude_contract_id: str | None = None,
) -> list[dict]:
    """合同登记/评审等：从合同图纸对应表选图纸编号（可带合同号展示）。"""
    from app.domains.lowcode import service as lc_svc
    from app.domains.lowcode.drawing_no_pool import is_drawing_no_taken_by_contract

    tpl = await lc_svc.ensure_builtin_form(db, tenant_id, "contract_drawing_map", user)
    items, _ = await lc_svc.list_instances(
        db, tenant_id, tpl.id, 1, min(max(limit, 1), 100),
        keyword=keyword or None, status=None, owner_ids=None,
    )
    out: list[dict] = []
    q = (keyword or "").strip().lower()
    for inst in items:
        # 草稿也占号，合同登记可选（对应表以图纸号为准，不要求先提交）
        fd = inst.form_data if isinstance(inst.form_data, dict) else {}
        contract_no = str(fd.get("contract_no") or "").strip()
        drawing_no = str(fd.get("drawing_no") or "").strip()
        if not drawing_no:
            continue
        if q and q not in contract_no.lower() and q not in drawing_no.lower():
            label_probe = f"{contract_no} {drawing_no}".lower()
            if q not in label_probe:
                continue
        # 已被其他合同登记占用的号不再出现在选数里（编辑本单时排除自身）
        if await is_drawing_no_taken_by_contract(
            db, tenant_id, drawing_no, exclude_contract_id=exclude_contract_id,
        ):
            continue
        dept = fd.get("department")
        department_id = None
        if isinstance(dept, str) and dept.strip():
            department_id = dept.strip()
        elif isinstance(dept, dict) and dept.get("id"):
            department_id = str(dept["id"])
        out.append({
            "id": inst.id,
            "contract_no": contract_no,
            "drawing_no": drawing_no,
            "department_id": department_id,
            "label": " · ".join(x for x in (drawing_no, contract_no) if x),
        })
    return out


async def list_base_form_lookups(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    form_code: str,
    keyword: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """合同登记等：从应用领域/应用物料/物料名称基础表取选项（名称）。"""
    from app.domains.lowcode.base_lookups import list_base_form_lookups as _list
    return await _list(db, tenant_id, user, form_code, keyword=keyword, limit=limit)


# ==================== Contract ====================

async def list_contracts_by_project(db: AsyncSession, tenant_id: str, project_id: str,
                                    user: dict | None = None):
    # 按 project_id 直查会绕过数据范围：先确认父商机对当前用户可见
    if user is not None:
        from app.domains.project.service import get_project
        await get_project(db, tenant_id, project_id, user)
    result = await db.execute(
        select(Contract).where(Contract.tenant_id == tenant_id, Contract.project_id == project_id)
        .order_by(Contract.created_at.desc())
    )
    return result.scalars().all()


async def get_contract(db: AsyncSession, tenant_id: str, contract_id: str,
                       user: dict | None = None) -> Contract:
    """按 id 取合同。传入 user 时按「所属商机的可见性」校验数据范围。

    user=None 表示系统内部调用（审批引擎读被审合同、到期提醒等），不做范围校验。
    """
    c = (await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not c:
        raise BusinessException(code=NOT_FOUND, message="合同不存在")
    from app.common.data_scope import assert_project_child_in_scope
    await assert_project_child_in_scope(db, tenant_id, user, c, label="该合同", biz_type="contract")
    return c


async def create_contract(db: AsyncSession, tenant_id: str, project_id: str | None, data: ContractCreate, user: dict) -> dict:
    as_draft = bool(getattr(data, "as_draft", False))
    # 关联商机可选：有则校验可见性；无则允许独立建合同（合同管理列表入口）
    project = None
    if project_id:
        from app.domains.project.service import get_project
        project = await get_project(db, tenant_id, project_id, user)
    # 字段级权限：丢弃用户对不可编辑/隐藏/脱敏扩展字段的写入，并校验必填
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    cfj = await sanitize_entity_write(
        db, tenant_id, "contract", data.custom_fields_json, None, user.get("roles"))
    await validate_entity_custom_fields(
        db, tenant_id, "contract", cfj, user.get("roles"), skip_required=as_draft,
    )
    # 商机侧「快速建合同」往往只带金额/条款；登记表一长串 default_required 只在
    # 实际提交的字段上校验（与 update 的 payload scope 一致）。exclude_unset 避免把
    # 未传字段以 None 塞进 payload 后被误判为「已提交但为空」。草稿可跳过必填。
    _NATIVE_CREATE_KEYS = (
        "contract_no", "amount_total", "end_date", "drawing_no", "peer_contract_no",
        "acquire_method", "delivery_date", "change_type", "order_date", "card_date",
        "assignee_id", "assignee_name", "department_id", "department_name",
        "registration_json",
    )
    raw = data.model_dump(exclude_unset=True)
    native_payload = {k: raw[k] for k in _NATIVE_CREATE_KEYS if k in raw}
    native = await enforce_native_field_policy(
        db, tenant_id, "contract", native_payload, None, user.get("roles"),
        required_scope="payload",
        skip_required=as_draft,
    )

    contract_no_requested = (native.get("contract_no") or data.contract_no or "").strip()
    reg = native.get("registration_json", data.registration_json) or {}
    if not isinstance(reg, dict):
        reg = {}
    # number_lookup 为历史选数残留；编号属性可按图纸号前缀静默带上（登记页已不再展示）
    reg = {k: v for k, v in reg.items() if k != "number_lookup"}
    # 图纸编号：从合同图纸对应表选用
    drawing_no = await _resolve_create_drawing_no(
        db, tenant_id, user,
        native.get("drawing_no") or data.drawing_no,
        number_attr=reg.get("number_attr"),
        allow_empty=as_draft,
    )
    if drawing_no:
        map_cn = await _lookup_map_contract_no(db, tenant_id, user, drawing_no)
        # 合同号优先用对应表「合同号」；前端已回填则沿用，否则用对应表或回退图纸号
        if not contract_no_requested:
            contract_no_requested = map_cn or drawing_no
        elif map_cn and contract_no_requested == drawing_no and map_cn != drawing_no:
            # 兼容旧前端把图纸号当合同号提交的情况
            contract_no_requested = map_cn
        if drawing_no.upper().startswith("SY"):
            reg["number_attr"] = "SY"
        elif drawing_no.upper().startswith("WMGF"):
            reg["number_attr"] = "WMGF"
        else:
            reg["number_attr"] = normalize_number_attr(reg.get("number_attr"))
    else:
        reg["number_attr"] = normalize_number_attr(reg.get("number_attr"))
    contract_no = await _resolve_create_contract_no(
        db, tenant_id, contract_no_requested,
        allow_draft=as_draft,
    )

    # 显式指定优先；未传时从关联商机带出客户，保证列表「客户名称」可补全
    customer_id = data.customer_id or (getattr(project, "customer_id", None) if project else None)
    if not as_draft and not customer_id:
        raise BusinessException(code=BUSINESS_ERROR, message="请选择关联客户")

    contract = Contract(
        id=generate_uuid(), tenant_id=tenant_id,
        project_id=project_id or None, customer_id=customer_id,
        contract_no=contract_no,
        current_version_no=1,
        amount_total=native.get("amount_total", data.amount_total),
        end_date=native.get("end_date", data.end_date),
        drawing_no=drawing_no,
        peer_contract_no=native.get("peer_contract_no", data.peer_contract_no),
        acquire_method=native.get("acquire_method", data.acquire_method),
        delivery_date=native.get("delivery_date", data.delivery_date),
        change_type=native.get("change_type", data.change_type),
        order_date=native.get("order_date", data.order_date),
        card_date=native.get("card_date", data.card_date),
        payment_terms_json=data.payment_terms_json,
        delivery_terms_json=data.delivery_terms_json,
        registration_json=reg or None,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        assignee_id=native.get("assignee_id", data.assignee_id),
        assignee_name=native.get("assignee_name", data.assignee_name),
        department_id=native.get("department_id", data.department_id),
        department_name=native.get("department_name", data.department_name),
        custom_fields_json=cfj,
    )
    db.add(contract)

    version = ContractVersion(
        id=generate_uuid(), tenant_id=tenant_id,
        contract_id=contract.id, version_no=1,
        title=data.title or "V1",
        key_clauses_json=data.key_clauses_json,
    )
    db.add(version)
    await db.commit()
    await db.refresh(contract)
    await db.refresh(version)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="contract", resource_id=contract.id,
                     summary=f"创建合同: {contract.contract_no}")
    return {"contract": contract, "version": version}


async def update_contract(db: AsyncSession, tenant_id: str, contract_id: str, data: ContractUpdate, user: dict) -> Contract:
    contract = await get_contract(db, tenant_id, contract_id, user)
    from app.domains.lowcode.edit_lock import assert_contract_record_editable
    await assert_contract_record_editable(db, tenant_id, contract)
    as_draft = bool(getattr(data, "as_draft", False))
    payload = data.model_dump(exclude_unset=True)
    payload.pop("as_draft", None)
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    if "custom_fields_json" in payload:
        payload["custom_fields_json"] = await sanitize_entity_write(
            db, tenant_id, "contract", payload["custom_fields_json"],
            contract.custom_fields_json, user.get("roles"))
        await validate_entity_custom_fields(
            db, tenant_id, "contract", payload["custom_fields_json"], user.get("roles"),
            skip_required=as_draft,
        )
    # 改图纸编号：须在对应表中，且未被其他合同占用；合同号取对应表「合同号」
    if "drawing_no" in payload:
        from app.domains.lowcode import service as lc_svc
        from app.domains.lowcode.drawing_no_pool import (
            drawing_no_exists_in_map,
            is_drawing_no_taken_by_contract,
        )
        new_dn = (str(payload.get("drawing_no") or "")).strip()
        if not new_dn:
            if as_draft:
                payload["drawing_no"] = ""
            else:
                raise BusinessException(
                    code=BUSINESS_ERROR,
                    message="请从合同图纸对应表选择图纸编号",
                )
        elif new_dn != (contract.drawing_no or ""):
            tpl = await lc_svc.ensure_builtin_form(db, tenant_id, "contract_drawing_map", user)
            if not await drawing_no_exists_in_map(db, tenant_id, new_dn, map_template_id=tpl.id):
                raise BusinessException(
                    code=BUSINESS_ERROR,
                    message=f"图纸编号「{new_dn}」不在合同图纸对应表中，请从对应表选择",
                )
            if await is_drawing_no_taken_by_contract(
                db, tenant_id, new_dn, exclude_contract_id=contract_id,
            ):
                raise BusinessException(
                    code=DUPLICATE_ENTRY,
                    message=f"图纸编号「{new_dn}」已用于其他合同登记，请更换",
                )
            payload["drawing_no"] = new_dn
            map_cn = await _lookup_map_contract_no(db, tenant_id, user, new_dn)
            requested_cn = (str(payload.get("contract_no") or "")).strip()
            # 优先前端回填的对应表合同号；否则查表；再回退图纸号
            payload["contract_no"] = requested_cn or map_cn or new_dn
            if map_cn and requested_cn == new_dn and map_cn != new_dn:
                payload["contract_no"] = map_cn
            reg = payload.get("registration_json")
            if not isinstance(reg, dict):
                reg = dict(contract.registration_json or {}) if isinstance(contract.registration_json, dict) else {}
            upper = new_dn.upper()
            if upper.startswith("SY"):
                reg["number_attr"] = "SY"
            elif upper.startswith("WMGF"):
                reg["number_attr"] = "WMGF"
            payload["registration_json"] = reg
        else:
            payload.pop("drawing_no", None)

    # 改合同号：校验唯一（不含本条）；空串不允许覆盖正式号
    # 合同登记合同号通常由上方 drawing_no 从对应表同步写入
    if "contract_no" in payload:
        new_no = (str(payload.get("contract_no") or "")).strip()
        if not new_no:
            if as_draft:
                payload.pop("contract_no", None)
            else:
                raise BusinessException(code=BUSINESS_ERROR, message="请填写合同号")
        elif new_no != (contract.contract_no or ""):
            exists = (await db.execute(
                select(Contract.id).where(
                    Contract.tenant_id == tenant_id,
                    Contract.contract_no == new_no,
                    Contract.id != contract_id,
                ).limit(1)
            )).scalar_one_or_none()
            if exists:
                raise BusinessException(
                    code=DUPLICATE_ENTRY,
                    message=f"合同号「{new_no}」已存在，请更换后再保存",
                )
            payload["contract_no"] = new_no
        else:
            payload.pop("contract_no", None)
    # 原生字段策略：合同金额被脱敏成 "***" 后，编辑弹窗会把它绑进 InputNumber，
    # 用户随手一存就会用 null 覆盖真实金额 —— 写入侧必须与读取侧对称拦截。
    payload = await enforce_native_field_policy(
        db, tenant_id, "contract", payload, contract, user.get("roles"),
        required_scope="payload", skip_required=as_draft,
    )
    if not as_draft:
        effective_customer_id = (
            payload.get("customer_id") if "customer_id" in payload else contract.customer_id
        )
        if not effective_customer_id:
            raise BusinessException(code=BUSINESS_ERROR, message="请选择关联客户")
    for field, val in payload.items():
        setattr(contract, field, val)
    await db.commit()
    await db.refresh(contract)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="contract", resource_id=contract.id,
                     summary=f"更新合同: {contract.contract_no}")
    return contract


async def delete_contract(db: AsyncSession, tenant_id: str, contract_id: str, user: dict):
    contract = await get_contract(db, tenant_id, contract_id, user)
    contract_no = contract.contract_no

    versions = (await db.execute(
        select(ContractVersion).where(ContractVersion.tenant_id == tenant_id, ContractVersion.contract_id == contract_id)
    )).scalars().all()

    current_version = next(
        (v for v in versions if v.version_no == contract.current_version_no), None,
    )
    from app.domains.lowcode.edit_lock import assert_contract_deletable
    await assert_contract_deletable(db, tenant_id, contract, version=current_version)

    # Cascade: cancel pending approval flows for contract versions
    version_ids = [v.id for v in versions]
    if version_ids:
        try:
            from app.domains.approval.models import ApprovalFlow, ApprovalTask
            from sqlalchemy import update as sql_update
            flow_ids = (await db.execute(
                select(ApprovalFlow.id).where(
                    ApprovalFlow.tenant_id == tenant_id,
                    ApprovalFlow.biz_type == "contract_version",
                    ApprovalFlow.biz_id.in_(version_ids),
                )
            )).scalars().all()
            if flow_ids:
                await db.execute(
                    sql_update(ApprovalFlow).where(ApprovalFlow.id.in_(flow_ids), ApprovalFlow.status == "pending")
                    .values(status="withdrawn")
                )
                await db.execute(
                    sql_update(ApprovalTask).where(
                        ApprovalTask.flow_id.in_(flow_ids), ApprovalTask.status.in_(["pending", "waiting"])
                    ).values(status="cancelled")
                )
        except Exception as e:
            logger.warning("Cascade cancel approvals on contract delete failed: %s", e)

    for v in versions:
        await db.delete(v)

    await db.delete(contract)
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="contract", resource_id=contract_id,
                     summary=f"删除合同: {contract_no}")


async def new_version(db: AsyncSession, tenant_id: str, contract_id: str, user: dict) -> ContractVersion:
    contract = await get_contract(db, tenant_id, contract_id, user)

    current_version = (await db.execute(
        select(ContractVersion).where(
            ContractVersion.tenant_id == tenant_id,
            ContractVersion.contract_id == contract_id,
            ContractVersion.version_no == contract.current_version_no,
        )
    )).scalar_one_or_none()

    new_no = contract.current_version_no + 1
    new_ver = ContractVersion(
        id=generate_uuid(), tenant_id=tenant_id,
        contract_id=contract_id, version_no=new_no,
        title=f"V{new_no}",
        key_clauses_json=current_version.key_clauses_json if current_version else None,
        risk_level=current_version.risk_level if current_version else None,
    )
    db.add(new_ver)
    contract.current_version_no = new_no
    await db.commit()
    await db.refresh(new_ver)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="new_version", resource_type="contract", resource_id=contract_id,
                     summary=f"创建合同新版本: {contract.contract_no} V{new_no}")
    return new_ver


async def create_from_quote(db: AsyncSession, tenant_id: str, quote_id: str, user: dict) -> dict:
    """Create a contract by converting from a quote, copying amount and terms."""
    from app.domains.quote.models import Quote, QuoteVersion, QuoteLine
    quote = (await db.execute(
        select(Quote).where(Quote.id == quote_id, Quote.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not quote:
        raise BusinessException(code=NOT_FOUND, message="报价不存在")
    # 源报价看不见就不能转成合同，否则可借转换把越权数据搬进自己的合同
    from app.common.data_scope import assert_project_child_in_scope
    await assert_project_child_in_scope(db, tenant_id, user, quote, label="该报价", biz_type="quote")

    # Get current quote version
    current_ver = (await db.execute(
        select(QuoteVersion).where(
            QuoteVersion.tenant_id == tenant_id,
            QuoteVersion.quote_id == quote_id,
            QuoteVersion.version_no == quote.current_version_no,
        )
    )).scalar_one_or_none()

    amount = float(current_ver.price_total) if current_ver and current_ver.price_total else None
    terms = current_ver.terms_summary_json if current_ver else None

    from app.common.code_generator import generate_code
    contract = Contract(
        id=generate_uuid(), tenant_id=tenant_id,
        project_id=quote.project_id, contract_no=await generate_code(db, tenant_id, "contract"),
        from_quote_id=quote_id,
        current_version_no=1,
        amount_total=amount,
        payment_terms_json=terms,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
    )
    db.add(contract)

    version = ContractVersion(
        id=generate_uuid(), tenant_id=tenant_id,
        contract_id=contract.id, version_no=1,
        title="V1",
    )
    db.add(version)
    await db.commit()
    await db.refresh(contract)
    await db.refresh(version)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="contract", resource_id=contract.id,
                     summary=f"从报价 {quote.quote_no} 转换创建合同: {contract.contract_no}")
    return {"contract": contract, "version": version}


async def sign_contract(db: AsyncSession, tenant_id: str, contract_id: str, signed_date: str, user: dict) -> Contract:
    contract = await get_contract(db, tenant_id, contract_id, user)
    if contract.status == "signed":
        raise BusinessException(code=BUSINESS_ERROR, message="合同已签署")

    # 若登记关联了合同评审流水号，签署前要求该评审已通过（签约闸门）
    reg = contract.registration_json if isinstance(contract.registration_json, dict) else {}
    review_sn = str(reg.get("review_sn") or "").strip()
    if review_sn:
        from app.domains.contract_review.models import ContractReview
        rv = (await db.execute(
            select(ContractReview).where(
                ContractReview.tenant_id == tenant_id,
                ContractReview.review_code == review_sn,
            ).limit(1)
        )).scalar_one_or_none()
        if rv is None:
            raise BusinessException(
                code=BUSINESS_ERROR,
                message=f"关联合同评审「{review_sn}」不存在，无法签署",
            )
        if rv.status != "approved":
            raise BusinessException(
                code=BUSINESS_ERROR,
                message=f"关联合同评审「{review_sn}」尚未通过（当前：{rv.status}），无法签署",
            )

    parsed_signed_date = date_type.fromisoformat(signed_date)
    if contract.end_date and parsed_signed_date > contract.end_date:
        raise BusinessException(code=BUSINESS_ERROR, message="签署日期不能晚于合同结束日期")

    contract.status = "signed"
    contract.signed_date = parsed_signed_date

    # Also mark current version as signed
    current_version = (await db.execute(
        select(ContractVersion).where(
            ContractVersion.tenant_id == tenant_id,
            ContractVersion.contract_id == contract_id,
            ContractVersion.version_no == contract.current_version_no,
        )
    )).scalar_one_or_none()
    if current_version:
        current_version.status = "signed"

    from app.domains.outbox.service import emit_event
    await emit_event(db, tenant_id, "crm.contract.signed", "contract", contract.id, {
        "contract_id": contract.id, "contract_no": contract.contract_no,
        "project_id": contract.project_id,
        "amount_total": float(contract.amount_total) if contract.amount_total else None,
        "signed_date": parsed_signed_date.isoformat(),
    })
    await db.commit()
    await db.refresh(contract)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="sign", resource_type="contract", resource_id=contract_id,
                     summary=f"签署合同: {contract.contract_no}")

    # Auto-notify contract creator
    try:
        from app.common.auto_notify import notify_contract_signed
        if contract.created_by_id and contract.created_by_id != user["sub"]:
            await notify_contract_signed(db, tenant_id, contract.contract_no, contract.created_by_id,
                                          user.get("real_name") or user.get("username"), contract_id)
    except Exception as e:
        logger.warning("Auto-notify contract signed failed: %s", e)

    # Auto-activity record on the project (skip if the contract has no project,
    # e.g. one ingested via the Open API where project_id is optional)
    if contract.project_id:
        try:
            from app.common.auto_activity import record_activity
            await record_activity(db, tenant_id, "project", contract.project_id, "system",
                                   f"签署合同: {contract.contract_no}", None,
                                   user["sub"], user.get("real_name") or user.get("username"))
        except Exception as e:
            logger.warning("Auto-activity record for contract sign failed: %s", e)

    return contract


# ==================== ContractVersion ====================

async def get_version(db: AsyncSession, tenant_id: str, version_id: str,
                      user: dict | None = None) -> ContractVersion:
    """按 id 取合同版本。版本自身没有 project_id，可见性由父合同决定。"""
    v = (await db.execute(
        select(ContractVersion).where(ContractVersion.id == version_id, ContractVersion.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not v:
        raise BusinessException(code=NOT_FOUND, message="合同版本不存在")
    if user is not None:
        await get_contract(db, tenant_id, v.contract_id, user)  # 越权即 403
    return v


async def get_versions_by_contract(db: AsyncSession, tenant_id: str, contract_id: str,
                                   user: dict | None = None):
    if user is not None:
        await get_contract(db, tenant_id, contract_id, user)  # 数据范围校验
    result = await db.execute(
        select(ContractVersion).where(ContractVersion.tenant_id == tenant_id, ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_no)
    )
    return result.scalars().all()


CONTRACT_VERSION_DEFAULT_FLOW_CODE = "SYS_CONTRACT_VERSION_APPROVAL"


async def _ensure_contract_version_default_flow(db: AsyncSession, tenant_id: str) -> None:
    from app.domains.lowcode.workflow_service import ensure_default_definition
    await ensure_default_definition(
        db, tenant_id,
        biz_type="contract_version",
        code=CONTRACT_VERSION_DEFAULT_FLOW_CODE,
        name="合同登记审批（运营）",
        # 系统兜底图在 workflow_service._contract_version_flow_graph（简道云登记运营）
        approver_rule={"type": "specified_role", "value": "finance_manager", "exclude_initiator": True},
        multi_mode="or_sign",
        empty_strategy="auto_approve",
    )


async def submit_version_for_approval(
    db: AsyncSession, tenant_id: str, version_id: str, user: dict,
    assignee_ids: list[str] | None = None,
    assignee_names: list[str] | None = None,
) -> ContractVersion:
    """合同版本提交审批：优先流程管理 start_for_biz，未发布时回退旧 approval。"""
    version = await get_version(db, tenant_id, version_id, user)
    if version.status in ("approved", "signed"):
        raise BusinessException(code=BUSINESS_ERROR, message=f"当前版本状态「{version.status}」不可再提交审批")

    await _ensure_contract_version_default_flow(db, tenant_id)

    c = (await db.execute(
        select(Contract).where(Contract.id == version.contract_id, Contract.tenant_id == tenant_id)
    )).scalar_one_or_none()
    title = f"合同审批: {c.contract_no if c else ''} V{version.version_no}"

    version.status = "submitted"
    await db.flush()

    from app.domains.lowcode.workflow_service import start_for_biz
    pinst = await start_for_biz(db, tenant_id, "contract_version", version_id, user, title=title)
    if pinst is None:
        if assignee_ids:
            from app.domains.approval.schemas import ApprovalSubmit
            from app.domains.approval.service import submit_approval
            await submit_approval(db, tenant_id, ApprovalSubmit(
                biz_type="contract_version",
                biz_id=version_id,
                title=title,
                assignee_ids=assignee_ids,
                assignee_names=assignee_names,
            ), user)
        else:
            from app.domains.approval.service import auto_trigger_approval
            await auto_trigger_approval(db, tenant_id, "contract_version", version_id, title, user)

    await db.commit()
    await db.refresh(version)
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="submit", resource_type="contract_version", resource_id=version_id,
        summary=title,
    )
    return version


async def update_version(db: AsyncSession, tenant_id: str, version_id: str, data: ContractVersionUpdate, user: dict) -> ContractVersion:
    version = await get_version(db, tenant_id, version_id, user)
    old_status = version.status if hasattr(version, 'status') else None
    payload = data.model_dump(exclude_unset=True)
    from app.domains.lowcode.edit_lock import assert_content_update_allowed
    await assert_content_update_allowed(
        db, tenant_id, "contract_version", version.id, old_status, payload)
    for field, val in payload.items():
        setattr(version, field, val)
    await db.commit()
    await db.refresh(version)

    # Auto-trigger approval when version is submitted
    new_status = version.status if hasattr(version, 'status') else None
    if new_status == "submitted" and old_status != "submitted":
        try:
            c = (await db.execute(
                select(Contract).where(Contract.id == version.contract_id, Contract.tenant_id == tenant_id)
            )).scalar_one_or_none()
            title = f"合同审批: {c.contract_no if c else ''} V{version.version_no}"
            await _ensure_contract_version_default_flow(db, tenant_id)
            # 优先新表单引擎工作流（灰度按 biz_type 切换），未绑定则回退旧引擎
            from app.domains.lowcode.workflow_service import start_for_biz
            pinst = await start_for_biz(db, tenant_id, "contract_version", version_id, user, title=title)
            if pinst is None:
                from app.domains.approval.service import auto_trigger_approval
                await auto_trigger_approval(db, tenant_id, "contract_version", version_id, title, user)
        except Exception as e:
            logger.warning("Auto-trigger approval for contract version failed: %s", e)

    return version
