"""新工作流引擎的通知层(与旧 approval 引擎能力对齐)。

旧 approval 引擎在 submit/decide/withdraw/delegate 时会发站内通知、下发钉钉个人待办、
推送群消息、写 outbox 事件与审计日志；新引擎此前只有催办和 SLA 超时两处通知，导致
任一 biz_type 灰度切到新引擎后审批人收不到任何推送。此模块把这套能力补齐并集中管理。

约定:
- 所有函数「尽力而为」，任何异常只记日志不外抛 —— 通知失败绝不能影响审批事务；
- 通知在业务事务 commit 之后下发(引擎用 _notify 队列延迟到提交后 flush)，
  唯独 outbox 事件必须在 commit 之前入队(与旧引擎 _enqueue_approval_event 一致);
- **除 outbox 入队外，所有写操作都在本模块自己开的短生命周期 session 里完成**。
  通知是旁路，绝不能在调用方的业务 session 上 commit —— 一旦通知侧的 commit 失败，
  调用方 session 会进入 needs-rollback，之后它自己的 commit 就会抛 PendingRollbackError
  (与 audit.log_action 用独立 session 的理由相同)。
- 深链: PC → /approvals?wf={实例id}(审批中心并打开抽屉)，移动端 → /m/lowcode/approvals/{实例id}(详情页)，
  与旧引擎 /approvals?flow= 与 /m/approvals/{flow_id} 的分流方式一致，钉钉容器免登链路复用。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.lowcode.workflow_models import WfProcessInstance, WfTaskInstance

logger = logging.getLogger("spt_crm.lowcode.wf_notify")

# 站内通知的 biz_type，前端 notificationRoute.ts 按此解析跳转目标
NOTIFY_BIZ_TYPE = "wf_instance"


async def _ensure_process_cc_rows(
    db: AsyncSession, tenant_id: str, process_instance_id: str, user_ids: list[str],
) -> None:
    """保证被抄送人在 wf_process_cc 有记录（审批中心「抄送我的」数据源）。"""
    from app.database import generate_uuid
    from app.domains.lowcode.workflow_models import WfProcessCc

    for uid in user_ids:
        if not uid:
            continue
        exists = (await db.execute(
            select(WfProcessCc.id).where(
                WfProcessCc.tenant_id == tenant_id,
                WfProcessCc.process_instance_id == process_instance_id,
                WfProcessCc.user_id == uid,
            ).limit(1)
        )).scalar_one_or_none()
        if exists:
            continue
        db.add(WfProcessCc(
            id=generate_uuid(),
            tenant_id=tenant_id,
            process_instance_id=process_instance_id,
            node_instance_id=None,
            user_id=uid,
            is_read=False,
        ))
    await db.flush()


@asynccontextmanager
async def _own_session():
    """通知专用的独立 session：与调用方的业务事务完全隔离。"""
    from app.database import async_session_factory
    session = async_session_factory()
    try:
        yield session
    finally:
        await session.close()


async def _user_name(db: AsyncSession, tenant_id: str, user_id: str | None) -> str:
    if not user_id:
        return ""
    try:
        from app.domains.auth.models import User
        u = (await db.execute(select(User).where(
            User.id == user_id, User.tenant_id == tenant_id,
        ))).scalar_one_or_none()
        return (u.real_name or u.username) if u else ""
    except Exception:
        return ""


def _skip_external_notify() -> bool:
    """本地冒烟/联调可设 WF_SKIP_EXTERNAL_NOTIFY=1，跳过钉钉等外呼（避免外网卡住审批）。

    站内通知不受此开关影响。
    """
    import os
    return os.environ.get("WF_SKIP_EXTERNAL_NOTIFY") == "1"


async def _resolve_form_code_for_notify(
    db: AsyncSession, inst: WfProcessInstance,
) -> str | None:
    """流程实例 → 表单模板 code（优先 biz_type，其次关联 FormInstance）。"""
    code = (getattr(inst, "biz_type", None) or "").strip()
    if code and code in _CC_NOTIFY_FIELD_PREFS:
        return code
    if code and code not in ("form_instance", "lowcode", "wf"):
        # 非预设表单也可能是真实 template code
        pass
    fid = getattr(inst, "form_instance_id", None)
    if not fid:
        return code or None
    try:
        from app.domains.lowcode.models import FormInstance, FormTemplate
        fi = await db.get(FormInstance, fid)
        if not fi or not fi.template_id:
            return code or None
        tpl = await db.get(FormTemplate, fi.template_id)
        if tpl and (tpl.code or "").strip():
            return tpl.code.strip()
    except Exception:
        pass
    return code or None


async def notify_tasks_created(
    tenant_id: str, inst: WfProcessInstance, task_ids: list[str],
) -> None:
    """审批节点激活/流转后，给新产生的待办人发站内通知 + 钉钉个人待办。

    对齐旧引擎 submit_approval 的通知行为：仅对 status=pending 的待办下发
    (顺序会签下 waiting 的后续审批人不打扰)。

    生产卡等已配置抄送卡字段的表单：钉钉工作通知同步发简道云式 OA 字段卡
    （下卡日期/所在部门/图纸编号），避免只有「某某提交了审批」一行字。
    """
    if not task_ids:
        return
    try:
        from app.domains.notification.service import send_notification
        from app.common.msg_integration import dispatch_todo

        skip_external = _skip_external_notify()
        async with _own_session() as db:
            tasks = (await db.execute(select(WfTaskInstance).where(
                WfTaskInstance.tenant_id == tenant_id,
                WfTaskInstance.id.in_(task_ids),
                WfTaskInstance.status == "pending",
            ))).scalars().all()
            if not tasks:
                return
            initiator = await _user_name(db, tenant_id, getattr(inst, "initiator_id", None))
            title = getattr(inst, "title", None) or getattr(inst, "biz_type", None) or "审批"
            inst_id = getattr(inst, "id", None)
            form_code = await _resolve_form_code_for_notify(db, inst) or ""
            form_rows: list[dict[str, str]] = []
            ding_oa_title: str | None = None
            author: str | None = None
            if form_code in _CC_NOTIFY_FIELD_PREFS:
                form_rows = await _cc_form_fields(db, tenant_id, inst)
                ding_oa_title = _CC_NOTIFY_TITLES.get(form_code)
                author = _fmt_cc_author(initiator)

            from app.domains.lowcode.workflow_models import WfNodeInstance
            ni_ids = [t.node_instance_id for t in tasks if t.node_instance_id]
            ni_by_id: dict[str, WfNodeInstance] = {}
            if ni_ids:
                for ni in (await db.execute(select(WfNodeInstance).where(
                    WfNodeInstance.tenant_id == tenant_id,
                    WfNodeInstance.id.in_(ni_ids),
                ))).scalars().all():
                    ni_by_id[ni.id] = ni

            for t in tasks:
                ni = ni_by_id.get(t.node_instance_id) if t.node_instance_id else None
                node_name = (getattr(ni, "node_name", None) or "").strip()
                if "发起人接收" in node_name:
                    n_title = f"【请确认】{title}"
                    n_content = "财务已完成开票，请确认接收并可下载发票附件/图片。"
                    todo_content = "财务已开票，请打开确认并可下载发票附件。"
                else:
                    n_title = f"【待审批】{title}"
                    n_content = f"{initiator} 提交了审批请求，请尽快处理。"
                    todo_content = f"{initiator} 提交了审批，请打开处理。"
                try:
                    await send_notification(
                        db=db, tenant_id=tenant_id, recipient_id=t.assignee_id,
                        type="approval_pending",
                        title=n_title,
                        content=n_content,
                        biz_type=NOTIFY_BIZ_TYPE, biz_id=inst_id,
                        sender_name=initiator or None,
                    )
                except Exception as e:
                    logger.warning("wf send_notification failed: %s", e)
                if skip_external:
                    continue
                try:
                    ding_title = ding_oa_title or n_title
                    ding_content = todo_content
                    if form_rows:
                        ding_content = "\n".join(
                            f"{r['key']}{'' if r['key'].endswith(':') else ':'} {r['value']}"
                            for r in form_rows
                        )
                    res = await dispatch_todo(
                        db, tenant_id, t.assignee_id,
                        ding_title,
                        ding_content,
                        link=f"/approvals?wf={inst_id}&task={t.id}",
                        mobile_link=f"/m/lowcode/approvals/{inst_id}?task={t.id}",
                        form=form_rows or None,
                        author=author,
                    )
                    todo_id = (res or {}).get("todo_id")
                    if todo_id:
                        t.dingtalk_todo_id = todo_id
                except Exception as e:
                    logger.warning("wf dispatch_todo failed: %s", e)
            await db.commit()
    except Exception as e:
        logger.warning("wf notify_tasks_created failed: %s", e)


async def complete_todo(tenant_id: str, assignee_id: str | None, todo_id: str | None) -> None:
    """完结指定用户名下的一条钉钉待办。转交场景下待办属于「原」审批人，需显式指定。"""
    if not assignee_id or not todo_id:
        return
    try:
        from app.common.msg_integration import complete_todo_for_user
        async with _own_session() as db:
            await complete_todo_for_user(db, tenant_id, assignee_id, todo_id)
    except Exception as e:
        logger.warning("wf complete_todo failed: %s", e)


async def complete_todos(tenant_id: str, task_ids: list[str]) -> None:
    """待办被处理/作废后，完结其钉钉个人待办，避免钉钉里一直挂着已处理项。"""
    if not task_ids:
        return
    try:
        from app.common.msg_integration import complete_todo_for_user
        async with _own_session() as db:
            tasks = (await db.execute(select(WfTaskInstance).where(
                WfTaskInstance.tenant_id == tenant_id,
                WfTaskInstance.id.in_(task_ids),
            ))).scalars().all()
            for t in tasks:
                todo_id = getattr(t, "dingtalk_todo_id", None)
                if not todo_id or not t.assignee_id:
                    continue
                try:
                    await complete_todo_for_user(db, tenant_id, t.assignee_id, todo_id)
                except Exception as e:
                    logger.warning("wf complete_todo failed: %s", e)
    except Exception as e:
        logger.warning("wf complete_todos failed: %s", e)


def _fmt_cc_author(name: str | None) -> str:
    """简道云抄送卡页脚：发起人 + 时分，如「炎蕊蕊 10:45」。"""
    from datetime import datetime
    now = datetime.now().strftime("%H:%M")
    who = (name or "").strip() or "系统"
    return f"{who} {now}"


def _biz_detail_to_form(detail: dict | None, *, limit: int = 4) -> list[dict[str, str]]:
    """把业务摘要 dict 转成钉钉 OA form 行。"""
    rows: list[dict[str, str]] = []
    if not detail:
        return rows
    for k, v in detail.items():
        if v is None or v == "" or v == "-":
            continue
        rows.append({"key": str(k), "value": str(v)})
        if len(rows) >= limit:
            break
    return rows


# 简道云抄送/知会卡：按表单定制标题与摘要列（对齐 JDY OA 样式）
_CC_NOTIFY_TITLES: dict[str, str] = {
    "prod_card_supplement": "「CRM-生产卡/补充流程」有新的流程待办事项",
}

# (field_id, 展示标签)；__drawing_no_formula__ 为虚拟列
_CC_NOTIFY_FIELD_PREFS: dict[str, list[tuple[str, str]]] = {
    "prod_card_supplement": [
        ("card_date", "下卡日期"),
        ("department", "所在部门"),
        ("__drawing_no_formula__", "图纸编号"),
    ],
    "payment_registration": [
        ("payment_date", "来款日期"),
        ("customer_name", "单位名称"),
        ("department", "部门"),
        ("payment_total", "来款合计"),
    ],
}


def _collect_ref_ids(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        out: list[str] = []
        for x in value:
            out.extend(_collect_ref_ids(x))
        return out
    if isinstance(value, dict):
        rid = value.get("id")
        return [str(rid)] if rid else []
    s = str(value).strip()
    return [s] if s else []


def _short_date_text(val) -> str:
    """日期字段抄送卡只展示 yyyy-MM-dd（对齐简道云）。"""
    s = str(val or "").strip()
    if not s:
        return ""
    if "T" in s:
        s = s.split("T", 1)[0]
    elif " " in s:
        s = s.split(" ", 1)[0]
    return s[:10] if len(s) >= 10 else s


def _prod_card_drawing_no(data: dict) -> str:
    """生产卡「图纸编号」：优先带出字段，其次查询引用。"""
    for k in ("no_drawing_no", "drawing_no_query"):
        v = data.get(k)
        if v in (None, "", [], {}):
            continue
        if isinstance(v, dict):
            return str(v.get("name") or v.get("label") or v.get("id") or "").strip()
        return str(v).strip()
    return ""


def _format_cc_field_value(
    field_type: str | None, value, label_maps: dict[str, dict[str, str]] | None,
) -> str:
    """表单字段 → 抄送卡可读文本（人员/部门 id 转名）。"""
    if value is None or value == "":
        return ""
    labels = label_maps or {}
    if field_type in ("person", "person_multi"):
        m = labels.get("users") or {}
        names = [m.get(i) or i for i in _collect_ref_ids(value)]
        return "、".join(n for n in names if n)
    if field_type in ("department", "department_multi"):
        m = labels.get("depts") or {}
        names = [m.get(i) or i for i in _collect_ref_ids(value)]
        return "、".join(n for n in names if n)
    if isinstance(value, dict):
        return str(value.get("name") or value.get("label") or value.get("text") or value)
    if isinstance(value, list):
        return "、".join(
            str(v.get("name") or v.get("label") or v.get("id") or v) if isinstance(v, dict) else str(v)
            for v in value
        )
    return str(value)


async def _cc_notify_label_maps(
    db: AsyncSession, tenant_id: str, field_defs: list, form_data: dict,
) -> dict[str, dict[str, str]]:
    """抄送卡所需的人员/部门 id → 显示名。"""
    from sqlalchemy import bindparam, text as sql_text

    person_ids: set[str] = set()
    dept_ids: set[str] = set()
    for fd in field_defs or []:
        if not isinstance(fd, dict):
            continue
        fid = fd.get("id")
        ftype = fd.get("type")
        if not fid or not ftype:
            continue
        val = form_data.get(fid)
        if ftype in ("person", "person_multi"):
            person_ids.update(_collect_ref_ids(val))
        elif ftype in ("department", "department_multi"):
            dept_ids.update(_collect_ref_ids(val))

    async def _map(sql: str, ids: set[str]) -> dict[str, str]:
        clean = [i for i in ids if i]
        if not clean:
            return {}
        stmt = sql_text(sql).bindparams(bindparam("ids", expanding=True))
        rows_db = (await db.execute(stmt, {"t": tenant_id, "ids": clean})).fetchall()
        return {str(r[0]): str(r[1] or "") for r in rows_db if r[0]}

    users = await _map(
        "SELECT id, COALESCE(NULLIF(real_name,''), username, id) FROM users "
        "WHERE tenant_id = :t AND id IN :ids",
        person_ids,
    )
    depts = await _map(
        "SELECT id, name FROM departments WHERE tenant_id = :t AND id IN :ids",
        dept_ids,
    )
    return {"users": users, "depts": depts}


async def _cc_form_fields_from_prefs(
    db: AsyncSession, tenant_id: str, form_code: str,
    data: dict, field_defs: list,
) -> list[dict[str, str]]:
    """按表单预设列顺序构建抄送摘要（对齐简道云字段表）。"""
    prefs = _CC_NOTIFY_FIELD_PREFS.get(form_code)
    if not prefs:
        return []
    types_by_id = {
        str(fd["id"]): str(fd.get("type") or "")
        for fd in (field_defs or [])
        if isinstance(fd, dict) and fd.get("id")
    }
    label_maps = await _cc_notify_label_maps(db, tenant_id, field_defs, data)
    rows: list[dict[str, str]] = []
    for fid_k, label in prefs:
        if fid_k == "__drawing_no_formula__":
            val = _prod_card_drawing_no(data)
        elif fid_k in ("card_date", "payment_date"):
            raw = data.get(fid_k)
            val = _short_date_text(raw) or _format_cc_field_value(
                types_by_id.get(fid_k), raw, label_maps,
            )
        else:
            val = _format_cc_field_value(
                types_by_id.get(fid_k), data.get(fid_k), label_maps,
            )
        if val in (None, "", "-"):
            continue
        rows.append({"key": label, "value": str(val)})
    return rows


async def _cc_process_name(db: AsyncSession, inst: WfProcessInstance) -> str:
    """流程展示名（对齐简道云「收款登记流程」）：优先流程定义名，其次实例标题。"""
    try:
        from app.domains.lowcode.workflow_models import WfProcessDefinition
        dfn_id = getattr(inst, "process_definition_id", None)
        if dfn_id:
            dfn = await db.get(WfProcessDefinition, dfn_id)
            if dfn and (dfn.name or "").strip():
                return dfn.name.strip()
    except Exception:
        pass
    return (getattr(inst, "title", None) or getattr(inst, "biz_type", None) or "流程").strip()


async def _cc_form_fields(db: AsyncSession, tenant_id: str, inst: WfProcessInstance) -> list[dict[str, str]]:
    """抄送卡字段摘要：业务单据用 biz_detail；表单流取若干展示字段。"""
    # 业务单据
    if getattr(inst, "biz_type", None) and getattr(inst, "biz_id", None):
        try:
            from app.domains.approval.service import _resolve_biz_detail
            detail = await _resolve_biz_detail(db, tenant_id, inst.biz_type, inst.biz_id) or {}
            # 线索优先挑简道云常见三列
            if inst.biz_type == "lead":
                prefer = ("项目名称", "公司名称", "申报人", "申报时间", "项目编号", "行业")
                ordered: dict = {}
                for k in prefer:
                    if k in detail and detail[k] not in (None, "", "-"):
                        ordered[k] = detail[k]
                for k, v in detail.items():
                    if k not in ordered:
                        ordered[k] = v
                return _biz_detail_to_form(ordered, limit=4)
            return _biz_detail_to_form(detail, limit=4)
        except Exception as e:
            logger.debug("cc form from biz_detail failed: %s", e)

    # 表单实例
    fid = getattr(inst, "form_instance_id", None)
    if not fid:
        return []
    try:
        from app.domains.lowcode.models import FormInstance, FormTemplate
        fi = await db.get(FormInstance, fid)
        if not fi or not isinstance(fi.form_data, dict):
            return []
        data = fi.form_data
        form_code = getattr(inst, "biz_type", None)
        if not form_code and fi.template_id:
            tpl = await db.get(FormTemplate, fi.template_id)
            if tpl and tpl.code:
                form_code = tpl.code
        if not form_code or form_code not in _CC_NOTIFY_FIELD_PREFS:
            # biz_type 可能不是模板 code，再按 template 解析一次
            if fi.template_id:
                tpl = await db.get(FormTemplate, fi.template_id)
                if tpl and tpl.code and tpl.code in _CC_NOTIFY_FIELD_PREFS:
                    form_code = tpl.code
        if form_code and form_code in _CC_NOTIFY_FIELD_PREFS:
            rows = await _cc_form_fields_from_prefs(
                db, tenant_id, form_code, data, fi.field_definitions or [],
            )
            if rows:
                return rows
        labels: dict[str, str] = {}
        for fd in (fi.field_definitions or []):
            if isinstance(fd, dict) and fd.get("id"):
                labels[str(fd["id"])] = str(fd.get("label") or fd.get("title") or fd["id"])
        rows: list[dict[str, str]] = []
        for fid_k, val in data.items():
            if val in (None, "", [], {}):
                continue
            if isinstance(val, (list, dict)):
                continue
            label = labels.get(str(fid_k), str(fid_k))
            rows.append({"key": label, "value": str(val)})
            if len(rows) >= 4:
                break
        return rows
    except Exception as e:
        logger.debug("cc form from form_instance failed: %s", e)
        return []


async def notify_cc_users(
    tenant_id: str, inst: WfProcessInstance, user_ids: list[str], node_name: str | None = None,
) -> None:
    """抄送节点激活后通知被抄送人（站内 + 钉钉 OA 卡，对齐简道云抄送样式，不建钉钉待办）。

    钉钉卡片：头「威猛云」+ 标题「抄送：「流程名」有新的流程处理结果抄送给你」
    + 关键字段表 + 发起人时分；点击整卡查看详情。
    """
    if not user_ids:
        return
    try:
        from app.domains.notification.service import send_notification
        from app.common.msg_integration import dispatch_cc_notify

        skip_external = _skip_external_notify()
        async with _own_session() as db:
            process_name = await _cc_process_name(db, inst)
            initiator = await _user_name(db, tenant_id, getattr(inst, "initiator_id", None))
            author = _fmt_cc_author(initiator)
            form_rows = await _cc_form_fields(db, tenant_id, inst)

            form_code = await _resolve_form_code_for_notify(db, inst)
            custom_title = _CC_NOTIFY_TITLES.get(form_code or "")
            if custom_title:
                ding_title = custom_title
            else:
                # 简道云同款主标题
                ding_title = f"抄送：「{process_name}」有新的流程处理结果抄送给你"
            # OA content 作兜底；有 form 时钉钉优先展示 form
            ding_content = "请点击查看详情"
            if form_rows:
                ding_content = "\n".join(
                    f"{r['key']}{'' if r['key'].endswith(':') else ':'} {r['value']}"
                    for r in form_rows
                )

            # 站内通知统一走 approval_cc + wf_instance，与审批中心「抄送我的」(wf_process_cc) 对齐
            ntype = "approval_cc"
            biz_type = NOTIFY_BIZ_TYPE
            biz_id = inst.id
            link = f"/approvals?tab=cc&wf={inst.id}"
            mobile_link = f"/m/approvals?tab=cc&wf={inst.id}"
            station_title = ding_title
            station_content = ding_content

            if inst.biz_type == "lead" and inst.biz_id:
                from app.domains.lead.models import Lead
                ld = (await db.execute(select(Lead).where(
                    Lead.id == inst.biz_id, Lead.tenant_id == tenant_id,
                ))).scalar_one_or_none()
                lead_title = (ld.title if ld else None) or process_name
                attacked = bool(ld and getattr(ld, "review_status", None) == "attacked")
                if attacked:
                    station_title = f"线索已标记袭击: {lead_title}"
                    station_content = (
                        f"线索「{lead_title}」经情报审批已标记为袭击，不可转商机，请知悉。"
                    )
                else:
                    station_title = ding_title
                    station_content = (
                        f"线索「{lead_title}」相关流程已抄送您。"
                        f"请打开审批中心「抄送我的」查看；可自行选择是否转商机。"
                    )
            elif node_name == "已提交开票申请":
                station_title = f"开票申请已提交: {process_name}"
                station_content = "您名下有新的开票申请已提交，请知悉。"
                ding_title = station_title
                ding_content = station_content
            elif node_name == "发票已开具可下载":
                station_title = f"发票已开具: {process_name}"
                station_content = (
                    "财务已完成开票，请打开「开票申请」或审批详情下载发票附件/图片。"
                )
                ding_title = station_title
                ding_content = station_content

            # 兜底：若引擎漏写 wf_process_cc，补齐，避免「通知有、抄送我的空」
            await _ensure_process_cc_rows(db, tenant_id, inst.id, user_ids)

            for uid in user_ids:
                try:
                    await send_notification(
                        db=db, tenant_id=tenant_id, recipient_id=uid,
                        type=ntype, title=station_title, content=station_content,
                        biz_type=biz_type, biz_id=biz_id,
                        sender_name=initiator or None,
                    )
                except Exception as e:
                    logger.warning("wf cc send_notification failed: %s", e)
                if skip_external:
                    continue
                try:
                    await dispatch_cc_notify(
                        db, tenant_id, uid, ding_title, ding_content,
                        link=link, mobile_link=mobile_link,
                        form=form_rows or None,
                        author=author,
                    )
                except Exception as e:
                    logger.warning("wf cc dispatch_cc_notify failed: %s", e)
            await db.commit()
    except Exception as e:
        logger.warning("wf notify_cc_users failed: %s", e)


async def notify_flow_finished(
    tenant_id: str, inst: WfProcessInstance, status: str, reason: str | None = None,
) -> None:
    """流程结束后通知发起人（对齐旧引擎 decide 的 approval_decided 通知）。

    业务员（线索负责人）的推送改由可视化流程「抄送」节点配置，不再在此硬编码。
    """
    if not inst.initiator_id:
        return
    label = {"completed": "已通过", "rejected": "已驳回", "withdrawn": "已撤回", "returned": "已退回"}.get(status)
    if not label:
        return
    try:
        from app.domains.notification.service import send_notification
        content = f"您提交的「{inst.title or inst.biz_type or '审批'}」{label}"
        if reason:
            content = f"{content}：{reason}"
        async with _own_session() as db:
            await send_notification(
                db=db, tenant_id=tenant_id, recipient_id=inst.initiator_id,
                type="approval_decided",
                title=f"审批{label}: {inst.title or inst.biz_type or ''}",
                content=content,
                biz_type=NOTIFY_BIZ_TYPE, biz_id=inst.id,
            )
            await db.commit()
    except Exception as e:
        logger.warning("wf notify_flow_finished failed: %s", e)


async def notify_withdrawn(
    tenant_id: str, inst: WfProcessInstance, assignee_ids: list[str], actor: dict,
) -> None:
    """发起人撤回后，通知当前正在处理的审批人（对齐旧引擎 approval_withdrawn 通知）。"""
    if not assignee_ids:
        return
    try:
        from app.domains.notification.service import send_notification
        actor_name = actor.get("real_name") or actor.get("username") or ""
        async with _own_session() as db:
            for aid in assignee_ids:
                try:
                    await send_notification(
                        db=db, tenant_id=tenant_id, recipient_id=aid,
                        type="approval_withdrawn",
                        title=f"审批已撤回: {inst.title or inst.biz_type or ''}",
                        content=f"发起人 {actor_name} 撤回了该审批，无需处理。",
                        biz_type=NOTIFY_BIZ_TYPE, biz_id=inst.id,
                        sender_name=actor_name or None,
                    )
                except Exception as e:
                    logger.warning("wf withdraw notify failed: %s", e)
            await db.commit()
    except Exception as e:
        logger.warning("wf notify_withdrawn failed: %s", e)


async def notify_empty_auto_approved(
    tenant_id: str, inst: WfProcessInstance, node_name: str,
) -> None:
    """审批节点解析不出任何审批人而被自动放行时，通知发起人。

    这条通知存在的意义是「让静默放行变得可见」：节点配置错误或审批人全部离职时，
    单据会在无人审批的情况下自动通过，若不通知则没有任何人会察觉。
    """
    if not inst.initiator_id:
        return
    try:
        from app.domains.notification.service import send_notification
        async with _own_session() as db:
            await send_notification(
                db=db, tenant_id=tenant_id, recipient_id=inst.initiator_id,
                type="system",
                title=f"审批节点无审批人已自动通过: {inst.title or inst.biz_type or ''}",
                content=f"节点「{node_name}」未解析到任何有效审批人，已按空审批人策略自动通过。"
                        f"请联系管理员检查该流程的审批人配置。",
                biz_type=NOTIFY_BIZ_TYPE, biz_id=inst.id,
            )
            await db.commit()
    except Exception as e:
        logger.warning("wf notify_empty_auto_approved failed: %s", e)


async def notify_review_flow_unavailable(
    tenant_id: str, biz_type: str, biz_id: str, submitter_id: str | None, title: str,
) -> None:
    """业务已切到新引擎但一条可用流程都起不来时，通知提交人。

    这种情况通常是管理员把该 biz_type 的流程删了/取消发布了。单据仍按免审放行以免卡死，
    但必须让人知道审核被跳过了 —— 否则审核门禁形同虚设且无人察觉。
    """
    if not submitter_id:
        return
    try:
        from app.domains.notification.service import send_notification
        async with _own_session() as db:
            await send_notification(
                db=db, tenant_id=tenant_id, recipient_id=submitter_id,
                type="system",
                title=f"审核流程未配置，已跳过审核: {title}",
                content=f"业务类型「{biz_type}」没有可用的已发布审批流程，本次提交已直接放行。"
                        f"请联系管理员在「扩展平台→流程设计」中恢复或新建该业务的审批流程。",
                biz_type=NOTIFY_BIZ_TYPE, biz_id=biz_id,
            )
            await db.commit()
    except Exception as e:
        logger.warning("wf notify_review_flow_unavailable failed: %s", e)


async def dispatch_msg(tenant_id: str, title: str, content: str) -> None:
    """群消息/webhook 推送（非关键路径，永不抛出）。"""
    if _skip_external_notify():
        return
    try:
        from app.common.msg_integration import dispatch_message
        async with _own_session() as db:
            await dispatch_message(db, tenant_id, title, content, msg_type="approval")
    except Exception as e:
        logger.warning("wf dispatch_message failed: %s", e)


async def enqueue_wf_event(
    db: AsyncSession, tenant_id: str, event_type: str, inst: WfProcessInstance,
    extra: dict | None = None,
) -> None:
    """写 outbox 领域事件。

    这是唯一使用调用方 session 的函数 —— outbox 事件必须与业务变更同一事务原子提交，
    否则会出现「状态变了但事件没发」或反之。必须在 db.commit() 之前调用。
    """
    try:
        from app.domains.outbox.service import enqueue_event
        from app.domains.outbox.schemas import OutboxEventCreate
        payload = {
            "process_instance_id": inst.id,
            "form_instance_id": inst.form_instance_id,
            "biz_type": inst.biz_type,
            "biz_id": inst.biz_id,
            "title": inst.title,
            "status": inst.status,
            "initiator_id": inst.initiator_id,
        }
        if extra:
            payload.update(extra)
        await enqueue_event(db, tenant_id, OutboxEventCreate(
            event_type=event_type,
            aggregate_type="wf_process_instance",
            aggregate_id=inst.id,
            payload_json=payload,
        ))
    except Exception as e:
        logger.warning("wf outbox enqueue failed for %s: %s", event_type, e)


async def audit(
    db: AsyncSession, tenant_id: str, inst: WfProcessInstance, user: dict,
    action: str, summary: str,
) -> None:
    """写审计日志（旧引擎有 log_action，新引擎此前只有内部 WfTaskActionLog）。

    log_action 本身就在自己的 session 里写，db 参数仅为签名稳定性保留。
    """
    try:
        from app.domains.audit.service import log_action
        await log_action(
            db, tenant_id=tenant_id, user_id=user.get("sub"),
            user_name=user.get("real_name") or user.get("username"),
            action=action,
            resource_type=inst.biz_type or "wf_process_instance",
            resource_id=inst.biz_id or inst.id,
            summary=summary,
        )
    except Exception as e:
        logger.warning("wf audit log failed: %s", e)
