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

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
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

logger = logging.getLogger("spt_crm.lowcode.workflow_engine")

# 发起人「修改并重新提交」虚拟节点（撤回/驳回/退回发起人后进入待办）
REVISE_NODE_DEF_ID = "__initiator_revise__"
REVISE_NODE_NAME = "修改并重新提交"


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
        # 人员多选等：actual 为列表时，任一成员命中即真（简道云 usergroup in）
        if isinstance(actual, list):
            return any(str(a) == str(e) for a in actual for e in lst)
        if isinstance(actual, dict) and actual.get("id") is not None:
            return any(str(actual.get("id")) == str(e) for e in lst)
        return any(str(actual) == str(e) for e in lst)
    if op == "not_in":
        lst = expected if isinstance(expected, list) else str(expected).split(",")
        if isinstance(actual, list):
            return all(str(a) != str(e) for a in actual for e in lst)
        if isinstance(actual, dict) and actual.get("id") is not None:
            return all(str(actual.get("id")) != str(e) for e in lst)
        return all(str(actual) != str(e) for e in lst)
    if op == "contains":
        return str(expected) in str(actual or "")
    if op == "not_contains":
        return str(expected) not in str(actual or "")
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
        # 整次 submit/act 复用组织快照，避免每个节点新建 Resolver 重复加载全量部门/用户
        self._approver_resolver = ApproverResolver(db, tenant_id)

    async def _has_downstream_approval(self, process_instance_id: str) -> bool:
        """下一节点（或任一审批节点）已有人审批通过 → 不可撤回。"""
        row = (await self.db.execute(
            select(WfTaskInstance.id).where(
                WfTaskInstance.process_instance_id == process_instance_id,
                WfTaskInstance.status == "approved",
            ).limit(1)
        )).scalar_one_or_none()
        return row is not None

    async def _cancel_initiator_revise_todos(self, process_instance_id: str) -> None:
        tasks = (await self.db.execute(
            select(WfTaskInstance).where(
                WfTaskInstance.process_instance_id == process_instance_id,
                WfTaskInstance.status == "pending",
            )
        )).scalars().all()
        if not tasks:
            return
        ni_ids = {t.node_instance_id for t in tasks if t.node_instance_id}
        revise_nis = set()
        if ni_ids:
            for ni in (await self.db.execute(
                select(WfNodeInstance).where(WfNodeInstance.id.in_(ni_ids))
            )).scalars().all():
                if ni.node_type == "revise" or ni.node_def_id == REVISE_NODE_DEF_ID:
                    revise_nis.add(ni.id)
                    ni.status = "cancelled"
                    ni.completed_at = _now()
        done_ids = []
        for t in tasks:
            if t.node_instance_id in revise_nis:
                t.status = "cancelled"
                t.action_at = _now()
                done_ids.append(t.id)
        if done_ids:
            self._queue("todos_done", done_ids)

    async def _create_initiator_revise_todo(
        self, inst: WfProcessInstance, *, reason: str | None = None,
    ) -> None:
        """撤回/驳回/退回发起人后：给发起人一条「修改并重新提交」待办。"""
        if not inst.initiator_id:
            return
        await self._cancel_initiator_revise_todos(inst.id)
        now = _now()
        ni = WfNodeInstance(
            id=generate_uuid(),
            tenant_id=self.tenant_id,
            process_instance_id=inst.id,
            node_def_id=REVISE_NODE_DEF_ID,
            node_type="revise",
            node_name=REVISE_NODE_NAME,
            status="running",
            config={"reason": reason} if reason else {},
            started_at=now,
        )
        self.db.add(ni)
        await self.db.flush()
        task = WfTaskInstance(
            id=generate_uuid(),
            tenant_id=self.tenant_id,
            process_instance_id=inst.id,
            node_instance_id=ni.id,
            assignee_id=inst.initiator_id,
            status="pending",
        )
        self.db.add(task)
        await self.db.flush()
        self._queue("tasks_created", [task.id], inst)

    # ---------- 通知(延迟到提交后下发) ----------

    @staticmethod
    def _is_lead_owner_confirm_node(node) -> bool:
        """是否「业务员确认是否转商机」节点（审批或历史抄送）。"""
        if not node:
            return False
        nid = getattr(node, "node_def_id", None) or (node.get("id") if isinstance(node, dict) else None) or ""
        name = (
            getattr(node, "node_name", None)
            or (node.get("name") if isinstance(node, dict) else None)
            or ""
        ).strip()
        if nid in ("cc_owner", "approval_owner_confirm"):
            return True
        return "转商机" in name or "确认转化" in name

    @staticmethod
    def _is_lead_intel_task_node(node_inst) -> bool:
        """是否信息情报部审批节点（需走收录/袭击/回退）。业务员确认节点返回 False。"""
        if not node_inst:
            return True
        if WorkflowEngine._is_lead_owner_confirm_node(node_inst):
            return False
        name = (getattr(node_inst, "node_name", None) or "").strip()
        if "情报" in name or name in ("线索审核", "内勤审批"):
            return True
        # 默认：线索流其它审批节点仍按情报闸门保护
        return True

    async def _lead_is_attacked(self, inst: WfProcessInstance) -> bool:
        if inst.biz_type != "lead" or not inst.biz_id:
            return False
        from app.domains.lead.models import Lead
        ld = await self.db.get(Lead, inst.biz_id)
        return bool(ld and getattr(ld, "review_status", None) == "attacked")

    async def _mark_lead_approved_after_intel(self, inst: WfProcessInstance, node) -> None:
        """情报节点通过/空审跳过后立刻 approved（流程可能还要走业务员确认）。

        与 intel_review_lead(include) 对齐：不能等整单 writeback，否则转化门禁一直卡 pending。
        同时清空旧驳回原因，避免详情页残留上一轮文案。
        """
        if inst.biz_type != "lead" or not inst.biz_id:
            return
        if not self._is_lead_intel_task_node(node):
            return
        if await self._lead_is_attacked(inst):
            return
        from app.domains.lead.models import Lead
        ld = await self.db.get(Lead, inst.biz_id)
        if not ld:
            return
        if getattr(ld, "review_status", None) == "pending":
            ld.review_status = "approved"
        ld.reject_reason = None
        await self.db.flush()

    def _queue(self, kind: str, *args) -> None:
        self._notify.append((kind, *args))

    @staticmethod
    def _inst_snap(inst: WfProcessInstance | None) -> SimpleNamespace | None:
        """后台通知不能依赖请求结束后的 ORM 会话，先拍平常用字段。"""
        if inst is None:
            return None
        return SimpleNamespace(
            id=inst.id,
            tenant_id=getattr(inst, "tenant_id", None),
            initiator_id=inst.initiator_id,
            title=inst.title,
            biz_type=inst.biz_type,
            biz_id=inst.biz_id,
            status=inst.status,
            business_no=getattr(inst, "business_no", None),
        )

    def _snap_queue_item(self, item: tuple) -> tuple:
        """把队列里夹带的 ORM 实例换成快照，供后台任务使用。"""
        kind = item[0]
        if kind in ("tasks_created", "empty_auto_approved") and len(item) > 2:
            return (kind, item[1], self._inst_snap(item[2]) if item[2] is not None else None)
        if kind == "cc_notified" and len(item) > 3:
            return (kind, item[1], item[2], self._inst_snap(item[3]) if item[3] is not None else None)
        if kind in ("finished", "withdrawn") and len(item) > 3:
            return (kind, item[1], item[2], self._inst_snap(item[3]) if item[3] is not None else None)
        return item

    async def flush_notifications(
        self, inst: WfProcessInstance | None = None, *, wait: bool = False,
    ) -> None:
        """提交成功后统一下发通知。

        默认后台异步（不阻塞提交接口）；timeout worker 等场景传 wait=True 确保发完再退出。
        必须在业务事务 commit **之后**调用。
        """
        if not self._notify:
            return
        pending_raw, self._notify = self._notify, []
        pending = [self._snap_queue_item(it) for it in pending_raw]
        snap = self._inst_snap(inst)
        suppress = self._suppress_finished_notify
        tenant_id = self.tenant_id

        async def _run() -> None:
            await WorkflowEngine._flush_notifications_now(
                tenant_id, pending, snap, suppress_finished=suppress,
            )

        if wait:
            await _run()
            return
        try:
            asyncio.get_running_loop().create_task(_run())
        except RuntimeError:
            await _run()

    @staticmethod
    async def _flush_notifications_now(
        tenant_id: str,
        pending: list[tuple],
        inst: SimpleNamespace | None,
        *,
        suppress_finished: bool = False,
    ) -> None:
        from app.domains.lowcode import wf_notify
        for item in pending:
            kind = item[0]
            try:
                if kind == "tasks_created":
                    target = item[2] if len(item) > 2 and item[2] is not None else inst
                    if target is not None:
                        await wf_notify.notify_tasks_created(tenant_id, target, item[1])
                elif kind == "todos_done":
                    await wf_notify.complete_todos(tenant_id, item[1])
                elif kind == "todo_done_explicit":
                    await wf_notify.complete_todo(tenant_id, item[1], item[2])
                elif kind == "cc_notified":
                    target = item[3] if len(item) > 3 and item[3] is not None else inst
                    if target is not None:
                        await wf_notify.notify_cc_users(
                            tenant_id, target, item[1], node_name=item[2],
                        )
                elif kind == "finished":
                    target = item[3] if len(item) > 3 and item[3] is not None else inst
                    if target is not None and not suppress_finished:
                        await wf_notify.notify_flow_finished(tenant_id, target, item[1], item[2])
                elif kind == "withdrawn":
                    target = item[3] if len(item) > 3 and item[3] is not None else inst
                    if target is not None:
                        await wf_notify.notify_withdrawn(tenant_id, target, item[1], item[2])
                elif kind == "empty_auto_approved":
                    target = item[2] if len(item) > 2 and item[2] is not None else inst
                    if target is not None:
                        await wf_notify.notify_empty_auto_approved(tenant_id, target, item[1])
            except Exception:  # pragma: no cover - 通知永不影响主流程
                logger.warning("flush notification failed for %s", kind, exc_info=True)

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

    async def _has_live_work(self, inst: WfProcessInstance) -> bool:
        """是否仍有未办结的审批节点或待办（旁路抄送触达 end 时用来判断能否收尾）。"""
        other_running = (await self.db.execute(select(WfNodeInstance.id).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.status == "running",
            WfNodeInstance.node_type == "approval",
        ).limit(1))).scalar_one_or_none()
        if other_running:
            return True
        live_task = (await self.db.execute(select(WfTaskInstance.id).where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status.in_(["pending", "waiting"]),
        ).limit(1))).scalar_one_or_none()
        return live_task is not None

    def _next_targets(self, version: WfProcessDefinitionVersion, node_id: str, form_data: dict) -> list[str]:
        """按连线条件选下一节点。

        - ``always: true``：抄送旁路，与主链并行、互不抢占（有条件时仍需为真）
        - ``exclusive_group``：同组内按连线顺序互斥（简道云 if/else）——命中第一条
          有条件边，否则走组内无条件边(else)；不同组彼此独立
        - 无 ``exclusive_group`` 的普通边：仍可多条条件同时命中（并行）；
          若这些并行边中无一条件命中，则走其中无条件边
        旁路边排在前面，避免 end 先激活导致同批抄送被跳过。
        """
        routes = self._outgoing(version, node_id)
        always_routes = [r for r in routes if r.get("always")]
        normal = [r for r in routes if not r.get("always")]

        exclusive_groups: dict[str, list] = {}
        parallel_edges: list = []
        for r in normal:
            gid = r.get("exclusive_group")
            if gid:
                exclusive_groups.setdefault(str(gid), []).append(r)
            else:
                parallel_edges.append(r)

        core: list[str] = []
        for edges in exclusive_groups.values():
            hit: str | None = None
            for r in edges:
                cond = r.get("condition")
                if cond and evaluate_condition(cond, form_data):
                    hit = r["target"]
                    break
            if hit:
                core.append(hit)
            else:
                for r in edges:
                    if not r.get("condition"):
                        core.append(r["target"])

        matched_para = [
            r["target"] for r in parallel_edges
            if r.get("condition") and evaluate_condition(r["condition"], form_data)
        ]
        if matched_para:
            core.extend(matched_para)
        else:
            core.extend(r["target"] for r in parallel_edges if not r.get("condition"))

        always_targets: list[str] = []
        for r in always_routes:
            cond = r.get("condition")
            if cond and not evaluate_condition(cond, form_data):
                continue
            always_targets.append(r["target"])
        return list(dict.fromkeys([*always_targets, *core]))

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
        labels = {
            "submit": "提交审批", "approve": "审批通过", "reject": "审批驳回",
            "withdraw": "撤回审批", "resubmit": "重新发起",
        }
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
            # 主链与旁路抄送可能并行：抄送先「到达」end 时，审批节点/待办仍在，
            # 不能提前 completed（否则会出现表头已通过、图纸领取仍处理中）。
            if await self._has_live_work(inst):
                return
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
            return await self._approver_resolver.resolve(rule, ctx)
        except NoApproverError:
            return []

    async def _activate_approval(self, inst, version, node, ctx) -> None:
        # 并行分叉汇入同一审批节点时（如 研究院安排∥工艺包装 → 再入研究院安排）：
        # 已有进行中的同定义节点则跳过，避免重复建待办。
        existing = (await self.db.execute(
            select(WfNodeInstance.id).where(
                WfNodeInstance.process_instance_id == inst.id,
                WfNodeInstance.node_def_id == node["id"],
                WfNodeInstance.status == "running",
            ).limit(1)
        )).scalar_one_or_none() if self.db is not None else None
        if existing:
            return

        # 线索袭击：不可转化，跳过「业务员确认是否转商机」待办，改为知会申报人后直通结束
        if (
            inst.biz_type == "lead"
            and self._is_lead_owner_confirm_node(node)
            and await self._lead_is_attacked(inst)
        ):
            users = await self._resolve_approvers(version, node, ctx)
            ni = WfNodeInstance(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                node_def_id=node["id"], node_type="approval",
                node_name=node.get("name") or "业务员确认是否转商机",
                status="completed", config={"skipped": "attacked"},
                started_at=_now(), completed_at=_now(),
            )
            self.db.add(ni)
            await self.db.flush()
            self._log(inst.id, ni.id, None, {"sub": "system"}, "auto_skip",
                      "线索已标记袭击，跳过业务员确认")
            if users:
                self._queue("cc_notified", list(users), node.get("name") or "业务员确认是否转商机", inst)
            await self._advance(inst, version, node["id"], ctx)
            return

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
            await self._mark_lead_approved_after_intel(inst, node)
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
        # 抄送原先只落库不推送；登记通知，提交后统一下发（站内 + 钉钉）
        if users:
            self._queue("cc_notified", list(users), node.get("name") or "抄送", inst)

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
                  transfer_to: str | None = None, return_to: str | None = None,
                  field_updates: dict | None = None, *,
                  allow_lead_intel: bool = False) -> None:
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
        if not inst:
            raise BusinessException(code=BUSINESS_ERROR, message="流程不存在")

        # 发起人修订待办：流程已撤回/驳回，点「重新提交」走 resubmit
        node_inst = await self.db.get(WfNodeInstance, task.node_instance_id)
        is_revise = bool(
            node_inst and (node_inst.node_type == "revise" or node_inst.node_def_id == REVISE_NODE_DEF_ID)
        )
        if is_revise:
            if inst.status not in ("withdrawn", "rejected"):
                raise BusinessException(code=BUSINESS_ERROR, message="当前状态不可重新提交")
            if action not in ("approve", "resubmit"):
                raise BusinessException(code=VALIDATION_ERROR, message="修订待办请修改后重新提交")
            task.status = "approved"
            task.opinion = opinion or "重新提交"
            task.action_at = _now()
            task.version += 1
            if node_inst:
                node_inst.status = "completed"
                node_inst.completed_at = _now()
            self._log(inst.id, task.node_instance_id, task.id, actor, "resubmit", opinion)
            self._queue("todo_done_explicit", task.assignee_id, getattr(task, "dingtalk_todo_id", None))
            await self.db.flush()
            await self.resubmit(inst.id, actor)
            return

        if inst.status != "running":
            raise BusinessException(code=BUSINESS_ERROR, message="流程已结束")

        # 线索审核：信息情报部节点必须走情报裁定；「业务员确认是否转商机」允许普通通过/驳回
        if (
            inst.biz_type == "lead"
            and action in ("approve", "reject")
            and not allow_lead_intel
            and self._is_lead_intel_task_node(node_inst)
        ):
            raise BusinessException(
                code=VALIDATION_ERROR,
                message="线索审核请使用情报审批（收录/袭击/回退），不可直接通过或驳回",
            )

        version = await self.db.get(WfProcessDefinitionVersion, inst.process_version_id)
        ctx = ApprovalContext(initiator_id=inst.initiator_id, form_data=await self._form_data(inst),
                              nominated=inst.nominated_approvers or {})

        # 审批通过：按节点 field_perms 写回业务字段（对齐简道云 optAuth）
        if action == "approve":
            await self._apply_node_field_updates(
                inst, version, task, field_updates, opinion=opinion, action=action,
            )
            ctx.form_data = await self._form_data(inst)

        if action == "comment":
            content = (opinion or "").strip()
            if not content:
                raise BusinessException(code=VALIDATION_ERROR, message="请填写评论内容")
            # 评论不推进/不完结待办，仅写入讨论区
            self.db.add(WfProcessComment(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                user_id=actor.get("sub"), user_name=actor.get("real_name"), content=content,
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
            # 退回发起人：结束流程并生成发起人修订待办；退回审批节点：流程仍进行中
            if (return_to or "") == "__initiator__":
                task.status = "returned"
                task.opinion = opinion
                task.action_at = _now()
                task.version += 1
                self._log(inst.id, task.node_instance_id, task.id, actor, "return", opinion)
                self._queue("todo_done_explicit", task.assignee_id, getattr(task, "dingtalk_todo_id", None))
                await self._reject_flow(inst, reason=opinion)
                await self._create_initiator_revise_todo(inst, reason=opinion)
                await self.db.commit()
                await self.flush_notifications(inst)
                await self._audit(inst, actor, "return")
                return
            target = self._nodes_by_id(version).get(return_to or "")
            if not target or target.get("type") != "approval":
                raise BusinessException(code=VALIDATION_ERROR, message="退回目标必须是有效的审批节点或发起人")
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
            node_inst = await self.db.get(WfNodeInstance, task.node_instance_id)
            # 业务员「暂不转商机」：结束流程但保留情报收录态，勿把线索回写成 rejected（不可再报备）
            if inst.biz_type == "lead" and self._is_lead_owner_confirm_node(node_inst):
                await self._complete_instance(inst, "completed", reason=opinion or "暂不转商机")
                await self.db.commit()
                await self.flush_notifications(inst)
                await self._audit(inst, actor, "reject")
                return
            # 驳回意见随流程结束回写到业务表(如 leads.reject_reason)
            await self._reject_flow(inst, reason=opinion)
            # 线索情报驳回为终态（不可再报备），不发发起人修订待办；其它业务仍可改后再提
            if inst.biz_type != "lead":
                await self._create_initiator_revise_todo(inst, reason=opinion)
            await self.db.commit()
            await self.flush_notifications(inst)
            await self._audit(inst, actor, "reject")
            return

        # approve → 判断节点是否完成
        await self._on_task_approved(inst, version, task, ctx)
        await self.db.commit()
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "approve")

    async def _apply_node_field_updates(
        self, inst, version, task, field_updates: dict | None, *,
        opinion: str | None, action: str,
    ) -> None:
        from app.domains.lowcode.wf_field_writeback import (
            apply_field_updates, parse_field_perms, validate_field_updates,
        )
        node_inst = await self.db.get(WfNodeInstance, task.node_instance_id)
        node_def_id = node_inst.node_def_id if node_inst else None
        node = self._nodes_by_id(version).get(node_def_id or "") or {}
        perms = parse_field_perms(node)
        opinion_required = bool(node.get("opinion_required"))
        # 无配置且无提交时跳过；有提交或必填/意见要求则走校验
        if not perms and not field_updates and not opinion_required:
            return

        form_fields: list = []
        form_rules: list = []
        form_data: dict = {}
        if inst.form_instance_id:
            try:
                from app.domains.lowcode.models import FormInstance, FormTemplateVersion
                from app.domains.lowcode.service import get_published_version
                fi = await self.db.get(FormInstance, inst.form_instance_id)
                if fi and fi.tenant_id == self.tenant_id:
                    form_data = dict(fi.form_data or {}) if isinstance(fi.form_data, dict) else {}
                    form_fields = list(fi.field_definitions or [])
                    try:
                        pub = await get_published_version(self.db, self.tenant_id, fi.template_id)
                        if pub:
                            form_rules = list(pub.rule_definitions or [])
                            if not form_fields:
                                form_fields = list(pub.field_definitions or [])
                    except Exception:
                        ver = await self.db.get(FormTemplateVersion, fi.template_version_id) if fi.template_version_id else None
                        if ver:
                            form_rules = list(ver.rule_definitions or [])
                            if not form_fields:
                                form_fields = list(ver.field_definitions or [])
            except Exception:
                form_fields, form_rules, form_data = [], [], {}

        filtered = validate_field_updates(
            perms, field_updates, opinion=opinion,
            opinion_required=opinion_required, action=action,
            form_fields=form_fields, form_rules=form_rules, form_data=form_data,
        )
        if action == "approve" and filtered:
            await self._assert_person_field_values(inst.biz_type, filtered)
            await self._assert_pickable_scope(inst, filtered)
        if filtered:
            await apply_field_updates(
                self.db, self.tenant_id,
                biz_type=inst.biz_type, biz_id=inst.biz_id,
                form_instance_id=inst.form_instance_id,
                updates=filtered,
            )

    async def _assert_pickable_scope(self, inst, updates: dict) -> None:
        """人员/部门字段若配置了 pickable_scope，所选值必须在范围内。"""
        from sqlalchemy import select
        from app.common.exceptions import BusinessException
        from app.common.error_codes import VALIDATION_ERROR
        from app.domains.auth.models import User, Role, UserRole
        from app.domains.organization.models import Department
        from app.domains.lowcode.pickable_scope import (
            role_codes_from_field, scope_code_from_field, filter_by_fields_from_field,
        )
        from app.domains.lowcode.models import FormInstance
        from app.domains.lowcode.service import get_published_version
        from app.domains.organization import pickable_scope_service as pss

        form_defs: list = []
        form_data: dict = {}
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi and fi.tenant_id == self.tenant_id:
                form_data = dict(fi.form_data or {})
                try:
                    ver = await get_published_version(self.db, self.tenant_id, fi.template_id)
                    form_defs = list((ver.field_definitions if ver else None) or [])
                except Exception:
                    form_defs = []
        if not form_defs:
            return
        # 审批写回的值优先
        merged = {**form_data, **(updates or {})}
        by_id = {f["id"]: f for f in form_defs if isinstance(f, dict) and f.get("id")}
        person_types = {"person", "person_multi", "user"}
        dept_types = {"department", "department_multi"}

        for key, raw in updates.items():
            fd = by_id.get(key)
            if not fd or raw in (None, "", []):
                continue
            ftype = str(fd.get("type") or "")
            candidates = [str(x) for x in (raw if isinstance(raw, list) else [raw]) if x]
            if not candidates:
                continue

            scode = scope_code_from_field(fd)
            label = fd.get("label") or key

            # —— 部门字段：按部门可选范围校验 ——
            if ftype in dept_types:
                if not scode:
                    continue
                await pss.ensure_preset_scopes(self.db, self.tenant_id)
                scope = await pss.get_scope_by_code(self.db, self.tenant_id, scode)
                if not scope:
                    raise BusinessException(
                        code=VALIDATION_ERROR,
                        message=f"「{label}」可选范围「{scode}」不存在，请到「系统管理 → 可选范围」配置",
                    )
                allowed_depts = await pss.resolve_department_ids(
                    self.db, self.tenant_id, scope,
                )
                if allowed_depts is None:
                    continue
                bad = [c for c in candidates if c not in allowed_depts]
                if not bad:
                    continue
                rows = (
                    await self.db.execute(
                        select(Department.id, Department.name).where(
                            Department.tenant_id == self.tenant_id,
                            Department.id.in_(bad),
                        )
                    )
                ).all()
                name_by_id = {r[0]: (r[1] or r[0]) for r in rows}
                bad_labels = [name_by_id.get(c, c) for c in bad]
                raise BusinessException(
                    code=VALIDATION_ERROR,
                    message=f"「{label}」所选部门不在可选范围内: {', '.join(bad_labels)}",
                )

            # —— 人员字段：按人员可选范围（可再按科室收窄）——
            if ftype not in person_types:
                continue

            extra_depts: list[str] = []
            # 方案管理设计指派/设计人：提交校验也不按科室收窄
            skip_dept_filter = key in ("design_assignees", "designer")
            for fid in ([] if skip_dept_filter else filter_by_fields_from_field(fd)):
                v = merged.get(fid)
                if isinstance(v, list):
                    extra_depts.extend(str(x) for x in v if x)
                elif v not in (None, ""):
                    extra_depts.append(str(v))

            allowed: set[str] | None = None
            if scode:
                await pss.ensure_preset_scopes(self.db, self.tenant_id)
                scope = await pss.get_scope_by_code(self.db, self.tenant_id, scode)
                if not scope:
                    raise BusinessException(
                        code=VALIDATION_ERROR,
                        message=f"「{label}」可选范围「{scode}」不存在，请到「系统管理 → 可选范围」配置",
                    )
                # 部门类范围误绑到人员字段时，不应按人员解析
                if getattr(scope, "kind", None) == "department":
                    continue
                allowed = await pss.resolve_person_ids(
                    self.db, self.tenant_id, scope, extra_dept_ids=extra_depts or None,
                )
                if allowed is None:
                    continue
            else:
                codes = role_codes_from_field(fd)
                if not codes:
                    continue
                role_ids = (
                    await self.db.execute(
                        select(Role.id).where(Role.tenant_id == self.tenant_id, Role.code.in_(codes))
                    )
                ).scalars().all()
                if not role_ids and any(c == "room_leader" for c in codes):
                    from app.common.rbac_sync import ensure_business_roles
                    created = await ensure_business_roles(self.db, self.tenant_id, ["room_leader"])
                    if created:
                        await self.db.flush()
                    role_ids = (
                        await self.db.execute(
                            select(Role.id).where(Role.tenant_id == self.tenant_id, Role.code.in_(codes))
                        )
                    ).scalars().all()
                if not role_ids:
                    raise BusinessException(
                        code=VALIDATION_ERROR,
                        message=f"「{label}」可选角色未配置，请到「系统管理 → 可选范围 / 角色」维护",
                    )
                allowed = set(
                    (
                        await self.db.execute(
                            select(UserRole.user_id).where(
                                UserRole.tenant_id == self.tenant_id,
                                UserRole.role_id.in_(role_ids),
                            )
                        )
                    ).scalars().all()
                )
                if extra_depts:
                    from app.domains.organization.pickable_scope_service import _user_ids_in_depts
                    allowed &= await _user_ids_in_depts(self.db, self.tenant_id, extra_depts, True)

            rows = (
                await self.db.execute(
                    select(User.id, User.username, User.real_name).where(
                        User.tenant_id == self.tenant_id,
                        (User.id.in_(candidates)) | (User.username.in_(candidates)),
                    )
                )
            ).all()
            id_by_key = {}
            name_by_id: dict[str, str] = {}
            for uid, uname, rname in rows:
                id_by_key[uid] = uid
                if uname:
                    id_by_key[uname] = uid
                name_by_id[uid] = (rname or uname or uid)
            bad = []
            bad_labels = []
            for c in candidates:
                uid = id_by_key.get(c)
                if not uid or uid not in allowed:
                    bad.append(c)
                    bad_labels.append(name_by_id.get(uid or "", c) if uid else c)
            if bad:
                hint = ""
                if extra_depts:
                    hint = "（已按所选科室收窄，请确认人选属于该科室，或先改科室）"
                raise BusinessException(
                    code=VALIDATION_ERROR,
                    message=(
                        f"「{label}」所选人员不在可选范围内: "
                        f"{', '.join(bad_labels)}{hint}"
                    ),
                )

    async def _assert_person_field_values(self, biz_type: str | None, updates: dict) -> None:
        """人员字段必须能解析到在职用户（供下一节点 form_field_person 使用）。"""
        from app.domains.lowcode.biz_field_catalog import get_catalog
        from app.domains.lowcode.approver_resolver import ApproverResolver
        catalog = {f["id"]: f for f in get_catalog(biz_type or "")}
        person_keys = [
            k for k, v in updates.items()
            if (catalog.get(k) or {}).get("type") in ("person", "user") and v not in (None, "")
        ]
        if not person_keys:
            return
        resolver = ApproverResolver(self.db, self.tenant_id)
        labels = {f["id"]: f.get("label") or f["id"] for f in catalog.values()}
        active = await resolver._active_user_ids()
        for key in person_keys:
            raw = updates[key]
            candidates = raw if isinstance(raw, list) else [raw]
            resolved: list[str] = []
            for item in candidates:
                uid = await resolver._resolve_user_identifier(str(item))
                if uid and uid in active:
                    resolved.append(uid)
            if not resolved:
                raise BusinessException(
                    code=VALIDATION_ERROR,
                    message=f"请选择有效的{labels.get(key, key)}（须从组织架构选择）",
                )
            # 写回统一为 user_id，便于下一节点解析
            updates[key] = resolved[0] if len(resolved) == 1 and not isinstance(raw, list) else resolved

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
            await self._mark_lead_approved_after_intel(inst, ni)
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
        # 关闭仍在 running 的节点，避免流程动态长期显示「处理中」
        # （超时自动驳回会先把当前节点置 rejected，这里兜底并行闸内其它 running 节点）
        now = _now()
        nis = (await self.db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.status == "running",
        ))).scalars().all()
        for ni in nis:
            ni.status = "rejected"
            ni.completed_at = now
        await self._complete_instance(inst, "rejected", reason=reason)

    # ---------- 收尾 / 回写 ----------

    async def _complete_instance(self, inst, status: str, reason: str | None = None) -> None:
        inst.status = status
        inst.completed_at = _now()
        # 收尾时关掉残留 running 节点 / pending 待办，避免流程动态长期「处理中」
        now = _now()
        nis = (await self.db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.status == "running",
        ))).scalars().all()
        for ni in nis:
            ni.status = "cancelled" if status == "completed" else "rejected"
            ni.completed_at = now
        tasks = (await self.db.execute(select(WfTaskInstance).where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status.in_(["pending", "waiting"]),
        ))).scalars().all()
        for t in tasks:
            t.status = "cancelled"
        if tasks:
            self._queue("todos_done", [t.id for t in tasks])
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
        # 业务单据流（线索/报价等）没有 FormInstance：按 biz 重建字段上下文，
        # 供审批通过后的抄送节点「表单人员字段」等规则解析（如 owner_id）。
        if inst.biz_type and inst.biz_id:
            try:
                from app.domains.approval.service import _build_policy_context
                return await _build_policy_context(
                    self.db, self.tenant_id, inst.biz_type, inst.biz_id,
                ) or {}
            except Exception:
                return {}
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
        if await self._has_downstream_approval(inst.id):
            raise BusinessException(code=BUSINESS_ERROR, message="下一节点已审批，无法撤回")
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
        # 表单回到草稿，便于修改后重新发起；业务单据回写到可再提交状态（见 REGISTRY.withdrawn）。
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                fi.status = "draft"
        if inst.biz_type and inst.biz_id:
            from app.domains.lowcode.wf_biz_writeback import writeback
            await writeback(self.db, self.tenant_id, inst.biz_type, inst.biz_id, "withdrawn")
        # 被撤回而作废的待办，完结其钉钉待办并通知当前审批人（对齐旧引擎 withdraw_flow）。
        self._queue("todos_done", [t.id for t in tasks])
        self._queue("withdrawn", current_assignees, actor, inst)
        # 发起人待办：修改后再次提交
        await self._create_initiator_revise_todo(inst)
        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(self.db, self.tenant_id, "workflow.withdrawn", inst)
        await self.db.commit()
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "withdraw")

    async def resubmit(self, process_instance_id: str, actor: dict) -> WfProcessInstance:
        """已撤回/已驳回流程由发起人重新发起：新建流程实例，挂回同一表单或业务单据。"""
        inst = (await self.db.execute(
            select(WfProcessInstance).where(
                WfProcessInstance.id == process_instance_id,
                WfProcessInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if not inst:
            raise BusinessException(code=NOT_FOUND, message="流程不存在")
        if inst.initiator_id != actor.get("sub"):
            raise BusinessException(code=FORBIDDEN, message="仅发起人可重新发起")
        if inst.status not in ("withdrawn", "rejected"):
            raise BusinessException(code=BUSINESS_ERROR, message="仅已撤回或已驳回的流程可重新发起")

        # 清掉发起人修订待办（若从「我发起的」直接重提，也可能仍挂着）
        await self._cancel_initiator_revise_todos(inst.id)

        # 防重：同一表单/业务已有进行中流程则直接返回
        if inst.form_instance_id:
            existing = (await self.db.execute(select(WfProcessInstance).where(
                WfProcessInstance.tenant_id == self.tenant_id,
                WfProcessInstance.form_instance_id == inst.form_instance_id,
                WfProcessInstance.status == "running",
            ).limit(1))).scalar_one_or_none()
            if existing:
                return existing
        if inst.biz_type and inst.biz_id:
            existing = (await self.db.execute(select(WfProcessInstance).where(
                WfProcessInstance.tenant_id == self.tenant_id,
                WfProcessInstance.biz_type == inst.biz_type,
                WfProcessInstance.biz_id == inst.biz_id,
                WfProcessInstance.status == "running",
            ).limit(1))).scalar_one_or_none()
            if existing:
                return existing

        # 优先用当前已发布版本，保证重新发起吃到最新流程设计
        version = (await self.db.execute(select(WfProcessDefinitionVersion).where(
            WfProcessDefinitionVersion.tenant_id == self.tenant_id,
            WfProcessDefinitionVersion.process_definition_id == inst.process_definition_id,
            WfProcessDefinitionVersion.status == "published",
        ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()
        if not version:
            version = await self.db.get(WfProcessDefinitionVersion, inst.process_version_id)
        if not version:
            raise BusinessException(code=BUSINESS_ERROR, message="流程未发布，无法重新发起")

        form_data = await self._form_data(inst)
        title = inst.title
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                fi.status = "submitted"
                title = (fi.title or "").strip() or title
                form_data = dict(fi.form_data or {}) or form_data
        if inst.biz_type and inst.biz_id:
            from app.domains.lowcode.wf_biz_writeback import writeback
            await writeback(self.db, self.tenant_id, inst.biz_type, inst.biz_id, "submitted")

        self._log(inst.id, None, None, actor, "resubmit", "重新发起")
        await self.db.flush()

        new_inst = await self.submit(
            inst.process_definition_id, version, actor,
            form_instance_id=inst.form_instance_id,
            form_data=form_data, title=title,
            biz_type=inst.biz_type, biz_id=inst.biz_id,
            nominated=dict(inst.nominated_approvers or {}) or None,
        )
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                fi.status = new_inst.status
                fi.process_instance_id = new_inst.id
                await self.db.commit()
        return new_inst

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

    # ---------- 数据评论（对齐简道云，与审批意见无关） ----------

    async def add_comment(self, process_instance_id: str, actor: dict, content: str) -> None:
        text = (content or "").strip()
        if not text:
            raise BusinessException(code=VALIDATION_ERROR, message="请填写评论内容")
        inst = (await self.db.execute(select(WfProcessInstance).where(
            WfProcessInstance.id == process_instance_id,
            WfProcessInstance.tenant_id == self.tenant_id,
        ))).scalar_one_or_none()
        if not inst:
            raise BusinessException(code=NOT_FOUND, message="流程不存在")
        self.db.add(WfProcessComment(
            id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
            user_id=actor.get("sub"), user_name=actor.get("real_name"), content=text,
        ))
        await self.db.commit()
