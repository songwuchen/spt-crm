"""列表关联名回填工具 (issue #91 / #92)。

方案/报价/合同/变更/交付里程碑等实体只存 project_id，售后工单只存
customer_id/order_id。列表页需展示商机名称/客户名称/订单名称时，用批量查询按
id 实时关联，避免前端靠"拉前 N 条"猜映射（受分页/数据范围限制会查不到名字）。
"""
from sqlalchemy import select


async def project_names_map(db, tenant_id: str, project_ids) -> dict:
    """给定 project_ids，返回 {project_id: {"project_name", "customer_name"}}。

    两跳关联：project_id -> OpportunityProject.name（商机名称），
    project_id -> customer_id -> Customer.name（客户名称）。
    """
    from app.domains.project.models import OpportunityProject
    from app.domains.customer.models import Customer

    ids = {pid for pid in project_ids if pid}
    if not ids:
        return {}
    prows = (await db.execute(
        select(OpportunityProject.id, OpportunityProject.name, OpportunityProject.customer_id).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.id.in_(ids),
        )
    )).all()
    cust_ids = {cid for _, _, cid in prows if cid}
    cust_names: dict = {}
    if cust_ids:
        crows = (await db.execute(
            select(Customer.id, Customer.name).where(
                Customer.tenant_id == tenant_id,
                Customer.id.in_(cust_ids),
            )
        )).all()
        cust_names = {cid: name for cid, name in crows}
    return {
        pid: {"project_name": name, "customer_name": cust_names.get(cid)}
        for pid, name, cid in prows
    }


async def customer_names_map(db, tenant_id: str, customer_ids) -> dict:
    """给定 customer_ids，返回 {customer_id: name}。"""
    from app.domains.customer.models import Customer

    ids = {cid for cid in customer_ids if cid}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Customer.id, Customer.name).where(
            Customer.tenant_id == tenant_id,
            Customer.id.in_(ids),
        )
    )).all()
    return {cid: name for cid, name in rows}


async def order_names_map(db, tenant_id: str, order_ids) -> dict:
    """给定 order_ids，返回 {order_id: 订单名称}（优先 title，回退 order_no）。"""
    from app.domains.order.models import Order

    ids = {oid for oid in order_ids if oid}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Order.id, Order.title, Order.order_no).where(
            Order.tenant_id == tenant_id,
            Order.id.in_(ids),
        )
    )).all()
    return {oid: (title or order_no) for oid, title, order_no in rows}
