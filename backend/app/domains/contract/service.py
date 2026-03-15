import logging
from datetime import datetime, timezone, date as date_type

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR
from app.domains.contract.models import Contract, ContractVersion
from app.domains.contract.schemas import ContractCreate, ContractUpdate, ContractVersionUpdate
from app.domains.audit.service import log_action
from app.common.code_generator import generate_code

logger = logging.getLogger("spt_crm.contract")



# ==================== Contract ====================

async def list_contracts_by_project(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(Contract).where(Contract.tenant_id == tenant_id, Contract.project_id == project_id)
        .order_by(Contract.created_at.desc())
    )
    return result.scalars().all()


async def get_contract(db: AsyncSession, tenant_id: str, contract_id: str) -> Contract:
    c = (await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not c:
        raise BusinessException(code=NOT_FOUND, message="合同不存在")
    return c


async def create_contract(db: AsyncSession, tenant_id: str, project_id: str, data: ContractCreate, user: dict) -> dict:
    contract = Contract(
        id=generate_uuid(), tenant_id=tenant_id,
        project_id=project_id, contract_no=await generate_code(db, tenant_id, "contract"),
        current_version_no=1,
        amount_total=data.amount_total,
        payment_terms_json=data.payment_terms_json,
        delivery_terms_json=data.delivery_terms_json,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
    )
    db.add(contract)

    version = ContractVersion(
        id=generate_uuid(), tenant_id=tenant_id,
        contract_id=contract.id, version_no=1,
        title=data.title or "V1",
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
    contract = await get_contract(db, tenant_id, contract_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(contract, field, val)
    await db.commit()
    await db.refresh(contract)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="contract", resource_id=contract.id,
                     summary=f"更新合同: {contract.contract_no}")
    return contract


async def delete_contract(db: AsyncSession, tenant_id: str, contract_id: str, user: dict):
    contract = await get_contract(db, tenant_id, contract_id)
    contract_no = contract.contract_no

    versions = (await db.execute(
        select(ContractVersion).where(ContractVersion.tenant_id == tenant_id, ContractVersion.contract_id == contract_id)
    )).scalars().all()

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
    contract = await get_contract(db, tenant_id, contract_id)

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
    contract = await get_contract(db, tenant_id, contract_id)
    if contract.status == "signed":
        raise BusinessException(code=BUSINESS_ERROR, message="合同已签署")

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

    # Auto-activity record on the project
    try:
        from app.common.auto_activity import record_activity
        await record_activity(db, tenant_id, "project", contract.project_id, "system",
                               f"签署合同: {contract.contract_no}", None,
                               user["sub"], user.get("real_name") or user.get("username"))
    except Exception as e:
        logger.warning("Auto-activity record for contract sign failed: %s", e)

    return contract


# ==================== ContractVersion ====================

async def get_version(db: AsyncSession, tenant_id: str, version_id: str) -> ContractVersion:
    v = (await db.execute(
        select(ContractVersion).where(ContractVersion.id == version_id, ContractVersion.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not v:
        raise BusinessException(code=NOT_FOUND, message="合同版本不存在")
    return v


async def get_versions_by_contract(db: AsyncSession, tenant_id: str, contract_id: str):
    result = await db.execute(
        select(ContractVersion).where(ContractVersion.tenant_id == tenant_id, ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_no)
    )
    return result.scalars().all()


async def update_version(db: AsyncSession, tenant_id: str, version_id: str, data: ContractVersionUpdate, user: dict) -> ContractVersion:
    version = await get_version(db, tenant_id, version_id)
    old_status = version.status if hasattr(version, 'status') else None
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(version, field, val)
    await db.commit()
    await db.refresh(version)

    # Auto-trigger approval when version is submitted
    new_status = version.status if hasattr(version, 'status') else None
    if new_status == "submitted" and old_status != "submitted":
        try:
            from app.domains.approval.service import auto_trigger_approval
            c = (await db.execute(
                select(Contract).where(Contract.id == version.contract_id)
            )).scalar_one_or_none()
            title = f"合同审批: {c.contract_no if c else ''} V{version.version_no}"
            await auto_trigger_approval(db, tenant_id, "contract_version", version_id, title, user)
        except Exception as e:
            logger.warning("Auto-trigger approval for contract version failed: %s", e)

    return version
