import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR
from app.domains.quote.models import Quote, QuoteVersion, QuoteLine, CostSnapshot, QuoteSendLog
from app.domains.quote.schemas import QuoteCreate, QuoteUpdate, QuoteVersionUpdate, QuoteLineCreate, QuoteLineUpdate, CostSnapshotCreate, QuoteSendLogCreate
from app.domains.audit.service import log_action
from app.common.code_generator import generate_code

logger = logging.getLogger("spt_crm.quote")



async def _recalc_totals(db: AsyncSession, tenant_id: str, version_id: str):
    """Recalculate version totals from line items."""
    version = (await db.execute(
        select(QuoteVersion).where(QuoteVersion.id == version_id, QuoteVersion.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not version:
        return

    lines = (await db.execute(
        select(QuoteLine).where(QuoteLine.quote_version_id == version_id, QuoteLine.tenant_id == tenant_id)
    )).scalars().all()

    price_total = sum(float(l.line_total or 0) for l in lines)
    version.price_total = price_total

    tax_rate = float(version.tax_rate or 0)
    version.tax_total = round(price_total * tax_rate, 2)

    total_cost = sum(float(l.cost_est or 0) * float(l.qty or 0) for l in lines)
    if price_total > 0:
        version.margin_rate = round((price_total - total_cost) / price_total, 4)
    else:
        version.margin_rate = 0


# ==================== Quote ====================

async def list_quotes_by_project(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(Quote).where(Quote.tenant_id == tenant_id, Quote.project_id == project_id)
        .order_by(Quote.created_at.desc())
    )
    return result.scalars().all()


async def get_quote(db: AsyncSession, tenant_id: str, quote_id: str) -> Quote:
    q = (await db.execute(
        select(Quote).where(Quote.id == quote_id, Quote.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not q:
        raise BusinessException(code=NOT_FOUND, message="报价不存在")
    return q


async def create_quote(db: AsyncSession, tenant_id: str, project_id: str, data: QuoteCreate, user: dict) -> dict:
    # 字段级权限：丢弃用户对不可编辑/隐藏扩展字段的写入
    from app.domains.lowcode.field_permission import sanitize_entity_write
    cf = await sanitize_entity_write(db, tenant_id, "quote", data.custom_fields_json, None, user.get("roles"))
    quote = Quote(
        id=generate_uuid(), tenant_id=tenant_id,
        project_id=project_id, quote_no=await generate_code(db, tenant_id, "quote"),
        current_version_no=1,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        assignee_id=data.assignee_id, assignee_name=data.assignee_name,
        department_id=data.department_id, department_name=data.department_name,
        custom_fields_json=cf,
    )
    db.add(quote)

    version = QuoteVersion(
        id=generate_uuid(), tenant_id=tenant_id,
        quote_id=quote.id, version_no=1,
        title=data.title or "V1",
        validity_days=data.validity_days,
        terms_summary_json=data.terms_summary_json,
    )
    db.add(version)
    await db.commit()
    await db.refresh(quote)
    await db.refresh(version)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="quote", resource_id=quote.id,
                     summary=f"创建报价: {quote.quote_no}")

    # Auto-activity record on the project
    try:
        from app.common.auto_activity import record_activity
        await record_activity(db, tenant_id, "project", project_id, "system",
                               f"创建报价: {quote.quote_no}", None,
                               user["sub"], user.get("real_name") or user.get("username"))
    except Exception as e:
        logger.warning("Auto-activity record for quote creation failed: %s", e)

    return {"quote": quote, "version": version}


async def update_quote(db: AsyncSession, tenant_id: str, quote_id: str, data: QuoteUpdate, user: dict) -> Quote:
    quote = await get_quote(db, tenant_id, quote_id)
    dump = data.model_dump(exclude_unset=True)
    # 字段级权限：不可编辑扩展字段保留原值，忽略用户改动
    if "custom_fields_json" in dump:
        from app.domains.lowcode.field_permission import sanitize_entity_write
        dump["custom_fields_json"] = await sanitize_entity_write(
            db, tenant_id, "quote", dump["custom_fields_json"], quote.custom_fields_json, user.get("roles"))
    for field, val in dump.items():
        setattr(quote, field, val)
    await db.commit()
    await db.refresh(quote)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="quote", resource_id=quote.id,
                     summary=f"更新报价: {quote.quote_no}")
    return quote


async def delete_quote(db: AsyncSession, tenant_id: str, quote_id: str, user: dict):
    quote = await get_quote(db, tenant_id, quote_id)
    quote_no = quote.quote_no

    # Delete all versions and lines
    versions = (await db.execute(
        select(QuoteVersion).where(QuoteVersion.tenant_id == tenant_id, QuoteVersion.quote_id == quote_id)
    )).scalars().all()

    # Cascade: cancel pending approval flows for quote versions
    version_ids = [v.id for v in versions]
    if version_ids:
        try:
            from app.domains.approval.models import ApprovalFlow, ApprovalTask
            from sqlalchemy import update as sql_update
            flow_ids = (await db.execute(
                select(ApprovalFlow.id).where(
                    ApprovalFlow.tenant_id == tenant_id,
                    ApprovalFlow.biz_type == "quote_version",
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
            logger.warning("Cascade cancel approvals on quote delete failed: %s", e)

    for v in versions:
        lines = (await db.execute(
            select(QuoteLine).where(QuoteLine.tenant_id == tenant_id, QuoteLine.quote_version_id == v.id)
        )).scalars().all()
        for l in lines:
            await db.delete(l)
        await db.delete(v)

    await db.delete(quote)
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="quote", resource_id=quote_id,
                     summary=f"删除报价: {quote_no}")


async def new_version(db: AsyncSession, tenant_id: str, quote_id: str, user: dict) -> QuoteVersion:
    """Create a new version by copying lines from current version."""
    quote = await get_quote(db, tenant_id, quote_id)

    # Get current version
    current_version = (await db.execute(
        select(QuoteVersion).where(
            QuoteVersion.tenant_id == tenant_id,
            QuoteVersion.quote_id == quote_id,
            QuoteVersion.version_no == quote.current_version_no,
        )
    )).scalar_one_or_none()

    new_no = quote.current_version_no + 1
    new_ver = QuoteVersion(
        id=generate_uuid(), tenant_id=tenant_id,
        quote_id=quote_id, version_no=new_no,
        title=f"V{new_no}",
        tax_rate=current_version.tax_rate if current_version else None,
        validity_days=current_version.validity_days if current_version else 30,
        terms_summary_json=current_version.terms_summary_json if current_version else None,
    )
    db.add(new_ver)

    # Copy lines
    if current_version:
        lines = (await db.execute(
            select(QuoteLine).where(QuoteLine.tenant_id == tenant_id, QuoteLine.quote_version_id == current_version.id)
            .order_by(QuoteLine.line_no)
        )).scalars().all()
        for line in lines:
            new_line = QuoteLine(
                id=generate_uuid(), tenant_id=tenant_id,
                quote_version_id=new_ver.id, line_no=line.line_no,
                item_type=line.item_type, item_name=line.item_name,
                item_code=line.item_code, spec=line.spec,
                qty=line.qty, unit=line.unit, unit_price=line.unit_price,
                line_total=line.line_total, cost_est=line.cost_est, leadtime_days=line.leadtime_days,
            )
            db.add(new_line)

    quote.current_version_no = new_no
    await db.commit()
    await db.refresh(new_ver)

    await _recalc_totals(db, tenant_id, new_ver.id)
    await db.commit()
    await db.refresh(new_ver)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="new_version", resource_type="quote", resource_id=quote_id,
                     summary=f"创建报价新版本: {quote.quote_no} V{new_no}")
    return new_ver


# ==================== QuoteVersion ====================

async def get_version(db: AsyncSession, tenant_id: str, version_id: str) -> QuoteVersion:
    v = (await db.execute(
        select(QuoteVersion).where(QuoteVersion.id == version_id, QuoteVersion.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not v:
        raise BusinessException(code=NOT_FOUND, message="报价版本不存在")
    return v


async def get_versions_by_quote(db: AsyncSession, tenant_id: str, quote_id: str):
    result = await db.execute(
        select(QuoteVersion).where(QuoteVersion.tenant_id == tenant_id, QuoteVersion.quote_id == quote_id)
        .order_by(QuoteVersion.version_no)
    )
    return result.scalars().all()


async def update_version(db: AsyncSession, tenant_id: str, version_id: str, data: QuoteVersionUpdate, user: dict) -> QuoteVersion:
    version = await get_version(db, tenant_id, version_id)
    old_status = version.status if hasattr(version, 'status') else None
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(version, field, val)

    await _recalc_totals(db, tenant_id, version_id)
    await db.commit()
    await db.refresh(version)

    # Auto-trigger approval when version is submitted
    new_status = version.status if hasattr(version, 'status') else None
    if new_status == "submitted" and old_status != "submitted":
        try:
            q = (await db.execute(select(Quote).where(Quote.id == version.quote_id, Quote.tenant_id == tenant_id))).scalar_one_or_none()
            title = f"报价审批: {q.quote_no if q else ''} V{version.version_no}"
            from app.domains.approval.service import _check_margin_redline, auto_trigger_approval
            # 毛利红线是报价专有的业务闸门，只存在于旧 submit_approval。触及红线时不进新引擎，
            # 交旧引擎按红线拦截（其结果在本 try 内处理），保证灰度切换不绕过财务管控。
            margin = await _check_margin_redline(db, tenant_id, "quote_version", version_id)
            if margin and margin.get("action") == "block":
                await auto_trigger_approval(db, tenant_id, "quote_version", version_id, title, user)
            else:
                # 优先新表单引擎工作流（灰度按 biz_type 切换），未绑定则回退旧引擎
                from app.domains.lowcode.workflow_service import start_for_biz
                pinst = await start_for_biz(db, tenant_id, "quote_version", version_id, user, title=title)
                if pinst is None:
                    await auto_trigger_approval(db, tenant_id, "quote_version", version_id, title, user)
        except Exception as e:
            logger.warning("Auto-trigger approval for quote version failed: %s", e)

    return version


# ==================== QuoteLine ====================

async def list_lines(db: AsyncSession, tenant_id: str, version_id: str):
    result = await db.execute(
        select(QuoteLine).where(QuoteLine.tenant_id == tenant_id, QuoteLine.quote_version_id == version_id)
        .order_by(QuoteLine.line_no)
    )
    return result.scalars().all()


async def add_line(db: AsyncSession, tenant_id: str, version_id: str, data: QuoteLineCreate, user: dict) -> QuoteLine:
    # Auto line_no
    max_line_no = (await db.execute(
        select(func.max(QuoteLine.line_no)).where(
            QuoteLine.tenant_id == tenant_id, QuoteLine.quote_version_id == version_id
        )
    )).scalar() or 0

    qty = data.qty or 0
    unit_price = data.unit_price or 0
    line_total = round(qty * unit_price, 2)

    line = QuoteLine(
        id=generate_uuid(), tenant_id=tenant_id,
        quote_version_id=version_id,
        line_no=max_line_no + 1,
        line_total=line_total,
        **data.model_dump(),
    )
    db.add(line)
    await db.flush()

    await _recalc_totals(db, tenant_id, version_id)
    await db.commit()
    await db.refresh(line)
    return line


async def update_line(db: AsyncSession, tenant_id: str, line_id: str, data: QuoteLineUpdate, user: dict) -> QuoteLine:
    line = (await db.execute(
        select(QuoteLine).where(QuoteLine.id == line_id, QuoteLine.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not line:
        raise BusinessException(code=NOT_FOUND, message="行项目不存在")

    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(line, field, val)

    qty = float(line.qty or 0)
    unit_price = float(line.unit_price or 0)
    line.line_total = round(qty * unit_price, 2)

    await _recalc_totals(db, tenant_id, line.quote_version_id)
    await db.commit()
    await db.refresh(line)
    return line


async def delete_line(db: AsyncSession, tenant_id: str, line_id: str, user: dict):
    line = (await db.execute(
        select(QuoteLine).where(QuoteLine.id == line_id, QuoteLine.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not line:
        raise BusinessException(code=NOT_FOUND, message="行项目不存在")

    version_id = line.quote_version_id
    await db.delete(line)
    await _recalc_totals(db, tenant_id, version_id)
    await db.commit()


# ==================== Version Comparison ====================

async def compare_versions(db: AsyncSession, tenant_id: str, version_id_a: str, version_id_b: str) -> dict:
    """Compare two quote versions: header fields + line items."""
    ver_a = await get_version(db, tenant_id, version_id_a)
    ver_b = await get_version(db, tenant_id, version_id_b)
    lines_a = await list_lines(db, tenant_id, version_id_a)
    lines_b = await list_lines(db, tenant_id, version_id_b)

    def _ver_dict(v):
        return {
            "id": v.id, "version_no": v.version_no, "title": v.title,
            "price_total": float(v.price_total) if v.price_total is not None else None,
            "tax_rate": float(v.tax_rate) if v.tax_rate is not None else None,
            "tax_total": float(v.tax_total) if v.tax_total is not None else None,
            "discount_total": float(v.discount_total) if v.discount_total is not None else None,
            "margin_rate": float(v.margin_rate) if v.margin_rate is not None else None,
            "delivery_promise_date": str(v.delivery_promise_date) if v.delivery_promise_date else None,
            "validity_days": v.validity_days,
            "status": v.status,
        }

    def _line_dict(l):
        return {
            "line_no": l.line_no, "item_type": l.item_type, "item_name": l.item_name,
            "item_code": l.item_code, "spec": l.spec,
            "qty": float(l.qty) if l.qty is not None else None,
            "unit": l.unit,
            "unit_price": float(l.unit_price) if l.unit_price is not None else None,
            "line_total": float(l.line_total) if l.line_total is not None else None,
            "cost_est": float(l.cost_est) if l.cost_est is not None else None,
            "leadtime_days": l.leadtime_days,
        }

    # Match lines by item_code or line_no
    lines_a_dict = {(l.item_code or f"line_{l.line_no}"): _line_dict(l) for l in lines_a}
    lines_b_dict = {(l.item_code or f"line_{l.line_no}"): _line_dict(l) for l in lines_b}

    all_keys = list(dict.fromkeys(list(lines_a_dict.keys()) + list(lines_b_dict.keys())))
    line_diffs = []
    for key in all_keys:
        la = lines_a_dict.get(key)
        lb = lines_b_dict.get(key)
        if la and lb:
            changes = {}
            for field in ["qty", "unit_price", "line_total", "cost_est", "leadtime_days", "spec"]:
                if la.get(field) != lb.get(field):
                    changes[field] = {"a": la.get(field), "b": lb.get(field)}
            line_diffs.append({"key": key, "item_name": la.get("item_name") or lb.get("item_name"), "status": "changed" if changes else "unchanged", "a": la, "b": lb, "changes": changes})
        elif la:
            line_diffs.append({"key": key, "item_name": la.get("item_name"), "status": "removed", "a": la, "b": None, "changes": {}})
        else:
            line_diffs.append({"key": key, "item_name": lb.get("item_name"), "status": "added", "a": None, "b": lb, "changes": {}})

    # Header diffs
    header_changes = {}
    for field in ["price_total", "tax_rate", "margin_rate", "discount_total", "delivery_promise_date", "validity_days"]:
        va = _ver_dict(ver_a).get(field)
        vb = _ver_dict(ver_b).get(field)
        if va != vb:
            header_changes[field] = {"a": va, "b": vb}

    return {
        "version_a": _ver_dict(ver_a),
        "version_b": _ver_dict(ver_b),
        "header_changes": header_changes,
        "line_diffs": line_diffs,
    }


# ==================== Cost Snapshot ====================

async def create_cost_snapshot(db: AsyncSession, tenant_id: str, version_id: str, user: dict, data: CostSnapshotCreate | None = None) -> CostSnapshot:
    version = await get_version(db, tenant_id, version_id)
    lines = await list_lines(db, tenant_id, version_id)

    cost_total = sum(float(l.cost_est or 0) * float(l.qty or 0) for l in lines)
    line_snapshot = [{
        "line_no": l.line_no, "item_name": l.item_name, "item_code": l.item_code,
        "qty": float(l.qty) if l.qty is not None else None,
        "unit_price": float(l.unit_price) if l.unit_price is not None else None,
        "line_total": float(l.line_total) if l.line_total is not None else None,
        "cost_est": float(l.cost_est) if l.cost_est is not None else None,
    } for l in lines]

    snapshot = CostSnapshot(
        id=generate_uuid(), tenant_id=tenant_id,
        quote_version_id=version_id,
        snapshot_type=data.snapshot_type if data else "manual",
        price_total=version.price_total,
        cost_total=cost_total,
        margin_rate=version.margin_rate,
        breakdown_json=data.breakdown_json if data else None,
        line_snapshot_json=line_snapshot,
        note=data.note if data else None,
        created_by_id=user["sub"],
        created_by_name=user.get("real_name") or user.get("username"),
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def list_cost_snapshots(db: AsyncSession, tenant_id: str, version_id: str):
    result = await db.execute(
        select(CostSnapshot).where(CostSnapshot.tenant_id == tenant_id, CostSnapshot.quote_version_id == version_id)
        .order_by(CostSnapshot.created_at.desc())
    )
    return result.scalars().all()


# ==================== Quote Send Log ====================

async def create_send_log(db: AsyncSession, tenant_id: str, quote_id: str, version_id: str, data: QuoteSendLogCreate, user: dict) -> QuoteSendLog:
    # Verify quote and version exist
    await get_quote(db, tenant_id, quote_id)
    await get_version(db, tenant_id, version_id)

    log = QuoteSendLog(
        id=generate_uuid(), tenant_id=tenant_id,
        quote_id=quote_id, quote_version_id=version_id,
        channel=data.channel,
        to_list_json=data.to_list_json,
        subject=data.subject,
        body=data.body,
        attachments_json=data.attachments_json,
        status="sent",
        sent_by_id=user["sub"],
        sent_by_name=user.get("real_name") or user.get("username"),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="send_quote", resource_type="quote", resource_id=quote_id,
                     summary=f"发送报价: {data.channel}")
    return log


async def list_send_logs(db: AsyncSession, tenant_id: str, quote_id: str):
    result = await db.execute(
        select(QuoteSendLog).where(QuoteSendLog.tenant_id == tenant_id, QuoteSendLog.quote_id == quote_id)
        .order_by(QuoteSendLog.created_at.desc())
    )
    return result.scalars().all()
