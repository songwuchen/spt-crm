"""流程推进引擎(统一入口)。

移植思想自 spt-lowcode services/workflow/engine.py,MVP 聚焦核心闭环:
- 节点类型: start / approval / cc / end(条件分支挂在连线 route.condition 上,无需独立 condition 节点);
- 多人模式: or_sign(或签,一人过即过) / countersign(会签,全过才过) / sequential(顺序会签);
- 动作: submit / approve / reject / withdraw / transfer / comment;
- 空审批人策略: auto_approve(跳过) / terminate(终止驳回);
- 待办为独立 WfTaskInstance,version 乐观锁防并发重复审批;全程留痕 WfTaskActionLog。
- 并行网关: parallel(fork,激活所有出边分支) + merge(AND-join,advisory lock 串行化到达记账);
- 超时(SLA): 审批节点 timeout={hours,action},由 reminder_worker 扫描触发 fire_timeout;
- 催办: 发起人对进行中待办人发提醒(urge)。

统一入口保证: 状态推进 + 待办生成/作废 + 日志 + (表单实例)回写 集中处理,避免散落。
高级能力(加签/退回指定节点/子流程/代理落地)见 act();其余按需迭代。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text as sa_text
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, VALIDATION_ERROR, BUSINESS_ERROR, FORBIDDEN
from app.database import generate_uuid
from app.domains.lowcode.approver_resolver import ApproverResolver, ApprovalContext, NoApproverError
from app.domains.lowcode.workflow_models import (
    WfProcessDefinitionVersion, WfProcessInstance, WfNodeInstance,
    WfTaskInstance, WfTaskActionLog, WfProcessComment, WfProcessCc,
)
from app.domains.lowcode.models import FormInstance


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ==================== 条件评估(分支路由) ====================

def _is_empty(v: Any) -> bool:
    return v is None or v == "" or (isinstance(v, list) and len(v) == 0)


def _cmp(actual: Any, op: str, expected: Any) -> bool:
    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    if op == "eq":
        return str(actual) == str(expected) or actual == expected
    if op == "ne":
        return not (str(actual) == str(expected) or actual == expected)
    if op == "is_empty":
        return _is_empty(actual)
    if op == "is_not_empty":
        return not _is_empty(actual)
    if op in ("gt", "gte", "lt", "lte"):
        a, b = num(actual), num(expected)
        if a is None or b is None:
            return False
        return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
    if op == "in":
        lst = expected if isinstance(expected, list) else str(expected).split(",")
        return any(str(actual) == str(e) for e in lst)
    if op == "not_in":
        lst = expected if isinstance(expected, list) else str(expected).split(",")
        return all(str(actual) != str(e) for e in lst)
    if op == "contains":
        return str(expected) in str(actual)
    return False


def evaluate_condition(cond: dict | None, form_data: dict) -> bool:
    """支持前端 RuleEngine 格式 {rel:'and'|'or', cond:[{field,operator,value}]} 及单条件。"""
    if not cond:
        return True  # 无条件 = 默认边,恒真
    nodes = cond.get("cond")
    if isinstance(nodes, list) and nodes:
        rel = cond.get("rel", "and")
        results = []
        for n in nodes:
            if "cond" in n:
                results.append(evaluate_condition(n, form_data))
            else:
                results.append(_cmp(form_data.get(n.get("field")), n.get("operator", "eq"), n.get("value")))
        return all(results) if rel == "and" else any(results)
    if cond.get("field"):
        return _cmp(form_data.get(cond["field"]), cond.get("operator", "eq"), cond.get("value"))
    return True


# ==================== 引擎 ====================

class WorkflowEngine:
    def __init__(self, db: AsyncSession, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        # 延迟通知队列: 审批事务内只登记意图,待 db.commit() 成功后再真正下发。
        # 这样通知失败不会回滚审批,也不会给尚未落库的待办发推送。
        self._notify: list[tuple] = []
        # SLA 超时场景由 reminder_worker 负责给发起人发「因超时…」的通知(它才有超时上下文),
        # 此时抑制引擎自己的流程结束通知,避免发起人收到两条讲同一件事的推送。
        self._suppress_finished_notify = False

    # ---------- 通知(延迟到提交后下发) ----------

    def _queue(self, kind: str, *args) -> None:
        self._notify.append((kind, *args))

    async def flush_notifications(self, inst: WfProcessInstance | None = None) -> None:
        """提交成功后统一下发通知。任何失败只记日志,绝不外抛。

        必须在业务事务 commit **之后**调用。引擎内部各动作(submit/act/withdraw)已自行
        调用;不自行提交的 fire_timeout 由其调用方(reminder_worker)在提交后调用。
        """
        if not self._notify:
            return
        pending, self._notify = self._notify, []
        from app.domains.lowcode import wf_notify
        for item in pending:
            kind = item[0]
            try:
                if kind == "tasks_created":
                    target = item[2] if len(item) > 2 and item[2] is not None else inst
                    if target is not None:
                        await wf_notify.notify_tasks_created(self.tenant_id, target, item[1])
                elif kind == "todos_done":
                    await wf_notify.complete_todos(self.tenant_id, item[1])
                elif kind == "todo_done_explicit":
                    await wf_notify.complete_todo(self.tenant_id, item[1], item[2])
                elif kind == "finished":
                    target = item[3] if len(item) > 3 and item[3] is not None else inst
                    if target is not None and not self._suppress_finished_notify:
                        await wf_notify.notify_flow_finished(self.tenant_id, target, item[1], item[2])
                elif kind == "withdrawn":
                    target = item[3] if len(item) > 3 and item[3] is not None else inst
                    if target is not None:
                        await wf_notify.notify_withdrawn(self.tenant_id, target, item[1], item[2])
                elif kind == "empty_auto_approved":
                    target = item[2] if len(item) > 2 and item[2] is not None else inst
                    if target is not None:
                        await wf_notify.notify_empty_auto_approved(self.tenant_id, target, item[1])
            except Exception:  # pragma: no cover - 通知永不影响主流程
                import logging
                logging.getLogger("spt_crm.lowcode.workflow_engine").warning(
                    "flush notification failed for %s", kind, exc_info=True)

    # ---------- 版本图辅助 ----------

    def _nodes_by_id(self, version: WfProcessDefinitionVersion) -> dict[str, dict]:
        return {n["id"]: n for n in (version.node_definitions or [])}

    def _start_node(self, version: WfProcessDefinitionVersion) -> dict | None:
        for n in version.node_definitions or []:
            if n.get("type") == "start":
                return n
        return None

    def _approver_rule(self, version: WfProcessDefinitionVersion, node: dict) -> dict | None:
        rule = node.get("approver_rule") or (node.get("config") or {}).get("approver_rule")
        if rule:
            return {**rule, "node_id": node["id"]}
        for r in version.approver_rules or []:
            if r.get("node_id") == node["id"]:
                return r
        return None

    def _outgoing(self, version: WfProcessDefinitionVersion, node_id: str) -> list[dict]:
        return [r for r in (version.route_definitions or []) if r.get("source") == node_id]

    def _next_targets(self, version: WfProcessDefinitionVersion, node_id: str, form_data: dict) -> list[str]:
        """按连线条件选下一节点: 命中条件的边优先;都不命中则走无条件(默认/else)边。"""
        routes = self._outgoing(version, node_id)
        matched = [r["target"] for r in routes if r.get("condition") and evaluate_condition(r["condition"], form_data)]
        if matched:
            return matched
        return [r["target"] for r in routes if not r.get("condition")]

    # ---------- 提交(发起流程) ----------

    async def submit(
        self, definition_id: str, version: WfProcessDefinitionVersion,
        initiator: dict, form_instance_id: str | None = None,
        form_data: dict | None = None, title: str | None = None,
        biz_type: str | None = None, biz_id: str | None = None,
        nominated: dict | None = None,
    ) -> WfProcessInstance:
        start = self._start_node(version)
        if not start:
            raise BusinessException(code=VALIDATION_ERROR, message="流程缺少开始节点")

        inst = WfProcessInstance(
            id=generate_uuid(), tenant_id=self.tenant_id,
            process_definition_id=definition_id, process_version_id=version.id,
            form_instance_id=form_instance_id, biz_type=biz_type, biz_id=biz_id,
            title=title, initiator_id=initiator.get("sub"),
            status="running", started_at=_now(),
            nominated_approvers=nominated or None,
        )
        self.db.add(inst)
        await self.db.flush()
        self._log(inst.id, None, None, initiator, "submit", None)

        ctx = ApprovalContext(initiator_id=initiator.get("sub"), form_data=form_data or {}, nominated=nominated or {})
        # 生命周期事件必须按发生顺序入队: submitted 要早于 _advance 可能产生的
        # approved/rejected,否则流程在提交过程中直接走完时下游会先收到结束事件。
        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(self.db, self.tenant_id, "workflow.submitted", inst)
        await self._advance(inst, version, start["id"], ctx)
        await self.db.commit()
        await self.db.refresh(inst)
        await self.flush_notifications(inst)
        await self._audit(inst, initiator, "submit")
        return inst

    async def _audit(self, inst: WfProcessInstance, actor: dict, action: str) -> None:
        from app.domains.lowcode import wf_notify
        labels = {"submit": "提交审批", "approve": "审批通过", "reject": "审批驳回", "withdraw": "撤回审批"}
        await wf_notify.audit(
            self.db, self.tenant_id, inst, actor, f"wf_{action}",
            f"{labels.get(action, action)}: {inst.title or inst.biz_type or ''}",
        )

    # ---------- 推进到下一节点 ----------

    async def _advance(self, inst: WfProcessInstance, version: WfProcessDefinitionVersion,
                       from_node_id: str, ctx: ApprovalContext) -> None:
        targets = self._next_targets(version, from_node_id, ctx.form_data)
        nodes = self._nodes_by_id(version)
        for tid in targets:
            node = nodes.get(tid)
            if not node:
                continue
            await self._activate_node(inst, version, node, ctx)
            if inst.status != "running":
                return  # 已结束(end / terminate)

    async def _activate_node(self, inst: WfProcessInstance, version: WfProcessDefinitionVersion,
                             node: dict, ctx: ApprovalContext) -> None:
        ntype = node.get("type")
        if ntype == "end":
            await self._complete_instance(inst, "completed")
            return
        if ntype == "cc":
            await self._create_cc(inst, version, node, ctx)
            await self._advance(inst, version, node["id"], ctx)
            return
        if ntype == "approval":
            await self._activate_approval(inst, version, node, ctx)
            return
        if ntype == "parallel":
            await self._activate_parallel(inst, version, node, ctx)
            return
        if ntype == "merge":
            await self._arrive_merge(inst, version, node, ctx)
            return
        # 其它类型(condition 等)视为直通(分支条件挂在连线上)
        await self._advance(inst, version, node["id"], ctx)

    async def _resolve_approvers(self, version, node, ctx) -> list[str]:
        rule = self._approver_rule(version, node)
        if not rule:
            return []
        try:
            return await ApproverResolver(self.db, self.tenant_id).resolve(rule, ctx)
        except NoApproverError:
            return []

    async def _activate_approval(self, inst, version, node, ctx) -> None:
        approvers = await self._resolve_approvers(version, node, ctx)
        if not approvers:
            strategy = node.get("empty_strategy") or (node.get("config") or {}).get("empty_strategy") or "auto_approve"
            node_name = node.get("name") or "审批"
            if strategy == "terminate":
                await self._complete_instance(inst, "rejected", reason=f"节点「{node_name}」无审批人,流程终止")
                self._log(inst.id, None, None, {"sub": "system"}, "auto_reject", "无审批人,流程终止")
                return
            # auto_approve: 跳过本节点。这是「无人审批却放行」的高风险路径 —— 必须留痕并
            # 通知发起人，否则单据会在无人知情的情况下被自动置为已通过(历史上的静默缺陷)。
            self._log(inst.id, None, None, {"sub": "system"}, "auto_approve", "无审批人,自动通过")
            self._queue("empty_auto_approved", node_name, inst)
            await self._advance(inst, version, node["id"], ctx)
            return

        mode = node.get("multi_mode") or (node.get("config") or {}).get("multi_mode") or "or_sign"
        # 超时配置(可选): {hours, action: notify/auto_approve/auto_reject/auto_transfer, transfer_to?}
        timeout = node.get("timeout") or (node.get("config") or {}).get("timeout")
        cfg: dict = {"mode": mode}
        if isinstance(timeout, dict) and timeout.get("hours"):
            cfg["timeout"] = timeout
        ni = WfNodeInstance(
            id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
            node_def_id=node["id"], node_type="approval", node_name=node.get("name") or "审批",
            status="running", config=cfg, started_at=_now(),
        )
        self.db.add(ni)
        await self.db.flush()

        fresh: list[str] = []
        for idx, uid in enumerate(approvers):
            # 顺序会签: 仅首个待办 pending,其余 waiting;或签/会签: 全部 pending
            status = "pending"
            if mode == "sequential" and idx > 0:
                status = "waiting"
            tid = generate_uuid()
            self.db.add(WfTaskInstance(
                id=tid, tenant_id=self.tenant_id, process_instance_id=inst.id,
                node_instance_id=ni.id, assignee_id=uid, status=status, task_order=idx,
            ))
            if status == "pending":
                fresh.append(tid)
        await self.db.flush()
        # 待办已落库,登记通知(站内 + 钉钉待办),提交后统一下发
        self._queue("tasks_created", fresh, inst)

    async def _create_cc(self, inst, version, node, ctx) -> None:
        users = await self._resolve_approvers(version, node, ctx)
        ni = WfNodeInstance(
            id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
            node_def_id=node["id"], node_type="cc", node_name=node.get("name") or "抄送",
            status="completed", config={}, started_at=_now(), completed_at=_now(),
        )
        self.db.add(ni)
        await self.db.flush()
        for uid in users:
            self.db.add(WfProcessCc(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                node_instance_id=ni.id, user_id=uid, is_read=False,
            ))

    # ---------- 并行网关(fork / AND-join) ----------

    async def _activate_parallel(self, inst, version, node, ctx) -> None:
        """并行网关(fork): 记录网关节点并激活全部出边分支(忽略连线条件,全部并行)。"""
        ni = WfNodeInstance(
            id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
            node_def_id=node["id"], node_type="parallel", node_name=node.get("name") or "并行",
            status="completed", config={}, started_at=_now(), completed_at=_now(),
        )
        self.db.add(ni)
        await self.db.flush()
        nodes = self._nodes_by_id(version)
        for r in self._outgoing(version, node["id"]):
            tnode = nodes.get(r.get("target"))
            if not tnode:
                continue
            await self._activate_node(inst, version, tnode, ctx)
            if inst.status != "running":
                return

    async def _arrive_merge(self, inst, version, node, ctx) -> None:
        """并行汇聚(AND-join): 每条分支到达时记账,全部到达后再推进。

        并发到达(两条分支的审批人同时通过)用事务级 advisory lock 串行化,
        防止重复建 merge 实例或漏计到达数。expected = 指向该节点的入边数。
        """
        expected = len([r for r in (version.route_definitions or []) if r.get("target") == node["id"]])
        if expected <= 1:
            # 退化: 单入边等同直通
            self.db.add(WfNodeInstance(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                node_def_id=node["id"], node_type="merge", node_name=node.get("name") or "汇聚",
                status="completed", config={"arrived": 1, "expected": expected}, started_at=_now(), completed_at=_now(),
            ))
            await self.db.flush()
            await self._advance(inst, version, node["id"], ctx)
            return
        await self.db.execute(sa_text("SELECT pg_advisory_xact_lock(hashtext(:k)::bigint)")
                              .bindparams(k=f"wfmerge:{inst.id}:{node['id']}"))
        ni = (await self.db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.node_def_id == node["id"],
            WfNodeInstance.status == "running",
        ))).scalar_one_or_none()
        if ni is None:
            ni = WfNodeInstance(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                node_def_id=node["id"], node_type="merge", node_name=node.get("name") or "汇聚",
                status="running", config={"arrived": 1, "expected": expected}, started_at=_now(),
            )
            self.db.add(ni)
            await self.db.flush()
            arrived = 1
        else:
            cfg = dict(ni.config or {})
            arrived = int(cfg.get("arrived", 0)) + 1
            cfg["arrived"] = arrived
            ni.config = cfg
            flag_modified(ni, "config")
        done = arrived >= expected
        if not done:
            # 防止漏到达永久卡住(某并行分支因条件走向未到达 merge): 若已无其它在途分支
            # (除本 merge 外无 running 节点、且全实例无 pending/waiting 待办),视为已全部收敛。
            other_running = (await self.db.execute(select(WfNodeInstance.id).where(
                WfNodeInstance.process_instance_id == inst.id,
                WfNodeInstance.status == "running",
                WfNodeInstance.id != ni.id,
            ).limit(1))).scalar_one_or_none()
            live_task = (await self.db.execute(select(WfTaskInstance.id).where(
                WfTaskInstance.process_instance_id == inst.id,
                WfTaskInstance.status.in_(["pending", "waiting"]),
            ).limit(1))).scalar_one_or_none()
            done = other_running is None and live_task is None
        if done:
            ni.status = "completed"
            ni.completed_at = _now()
            await self.db.flush()
            await self._advance(inst, version, node["id"], ctx)

    # ---------- 审批动作 ----------

    async def act(self, task_id: str, actor: dict, action: str, opinion: str | None = None,
                  transfer_to: str | None = None, return_to: str | None = None) -> None:
        task = (await self.db.execute(
            select(WfTaskInstance).where(
                WfTaskInstance.id == task_id, WfTaskInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if not task:
            raise BusinessException(code=NOT_FOUND, message="待办不存在")
        delegated = False
        if task.assignee_id != actor.get("sub"):
            # 允许有效代理人代办委托人的待办（代理审批）
            from app.domains.organization.models import UserAgent
            now = _now()
            agent_ok = (await self.db.execute(select(UserAgent.id).where(
                UserAgent.tenant_id == self.tenant_id, UserAgent.user_id == task.assignee_id,
                UserAgent.agent_id == actor.get("sub"), UserAgent.status == "active",
                UserAgent.start_time <= now, UserAgent.end_time >= now,
            ).limit(1))).scalar_one_or_none()
            if not agent_ok:
                raise BusinessException(code=FORBIDDEN, message="非当前待办的处理人")
            delegated = True
        if task.status != "pending":
            raise BusinessException(code=BUSINESS_ERROR, message="该待办已处理")
        if delegated and action in ("approve", "reject") and opinion is not None:
            opinion = f"{opinion}（代理审批）"

        inst = await self.db.get(WfProcessInstance, task.process_instance_id)
        if not inst or inst.status != "running":
            raise BusinessException(code=BUSINESS_ERROR, message="流程已结束")
        version = await self.db.get(WfProcessDefinitionVersion, inst.process_version_id)
        ctx = ApprovalContext(initiator_id=inst.initiator_id, form_data=await self._form_data(inst),
                              nominated=inst.nominated_approvers or {})

        if action == "comment":
            self.db.add(WfProcessComment(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                user_id=actor.get("sub"), user_name=actor.get("real_name"), content=opinion or "",
            ))
            await self.db.commit()
            return

        if action == "transfer":
            if not transfer_to:
                raise BusinessException(code=VALIDATION_ERROR, message="转交需指定接收人")
            # 钉钉待办挂在「原」审批人名下，必须先按原审批人完结，再给接收人重新下发，
            # 否则原审批人的钉钉里会一直留着一条已经不属于他的待办。
            self._queue("todo_done_explicit", task.assignee_id, getattr(task, "dingtalk_todo_id", None))
            task.assignee_id = transfer_to
            task.dingtalk_todo_id = None
            task.version += 1
            self._log(inst.id, task.node_instance_id, task.id, actor, "transfer", opinion)
            self._queue("tasks_created", [task.id], inst)
            await self.db.commit()
            await self.flush_notifications(inst)
            return

        if action == "return":
            # 退回到指定审批节点：作废当前待办/节点，重新激活目标节点，流程仍进行中
            target = self._nodes_by_id(version).get(return_to or "")
            if not target or target.get("type") != "approval":
                raise BusinessException(code=VALIDATION_ERROR, message="退回目标必须是有效的审批节点")
            task.status = "returned"
            task.opinion = opinion
            task.action_at = _now()
            task.version += 1
            self._log(inst.id, task.node_instance_id, task.id, actor, "return", opinion)
            self._queue("todo_done_explicit", task.assignee_id, getattr(task, "dingtalk_todo_id", None))
            await self._return_to_node(inst, version, target, ctx)
            await self.db.commit()
            await self.flush_notifications(inst)
            return

        task.status = "approved" if action == "approve" else "rejected"
        task.opinion = opinion
        task.action_at = _now()
        task.version += 1
        self._log(inst.id, task.node_instance_id, task.id, actor, action, opinion)
        # 本人这条待办已处理,完结其钉钉待办
        self._queue("todo_done_explicit", task.assignee_id, getattr(task, "dingtalk_todo_id", None))

        if action == "reject":
            # 驳回意见随流程结束回写到业务表(如 leads.reject_reason)
            await self._reject_flow(inst, reason=opinion)
            await self.db.commit()
            await self.flush_notifications(inst)
            await self._audit(inst, actor, "reject")
            return

        # approve → 判断节点是否完成
        await self._on_task_approved(inst, version, task, ctx)
        await self.db.commit()
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "approve")

    async def _on_task_approved(self, inst, version, task, ctx) -> None:
        ni = await self.db.get(WfNodeInstance, task.node_instance_id)
        mode = (ni.config or {}).get("mode", "or_sign")
        siblings = (await self.db.execute(
            select(WfTaskInstance).where(WfTaskInstance.node_instance_id == ni.id)
        )).scalars().all()

        node_done = False
        if mode == "or_sign":
            cancelled: list[str] = []
            for s in siblings:
                if s.id != task.id and s.status in ("pending", "waiting"):
                    s.status = "cancelled"
                    cancelled.append(s.id)
            # 或签一人通过即结束,其余审批人的钉钉待办要一并完结
            self._queue("todos_done", cancelled)
            node_done = True
        elif mode == "countersign":
            node_done = all(s.status == "approved" for s in siblings)
        elif mode == "sequential":
            nxt = [s for s in siblings if s.status == "waiting"]
            if nxt:
                nxt.sort(key=lambda s: s.task_order)
                nxt[0].status = "pending"
                # 顺序会签流转到下一位审批人,给他发通知与钉钉待办
                self._queue("tasks_created", [nxt[0].id], inst)
                node_done = False
            else:
                node_done = all(s.status in ("approved", "cancelled") for s in siblings)

        if node_done:
            ni.status = "completed"
            ni.completed_at = _now()
            await self.db.flush()
            await self._advance(inst, version, ni.node_def_id, ctx)

    async def _return_to_node(self, inst, version, target: dict, ctx) -> None:
        """退回：作废所有未处理待办与进行中的节点实例，然后重新激活目标审批节点。"""
        tasks = (await self.db.execute(select(WfTaskInstance).where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status.in_(["pending", "waiting"]),
        ))).scalars().all()
        for t in tasks:
            t.status = "cancelled"
        self._queue("todos_done", [t.id for t in tasks])
        nis = (await self.db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.status == "running",
        ))).scalars().all()
        for ni in nis:
            ni.status = "cancelled"
        await self.db.flush()
        # 重新激活目标节点（会重新解析审批人并建待办）
        await self._activate_node(inst, version, target, ctx)

    async def _reject_flow(self, inst, reason: str | None = None) -> None:
        # 作废所有未处理待办,流程置驳回
        tasks = (await self.db.execute(
            select(WfTaskInstance).where(
                WfTaskInstance.process_instance_id == inst.id,
                WfTaskInstance.status.in_(["pending", "waiting"]),
            )
        )).scalars().all()
        for t in tasks:
            t.status = "cancelled"
        # 被作废的待办要一并完结其钉钉待办,否则会一直挂在审批人的钉钉里
        self._queue("todos_done", [t.id for t in tasks])
        await self._complete_instance(inst, "rejected", reason=reason)

    # ---------- 收尾 / 回写 ----------

    async def _complete_instance(self, inst, status: str, reason: str | None = None) -> None:
        inst.status = status
        inst.completed_at = _now()
        await self.db.flush()
        # 回写关联表单实例状态
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                fi.status = status  # completed / rejected
        # 回写既有业务单据(灰度替换旧审批引擎): 按 biz_type 更新业务表状态列。
        # reason 用于把驳回意见落到业务表(如 leads.reject_reason),通过时清空。
        if inst.biz_type and inst.biz_id:
            from app.domains.lowcode.wf_biz_writeback import writeback
            await writeback(self.db, self.tenant_id, inst.biz_type, inst.biz_id, status, reason=reason)
        # outbox 领域事件必须在 commit 之前入队
        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(
            self.db, self.tenant_id,
            "workflow.approved" if status == "completed" else "workflow.rejected",
            inst, {"reason": reason} if reason else None,
        )
        self._queue("finished", status, reason, inst)

    async def _form_data(self, inst) -> dict:
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                return dict(fi.form_data or {})
        return {}

    def _log(self, pid, nid, tid, actor, action, opinion) -> None:
        self.db.add(WfTaskActionLog(
            id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=pid,
            node_instance_id=nid, task_instance_id=tid,
            actor_id=actor.get("sub"), actor_name=actor.get("real_name"),
            action=action, opinion=opinion,
        ))

    # ---------- 撤回 ----------

    async def withdraw(self, process_instance_id: str, actor: dict) -> None:
        inst = (await self.db.execute(
            select(WfProcessInstance).where(
                WfProcessInstance.id == process_instance_id,
                WfProcessInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if not inst:
            raise BusinessException(code=NOT_FOUND, message="流程不存在")
        if inst.initiator_id != actor.get("sub"):
            raise BusinessException(code=FORBIDDEN, message="仅发起人可撤回")
        if inst.status != "running":
            raise BusinessException(code=BUSINESS_ERROR, message="流程已结束,无法撤回")
        tasks = (await self.db.execute(
            select(WfTaskInstance).where(
                WfTaskInstance.process_instance_id == inst.id,
                WfTaskInstance.status.in_(["pending", "waiting"]),
            )
        )).scalars().all()
        current_assignees = [t.assignee_id for t in tasks if t.status == "pending"]
        for t in tasks:
            t.status = "cancelled"
        inst.status = "withdrawn"
        inst.completed_at = _now()
        self._log(inst.id, None, None, actor, "withdraw", None)
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                fi.status = "withdrawn"
        # 被撤回而作废的待办，完结其钉钉待办并通知当前审批人（对齐旧引擎 withdraw_flow）。
        # 注意：撤回**不**回写业务单据状态——旧引擎同样不回写，此处刻意保持一致。
        self._queue("todos_done", [t.id for t in tasks])
        self._queue("withdrawn", current_assignees, actor, inst)
        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(self.db, self.tenant_id, "workflow.withdrawn", inst)
        await self.db.commit()
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "withdraw")

    # ---------- 超时(SLA) ----------

    async def fire_timeout(self, ni: WfNodeInstance) -> dict | None:
        """处理一个已超时的审批节点实例(由 reminder_worker 判定超时后调用)。

        依据 ni.config['timeout']={hours, action, transfer_to?}:
          notify/remind → 仅提醒(不改状态);auto_approve/auto_reject/auto_transfer → 相应处置。
        幂等: 处理后置 config['sla_fired']=True,避免重复触发。不在此 commit(由调用方批量提交)。
        返回给 worker 用于发通知的描述 dict(recipients/title/content/instance_id),或 None。
        """
        cfg = dict(ni.config or {})
        to = cfg.get("timeout") or {}
        action = to.get("action", "notify")
        # 超时场景下由 reminder_worker 给发起人发带「超时」上下文的通知(见下方 notify 返回值),
        # 引擎自己的流程结束通知会与之重复,故在这条路径上抑制。
        self._suppress_finished_notify = True
        inst = await self.db.get(WfProcessInstance, ni.process_instance_id)
        notify: dict | None = None
        sys_actor = {"sub": "system", "real_name": "系统"}

        if inst is None or inst.status != "running" or ni.status != "running":
            action = "noop"  # 状态已变,仅标记防重

        if action in ("notify", "remind"):
            pend = (await self.db.execute(select(WfTaskInstance).where(
                WfTaskInstance.node_instance_id == ni.id, WfTaskInstance.status == "pending",
            ))).scalars().all()
            self._log(ni.process_instance_id, ni.id, None, sys_actor, "timeout", "审批超时提醒")
            notify = {
                "recipients": [t.assignee_id for t in pend],
                "title": f"审批超时提醒: {(inst.title if inst else None) or '待办'}",
                "content": "有一条审批任务已超时未处理,请尽快处理。",
                "instance_id": ni.process_instance_id,
            }
        elif action == "auto_approve":
            version = await self.db.get(WfProcessDefinitionVersion, inst.process_version_id)
            ctx = ApprovalContext(initiator_id=inst.initiator_id, form_data=await self._form_data(inst),
                                  nominated=inst.nominated_approvers or {})
            # 强制完成该节点: pending 置通过, 顺序会签的 waiting 兄弟任务作废(否则悬挂)。
            sibs = (await self.db.execute(select(WfTaskInstance).where(
                WfTaskInstance.node_instance_id == ni.id,
                WfTaskInstance.status.in_(["pending", "waiting"]),
            ))).scalars().all()
            for t in sibs:
                t.status = "approved" if t.status == "pending" else "cancelled"
                if t.status == "approved":
                    t.opinion = "超时自动通过"
                t.action_at = _now(); t.version += 1
            self._log(inst.id, ni.id, None, sys_actor, "auto_approve", "审批超时,自动通过")
            ni.status = "completed"; ni.completed_at = _now()
            await self.db.flush()
            await self._advance(inst, version, ni.node_def_id, ctx)
            notify = {"recipients": [inst.initiator_id], "title": f"审批超时自动通过: {inst.title or '流程'}",
                      "content": "一条审批因超时已自动通过,流程继续。", "instance_id": inst.id}
        elif action == "auto_reject":
            pend = (await self.db.execute(select(WfTaskInstance).where(
                WfTaskInstance.node_instance_id == ni.id, WfTaskInstance.status == "pending",
            ))).scalars().all()
            for t in pend:
                t.status = "rejected"; t.opinion = "超时自动驳回"; t.action_at = _now(); t.version += 1
            self._log(inst.id, ni.id, None, sys_actor, "auto_reject", "审批超时,自动驳回")
            ni.status = "rejected"; ni.completed_at = _now()
            await self._reject_flow(inst, reason="超时自动驳回")
            notify = {"recipients": [inst.initiator_id], "title": f"审批超时自动驳回: {inst.title or '流程'}",
                      "content": "一条审批因超时已自动驳回。", "instance_id": inst.id}
        elif action == "auto_transfer":
            to_user = to.get("transfer_to")
            pend = (await self.db.execute(select(WfTaskInstance).where(
                WfTaskInstance.node_instance_id == ni.id, WfTaskInstance.status == "pending",
            ))).scalars().all()
            if to_user:
                for t in pend:
                    # 转交前先按原处理人完结其钉钉待办，再给接收人重新下发
                    self._queue("todo_done_explicit", t.assignee_id, getattr(t, "dingtalk_todo_id", None))
                    t.assignee_id = to_user; t.dingtalk_todo_id = None; t.version += 1
                self._queue("tasks_created", [t.id for t in pend], inst)
                self._log(inst.id, ni.id, None, sys_actor, "auto_transfer", "审批超时,自动转交")
                notify = {"recipients": [to_user], "title": f"审批超时转交给你: {inst.title or '待办'}",
                          "content": "一条审批因原处理人超时已转交给你,请尽快处理。", "instance_id": inst.id}
            else:
                # 未配置转交人: 退化为提醒当前待办人, 避免静默无动作。
                self._log(inst.id, ni.id, None, sys_actor, "timeout", "审批超时提醒(未配置转交人)")
                notify = {"recipients": [t.assignee_id for t in pend],
                          "title": f"审批超时提醒: {inst.title or '待办'}",
                          "content": "有一条审批任务已超时未处理,请尽快处理。", "instance_id": inst.id}

        cfg["sla_fired"] = True
        ni.config = cfg
        flag_modified(ni, "config")
        return notify

    # ---------- 催办 ----------

    async def urge(self, process_instance_id: str, actor: dict) -> int:
        """催办: 发起人对进行中流程的当前待办人发提醒。返回被催办人数。"""
        inst = (await self.db.execute(select(WfProcessInstance).where(
            WfProcessInstance.id == process_instance_id,
            WfProcessInstance.tenant_id == self.tenant_id,
        ))).scalar_one_or_none()
        if not inst:
            raise BusinessException(code=NOT_FOUND, message="流程不存在")
        if inst.initiator_id != actor.get("sub"):
            raise BusinessException(code=FORBIDDEN, message="仅发起人可催办")
        if inst.status != "running":
            raise BusinessException(code=BUSINESS_ERROR, message="流程已结束,无需催办")
        recent = (await self.db.execute(select(WfTaskActionLog.id).where(
            WfTaskActionLog.process_instance_id == inst.id,
            WfTaskActionLog.action == "urge",
            WfTaskActionLog.created_at > _now() - timedelta(minutes=10),
        ).limit(1))).scalar_one_or_none()
        if recent:
            raise BusinessException(code=BUSINESS_ERROR, message="10 分钟内已催办过,请稍后再试")
        pend = (await self.db.execute(select(WfTaskInstance).where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status == "pending",
        ))).scalars().all()
        if not pend:
            raise BusinessException(code=BUSINESS_ERROR, message="当前没有待处理的审批")
        self._log(inst.id, None, None, actor, "urge", None)
        from app.domains.notification.service import send_notification
        n = 0
        for t in pend:
            try:
                await send_notification(
                    db=self.db, tenant_id=self.tenant_id, recipient_id=t.assignee_id,
                    type="system", title=f"审批催办: {inst.title or '待办'}",
                    content=f"发起人{actor.get('real_name') or ''}催办,请尽快处理该审批。",
                    biz_type="wf_instance", biz_id=inst.id,
                )
                n += 1
            except Exception:
                pass
        await self.db.commit()
        return n
