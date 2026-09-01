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
- 并行出边两件事分开：
  1. 选路 ``_next_targets``：哪些支路要亮（条件 / 互斥 / always）；
  2. 激活顺序 ``activate_order``：亮了之后引擎按 1→2→3→4→5 去建待办。
  并行不是串行——五个节点都会创建，只是激活有先后，避免抄送抢先把主链收尾。
  未写 ``activate_order`` 时按相位：主链审批 → 抄送 → 结束；同相位保持连线定义序。

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


def _sort_exclusive_group_edges(edges: list, name_by_id: dict[str, str]) -> list:
    """互斥组内排序：工艺包装优先，其次有条件边，最后 else（对齐简道云实单）。"""
    return sorted(edges, key=lambda r: (
        0 if name_by_id.get(str(r.get("target") or "")) == "工艺包装" else
        1 if r.get("condition") else 2
    ))


# ==================== 引擎 ====================

# 同一出边批次的激活顺序（选路 _next_targets 只决定「谁该亮」，不决定「先亮谁」）
ADVANCE_PHASE_CORE = 1      # 主链：审批 / 并行网关 / 汇聚 / 直通
ADVANCE_PHASE_SIDECAR = 2   # 旁路：抄送（always 边），不得结束流程
ADVANCE_PHASE_END = 3       # 结束：必须等主链待办建出来之后
_ABORT_STATUSES = frozenset({"rejected", "terminated", "cancelled", "withdrawn"})


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
        # 同一出边批次深度：>0 时 completed 只登记、不落状态，防止旁路抄送抢先收尾
        self._advance_batch_depth = 0
        self._deferred_complete: tuple | None = None
        # 本批是否因「节点已完成」跳过激活（采购回路等才允许据此发明 end）
        self._skipped_reactivate_this_batch = False
        # 本批是否因多入边汇聚延后激活（不得据此发明 end / 补收尾）
        self._deferred_convergence_this_batch = False
        # 退回后 resubmit 整轮：后续 _advance 链也要允许重入已完成节点（如发货通知财务→物流）
        self._resubmit_reenter = False

    async def _has_downstream_approval(self, process_instance_id: str) -> bool:
        """下一节点（或任一审批节点）已有人审批通过 → 不可撤回。"""
        row = (await self.db.execute(
            select(WfTaskInstance.id).where(
                WfTaskInstance.process_instance_id == process_instance_id,
                WfTaskInstance.status == "approved",
            ).limit(1)
        )).scalar_one_or_none()
        return row is not None

    async def _running_by_form(self, form_instance_id: str) -> WfProcessInstance | None:
        if not form_instance_id:
            return None
        return (await self.db.execute(select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == self.tenant_id,
            WfProcessInstance.form_instance_id == form_instance_id,
            WfProcessInstance.status == "running",
        ).order_by(WfProcessInstance.created_at.asc()).limit(1))).scalar_one_or_none()

    async def _cancel_form_stale_revise(self, form_instance_id: str, *, keep_process_id: str | None) -> None:
        """新流程已在跑时，作废同表单其它实例上残留的「修改并重新提交」待办。"""
        if not form_instance_id:
            return
        q = select(WfProcessInstance.id).where(
            WfProcessInstance.tenant_id == self.tenant_id,
            WfProcessInstance.form_instance_id == form_instance_id,
        )
        if keep_process_id:
            q = q.where(WfProcessInstance.id != keep_process_id)
        ids = [r[0] for r in (await self.db.execute(q)).all()]
        for pid in ids:
            await self._cancel_initiator_revise_todos(pid)

    async def _cancel_biz_stale_revise(
        self, biz_type: str, biz_id: str, *, keep_process_id: str | None,
    ) -> None:
        """新业务流发起时，作废同 biz 其它实例上残留的「修改并重新提交」待办。"""
        if not biz_type or not biz_id:
            return
        q = select(WfProcessInstance.id).where(
            WfProcessInstance.tenant_id == self.tenant_id,
            WfProcessInstance.biz_type == biz_type,
            WfProcessInstance.biz_id == biz_id,
        )
        if keep_process_id:
            q = q.where(WfProcessInstance.id != keep_process_id)
        ids = [r[0] for r in (await self.db.execute(q)).all()]
        for pid in ids:
            await self._cancel_initiator_revise_todos(pid)

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
        assignee_id: str | None = None,
    ) -> None:
        """撤回/驳回/退回发起人后：给发起人（或指定人）一条「修改并重新提交」待办。"""
        uid = assignee_id or inst.initiator_id
        if not uid:
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
            assignee_id=uid,
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
    def _is_lead_intel_task_node(node_inst, *, biz_type: str | None = None) -> bool:
        """是否信息情报部审批节点（需走收录/袭击/回退）。业务员确认 / 修订待办返回 False。"""
        if not node_inst:
            return biz_type != "lead_reactivation"
        ntype = getattr(node_inst, "node_type", None) or ""
        ndef = getattr(node_inst, "node_def_id", None) or ""
        if biz_type == "lead_reactivation":
            if ntype == "revise" or ndef == REVISE_NODE_DEF_ID:
                return False
            return ndef == "approval_intel" or "情报" in (getattr(node_inst, "node_name", None) or "")
        if ntype == "revise" or ndef == REVISE_NODE_DEF_ID:
            return False
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

    async def _redirect_lead_confirm_if_skip_reporter(
        self, inst: WfProcessInstance, approvers: list[str],
    ) -> list[str]:
        """转商机确认：跳过名单改派填表人；无申报人时回退负责人/填表人。

        申报人改为手选后可为空。确认节点 empty_strategy=terminate，若这里不回退，
        情报免审通过后确认节点会把整单驳回，线索无法转化。
        """
        if not inst.biz_id or not self.db:
            return approvers
        from app.domains.lead.models import Lead
        from app.domains.lead.reactivation import (
            get_tenant_config,
            lead_confirm_assignee_id,
            should_skip_reporter,
        )

        ld = await self.db.get(Lead, inst.biz_id)
        if not ld:
            return approvers
        cfg = await get_tenant_config(self.db, self.tenant_id)
        uid = (lead_confirm_assignee_id(ld, cfg) or "").strip()
        if should_skip_reporter(ld, cfg):
            if not uid:
                return approvers
            if approvers != [uid]:
                self._log(
                    inst.id, None, None, {"sub": "system"}, "lead_confirm_redirect",
                    f"申报人「{ld.reporter_name or ''}」跳过，转商机确认改派填表人",
                )
            return [uid]
        if approvers:
            return approvers
        return [uid] if uid else approvers

    async def _mark_lead_approved_after_intel(self, inst: WfProcessInstance, node) -> None:
        """情报节点通过/空审跳过后立刻 approved（流程可能还要走业务员确认）。

        与 intel_review_lead(include) 对齐：不能等整单 writeback，否则转化门禁一直卡 pending。
        同时清空旧驳回原因，避免详情页残留上一轮文案。
        """
        if inst.biz_type != "lead" or not inst.biz_id:
            return
        if not self._is_lead_intel_task_node(node, biz_type=inst.biz_type):
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
        import os
        if os.environ.get("PYTEST_CURRENT_TEST"):
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

    def _incoming_count(self, version: WfProcessDefinitionVersion, node_id: str) -> int:
        return len([r for r in (version.route_definitions or []) if r.get("target") == node_id])

    def _route_adjacency(self, version: WfProcessDefinitionVersion) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = {}
        for r in version.route_definitions or []:
            src, tgt = r.get("source"), r.get("target")
            if src and tgt:
                adj.setdefault(str(src), []).append(str(tgt))
        return adj

    def _can_reach(self, version: WfProcessDefinitionVersion, src: str, dst: str) -> bool:
        """静态图可达（不评估条件）：用于多入边审批节点的隐式汇聚。"""
        if str(src) == str(dst):
            return True
        adj = self._route_adjacency(version)
        seen = {str(src)}
        stack = [str(src)]
        while stack:
            cur = stack.pop()
            for nxt in adj.get(cur, []):
                if nxt == str(dst):
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False

    async def _other_running_can_reach(
        self, inst: WfProcessInstance, version: WfProcessDefinitionVersion, target_node_id: str,
    ) -> bool:
        """是否仍有其它在途审批节点可到达 target（隐式 AND-join）。"""
        rows = (await self.db.execute(
            select(WfNodeInstance.node_def_id).where(
                WfNodeInstance.process_instance_id == inst.id,
                WfNodeInstance.status == "running",
                WfNodeInstance.node_type == "approval",
            )
        )).scalars().all()
        return any(
            self._can_reach(version, str(nid), str(target_node_id))
            for nid in rows if nid
        )

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
          有条件边，否则走组内无条件边(else)；「工艺包装」在同组内始终优先评估
        - 无 ``exclusive_group`` 的普通边：仍可多条条件同时命中（并行）；
          若这些并行边中无一条件命中，则走其中无条件边
        返回顺序不等于激活顺序。激活见 ``_order_advance_targets`` /
        ``explain_advance_batch``（连线 ``activate_order`` + 相位）。
        """
        routes = self._outgoing(version, node_id)
        always_routes = [r for r in routes if r.get("always")]
        normal = [r for r in routes if not r.get("always")]
        name_by_id = {
            str(n.get("id") or ""): str(n.get("name") or "")
            for n in (version.node_definitions or [])
            if isinstance(n, dict) and n.get("id")
        }

        exclusive_groups: dict[str, list] = {}
        parallel_edges: list = []
        for r in normal:
            # 简道云 cond=[] → __always：恒真并行，即使误标了 exclusive_group 也不进互斥
            cond = r.get("condition") if isinstance(r, dict) else None
            is_always_parallel = (
                isinstance(cond, dict)
                and cond.get("field") == "__always"
                and cond.get("operator") == "is_empty"
            )
            gid = r.get("exclusive_group")
            if gid and not is_always_parallel:
                exclusive_groups.setdefault(str(gid), []).append(r)
            else:
                parallel_edges.append(r)

        # 缺 exclusive_group 的经典 if/else（若干有条件边 + 恰好一条无条件 else）
        # 按互斥处理，避免部门审批→市场支持∥总工双开（发布版漏标互斥组时的兜底）。
        # 显式 fork=parallel、或两条及以上无条件边、或全是条件边：仍并行。
        if not any(r.get("fork") == "parallel" for r in parallel_edges):
            if_else = [r for r in parallel_edges if r.get("condition")]
            if_else_blank = [r for r in parallel_edges if not r.get("condition")]
            if if_else and len(if_else_blank) == 1 and len(parallel_edges) == len(if_else) + 1:
                exclusive_groups.setdefault("__auto_if_else__", []).extend(
                    [*if_else, *if_else_blank]
                )
                parallel_edges = []

        core: list[str] = []
        for edges in exclusive_groups.values():
            ordered = _sort_exclusive_group_edges(edges, name_by_id)
            hit: str | None = None
            for r in ordered:
                cond = r.get("condition")
                if cond and evaluate_condition(cond, form_data):
                    hit = r["target"]
                    break
            if hit:
                core.append(hit)
            else:
                # else 只走组内第一条无条件边。条件被 sanitize 清成 null 后若残留
                # 多条「假 else」，全部放行会把串行节点双开（报价：部门审批∥财务核价）。
                for r in ordered:
                    if not r.get("condition"):
                        core.append(r["target"])
                        break

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
        entry_node_id: str | None = None,
    ) -> WfProcessInstance:
        start = self._start_node(version)
        if not start:
            raise BusinessException(code=VALIDATION_ERROR, message="流程缺少开始节点")

        if form_instance_id:
            existing = await self._running_by_form(form_instance_id)
            if existing:
                await self._cancel_form_stale_revise(form_instance_id, keep_process_id=existing.id)
                return existing

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
        if form_instance_id:
            await self._cancel_form_stale_revise(form_instance_id, keep_process_id=inst.id)
        if biz_type and biz_id:
            await self._cancel_biz_stale_revise(biz_type, biz_id, keep_process_id=inst.id)

        ctx = ApprovalContext(initiator_id=initiator.get("sub"), form_data=form_data or {}, nominated=nominated or {})
        # 生命周期事件必须按发生顺序入队: submitted 要早于 _advance 可能产生的
        # approved/rejected,否则流程在提交过程中直接走完时下游会先收到结束事件。
        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(self.db, self.tenant_id, "workflow.submitted", inst)
        if entry_node_id:
            nodes = self._nodes_by_id(version)
            entry = nodes.get(entry_node_id)
            if not entry:
                raise BusinessException(
                    code=VALIDATION_ERROR,
                    message=f"流程缺少入口节点: {entry_node_id}",
                )
            await self._activate_node(inst, version, entry, ctx)
        else:
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
            "withdraw": "撤回审批", "resubmit": "重新发起", "activate": "激活流程",
        }
        await wf_notify.audit(
            self.db, self.tenant_id, inst, actor, f"wf_{action}",
            f"{labels.get(action, action)}: {inst.title or inst.biz_type or ''}",
        )

    def _advance_phase(self, node: dict | None) -> int:
        """相位：主链(1) → 抄送(2) → 结束(3)。抄送不能排到审批前面。"""
        t = (node or {}).get("type")
        if t == "end":
            return ADVANCE_PHASE_END
        if t == "cc":
            return ADVANCE_PHASE_SIDECAR
        return ADVANCE_PHASE_CORE

    def _route_activate_order(self, route: dict | None) -> int:
        """连线 activate_order：同一相位内越小越先。未写视为 0（保持定义序）。"""
        if not isinstance(route, dict):
            return 0
        raw = route.get("activate_order", route.get("priority"))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def _route_for_target(self, version: WfProcessDefinitionVersion, from_node_id: str, target_id: str) -> dict | None:
        for r in self._outgoing(version, from_node_id):
            if isinstance(r, dict) and r.get("target") == target_id:
                return r
        return None

    def _order_advance_targets(
        self, version: WfProcessDefinitionVersion, from_node_id: str, targets: list[str],
    ) -> list[str]:
        """并行批次激活序：相位 → activate_order → 选路原序。"""
        nodes = self._nodes_by_id(version)
        keyed: list[tuple[int, int, int, str]] = []
        for i, tid in enumerate(targets):
            node = nodes.get(tid)
            if not node:
                continue
            route = self._route_for_target(version, from_node_id, tid)
            keyed.append((
                self._advance_phase(node),
                self._route_activate_order(route),
                i,
                tid,
            ))
        keyed.sort()
        return [tid for _, _, _, tid in keyed]

    def explain_advance_batch(
        self, version: WfProcessDefinitionVersion, from_node_id: str,
        form_data: dict | None = None,
    ) -> list[dict]:
        """同一出边将按此顺序激活（全部都会亮，这是先后不是互斥）。"""
        nodes = self._nodes_by_id(version)
        targets = self._next_targets(version, from_node_id, form_data or {})
        ordered = self._order_advance_targets(version, from_node_id, targets)
        out: list[dict] = []
        for seq, tid in enumerate(ordered, start=1):
            node = nodes.get(tid) or {}
            route = self._route_for_target(version, from_node_id, tid) or {}
            out.append({
                "seq": seq,
                "id": tid,
                "name": node.get("name") or tid,
                "type": node.get("type"),
                "phase": self._advance_phase(node),
                "activate_order": self._route_activate_order(route),
                "always": bool(route.get("always")),
            })
        return out

    # ---------- 推进到下一节点 ----------

    def _should_invent_end(
        self, from_node: dict, ordered: list[str], nodes: dict[str, dict],
        *, has_live_work: bool, skipped_reactivate: bool, deferred_convergence: bool = False,
    ) -> bool:
        """无在途待办时要不要发明 end。

        - 仍有并行支路/待办：不收尾（等收敛）
        - 从抄送节点推进：不收尾（避免同批抢跑；抄送相位本来就在主链后）
        - 后继全是旁路抄送且已无在途：收尾（生产卡「销售订单→结束」与「安排设计→抄送」
          并行时，先到结束会被挡住；设计支路后走完只剩抄送，必须在此补收尾）
        - 主链目标被 skip_reactivate：可收尾；主链仍会激活则不发明 end
        - 主链目标被 defer_convergence 延后：不收尾
        """
        if has_live_work or deferred_convergence:
            return False
        if (from_node or {}).get("type") == "cc":
            return False
        phases = [self._advance_phase(nodes.get(t)) for t in ordered]
        if ordered and all(p == ADVANCE_PHASE_SIDECAR for p in phases):
            return True
        if any(p == ADVANCE_PHASE_CORE for p in phases) and not skipped_reactivate:
            return False
        return True

    def _mark_await_end(self, inst: WfProcessInstance) -> None:
        """结束被并行支路挡住：记一笔，收敛后由 _try_finish_await_end 补收尾。"""
        raw = inst.pending_joins
        items: list = list(raw) if isinstance(raw, list) else ([] if raw is None else [raw])
        if any(isinstance(x, dict) and x.get("await_end") for x in items):
            return
        items.append({"await_end": True})
        inst.pending_joins = items
        try:
            flag_modified(inst, "pending_joins")
        except Exception:
            pass

    def _clear_await_end(self, inst: WfProcessInstance) -> None:
        raw = inst.pending_joins
        if not isinstance(raw, list):
            return
        nxt = [x for x in raw if not (isinstance(x, dict) and x.get("await_end"))]
        if len(nxt) == len(raw):
            return
        inst.pending_joins = nxt or None
        try:
            flag_modified(inst, "pending_joins")
        except Exception:
            pass

    def _has_await_end(self, inst: WfProcessInstance) -> bool:
        raw = inst.pending_joins
        if not isinstance(raw, list):
            return False
        return any(isinstance(x, dict) and x.get("await_end") for x in raw)

    def _has_pending_convergence(self, inst: WfProcessInstance) -> bool:
        raw = getattr(inst, "pending_joins", None)
        if not isinstance(raw, list):
            return False
        return any(isinstance(x, dict) and x.get("pending_convergence") for x in raw)

    def _mark_pending_convergence(self, inst: WfProcessInstance, node_id: str) -> None:
        raw = getattr(inst, "pending_joins", None)
        items: list = list(raw) if isinstance(raw, list) else ([] if raw is None else [raw])
        if any(isinstance(x, dict) and x.get("pending_convergence") == node_id for x in items):
            return
        items.append({"pending_convergence": node_id})
        inst.pending_joins = items
        try:
            flag_modified(inst, "pending_joins")
        except Exception:
            pass

    def _clear_pending_convergence(self, inst: WfProcessInstance, node_id: str) -> None:
        raw = getattr(inst, "pending_joins", None)
        if not isinstance(raw, list):
            return
        nxt = [
            x for x in raw
            if not (isinstance(x, dict) and x.get("pending_convergence") == node_id)
        ]
        inst.pending_joins = nxt or None
        try:
            flag_modified(inst, "pending_joins")
        except Exception:
            pass

    def _has_reenter_session(self, inst: WfProcessInstance) -> bool:
        """退回/重提/激活后跨请求推进：允许重入已完成节点直至流程终态。"""
        raw = getattr(inst, "pending_joins", None)
        if not isinstance(raw, list):
            return False
        return any(isinstance(x, dict) and x.get("reenter_session") for x in raw)

    def _mark_reenter_session(self, inst: WfProcessInstance) -> None:
        raw = getattr(inst, "pending_joins", None)
        items: list = list(raw) if isinstance(raw, list) else ([] if raw is None else [raw])
        if any(isinstance(x, dict) and x.get("reenter_session") for x in items):
            return
        items.append({"reenter_session": True})
        inst.pending_joins = items
        try:
            flag_modified(inst, "pending_joins")
        except Exception:
            pass

    def _clear_reenter_session(self, inst: WfProcessInstance) -> None:
        raw = getattr(inst, "pending_joins", None)
        if not isinstance(raw, list):
            return
        nxt = [x for x in raw if not (isinstance(x, dict) and x.get("reenter_session"))]
        if len(nxt) == len(raw):
            return
        inst.pending_joins = nxt or None
        try:
            flag_modified(inst, "pending_joins")
        except Exception:
            pass

    async def _try_finish_await_end(
        self, inst: WfProcessInstance, version: WfProcessDefinitionVersion, ctx: ApprovalContext,
    ) -> None:
        """并行支路都收敛且曾有人到达结束：补激活 end。"""
        if self.db is None or inst.status != "running":
            return
        if not self._has_await_end(inst):
            return
        if self._has_pending_convergence(inst):
            return
        if await self._has_live_work(inst):
            return
        end = next(
            (n for n in (version.node_definitions or []) if n.get("type") == "end"),
            None,
        )
        if not end:
            return
        self._clear_await_end(inst)
        await self._activate_node(inst, version, end, ctx)

    def _specified_rule_has_value(self, rule: dict | None) -> bool:
        if not isinstance(rule, dict) or rule.get("type") != "specified_user":
            return False
        return bool(ApproverResolver._as_list(rule.get("value")))

    async def _advance(
        self, inst: WfProcessInstance, version: WfProcessDefinitionVersion,
        from_node_id: str, ctx: ApprovalContext, *, force_reenter: bool = False,
    ) -> None:
        force_reenter = force_reenter or self._resubmit_reenter or self._has_reenter_session(inst)
        targets = self._next_targets(version, from_node_id, ctx.form_data)
        nodes = self._nodes_by_id(version)
        # 报价「采购→财务核价」等回路：连线标 reenter 时允许再次激活已完成节点
        reenter_targets = {
            r.get("target")
            for r in self._outgoing(version, from_node_id)
            if isinstance(r, dict) and (r.get("reenter") or r.get("allow_reenter"))
        }
        ordered = self._order_advance_targets(version, from_node_id, targets)
        self._skipped_reactivate_this_batch = False
        self._deferred_convergence_this_batch = False
        self._advance_batch_depth += 1
        try:
            for tid in ordered:
                node = nodes.get(tid)
                if not node:
                    continue
                await self._activate_node(
                    inst, version, node, ctx,
                    allow_reenter=force_reenter or tid in reenter_targets,
                )
                if inst.status in _ABORT_STATUSES:
                    self._deferred_complete = None
                    return
        finally:
            self._advance_batch_depth -= 1
        # 后继全部 skip_reactivate（或无出边）且无在途待办时收尾，避免采购回路卡住。
        # 抄送节点本身无出边，不能从抄送收尾——否则会抢在同批审批激活之前结束流程。
        from_node = nodes.get(from_node_id) or {}
        live = bool(self.db is not None and await self._has_live_work(inst))
        if (
            self.db is not None
            and inst.status == "running"
            and self._should_invent_end(
                from_node, ordered, nodes,
                has_live_work=live,
                skipped_reactivate=self._skipped_reactivate_this_batch,
                deferred_convergence=self._deferred_convergence_this_batch,
            )
        ):
            end = next(
                (n for n in (version.node_definitions or []) if n.get("type") == "end"),
                None,
            )
            if end:
                await self._activate_node(inst, version, end, ctx)
        await self._try_finish_await_end(inst, version, ctx)
        await self._flush_deferred_complete(inst)

    async def _activate_node(self, inst: WfProcessInstance, version: WfProcessDefinitionVersion,
                             node: dict, ctx: ApprovalContext, *, allow_reenter: bool = False) -> None:
        ntype = node.get("type")
        if ntype == "end":
            # 主链与旁路抄送可能并行：抄送先「到达」end 时，审批节点/待办仍在，
            # 不能提前 completed（否则会出现表头已通过、图纸领取仍处理中）。
            if await self._has_live_work(inst):
                self._mark_await_end(inst)
                return
            self._clear_await_end(inst)
            await self._complete_instance(inst, "completed")
            return
        if ntype == "cc":
            await self._create_cc(inst, version, node, ctx)
            # 无出边的旁路抄送到此为止，禁止再走「无待办则收尾」把同批审批吃掉
            if self._outgoing(version, node["id"]):
                await self._advance(inst, version, node["id"], ctx)
            return
        if ntype == "approval":
            await self._activate_approval(
                inst, version, node, ctx, allow_reenter=allow_reenter,
            )
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

    async def _activate_approval(
        self, inst, version, node, ctx, *, allow_reenter: bool = False,
    ) -> None:
        # 并行分叉汇入同一审批节点时（如 研究院安排∥工艺包装 → 再入研究院安排）：
        # 已有进行中的同定义节点则跳过，避免重复建待办。
        # 另：部门审批 if/else 失效导致「市场支持∥总工」双开时，总工先完成并推进到
        # 设计指派后，晚到的「市场支持→总工」不能再激活第二个总工（退回重入除外）。
        if self.db is not None:
            existing_running = (await self.db.execute(
                select(WfNodeInstance.id).where(
                    WfNodeInstance.process_instance_id == inst.id,
                    WfNodeInstance.node_def_id == node["id"],
                    WfNodeInstance.status == "running",
                ).limit(1)
            )).scalar_one_or_none()
            if existing_running:
                return
            if not allow_reenter:
                done_ni = (await self.db.execute(
                    select(WfNodeInstance).where(
                        WfNodeInstance.process_instance_id == inst.id,
                        WfNodeInstance.node_def_id == node["id"],
                        WfNodeInstance.status == "completed",
                    ).order_by(WfNodeInstance.completed_at.desc()).limit(1)
                )).scalar_one_or_none()
                if done_ni:
                    cfg = done_ni.config if isinstance(done_ni.config, dict) else {}
                    # 曾因无审批人 auto_approve：表单已补人则允许重开（如售前人员协调）
                    if cfg.get("auto_approve"):
                        retry = await self._resolve_approvers(version, node, ctx)
                        if retry:
                            pass
                        else:
                            self._skipped_reactivate_this_batch = True
                            self._log(
                                inst.id, None, None, {"sub": "system"}, "skip_reactivate",
                                f"节点「{node.get('name') or node['id']}」已完成，跳过晚到汇入的重复激活",
                            )
                            return
                    else:
                        self._skipped_reactivate_this_batch = True
                        self._log(
                            inst.id, None, None, {"sub": "system"}, "skip_reactivate",
                            f"节点「{node.get('name') or node['id']}」已完成，跳过晚到汇入的重复激活",
                        )
                        return
            # 多入边审批节点（如生产卡「销售订单登记」）：简道云会等所有仍可能
            # 汇入的在途分支结束后再开待办；无显式 merge 节点时在此做隐式汇聚。
            # 与 allow_reenter 无关：退回/激活后的 reenter_session 仍需等待并行支路。
            if (
                self._incoming_count(version, node["id"]) > 1
                and await self._other_running_can_reach(inst, version, node["id"])
            ):
                self._deferred_convergence_this_batch = True
                self._mark_pending_convergence(inst, node["id"])
                self._log(
                    inst.id, None, None, {"sub": "system"}, "defer_convergence",
                    f"节点「{node.get('name') or node['id']}」尚有在途分支未汇入，延后激活",
                )
                return

        self._clear_pending_convergence(inst, node["id"])

        # 线索袭击：不可转化，跳过「业务员确认是否转商机」待办，改为知会申报人后直通结束
        if (
            inst.biz_type == "lead"
            and self._is_lead_owner_confirm_node(node)
            and await self._lead_is_attacked(inst)
        ):
            users = await self._resolve_approvers(version, node, ctx)
            users = await self._redirect_lead_confirm_if_skip_reporter(inst, users)
            ni = WfNodeInstance(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                node_def_id=node["id"], node_type="approval",
                node_name=node.get("name") or "业务员确认是否转商机",
                status="completed", config={"skipped": "attacked"},
                started_at=_now(), completed_at=_now(),
            )
            self.db.add(ni)
            await self.db.flush()
            # 须写入 wf_process_cc，否则只有站内通知、「抄送我的」为空
            for uid in users:
                self.db.add(WfProcessCc(
                    id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                    node_instance_id=ni.id, user_id=uid, is_read=False,
                ))
            await self.db.flush()
            self._log(inst.id, ni.id, None, {"sub": "system"}, "auto_skip",
                      "线索已标记袭击，跳过业务员确认")
            if users:
                self._queue("cc_notified", list(users), node.get("name") or "业务员确认是否转商机", inst)
            await self._advance(inst, version, node["id"], ctx)
            return

        approvers = await self._resolve_approvers(version, node, ctx)
        if inst.biz_type == "lead" and self._is_lead_owner_confirm_node(node):
            approvers = await self._redirect_lead_confirm_if_skip_reporter(inst, approvers)
        if not approvers:
            strategy = node.get("empty_strategy") or (node.get("config") or {}).get("empty_strategy") or "auto_approve"
            node_name = node.get("name") or "审批"
            rule = self._approver_rule(version, node) or {}
            # 节点写了指定人：人在组织里就该建待办，禁止「找不到就自动过」把主链吃掉。
            if self._specified_rule_has_value(rule):
                logger.error(
                    "specified_user unresolved: node=%s value=%s process=%s",
                    node_name, rule.get("value"), inst.id,
                )
                ni = WfNodeInstance(
                    id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                    node_def_id=node["id"], node_type="approval",
                    node_name=node_name, status="running",
                    config={"unresolved_approver": True, "specified": rule.get("value")},
                    started_at=_now(),
                )
                self.db.add(ni)
                await self.db.flush()
                self._log(
                    inst.id, ni.id, None, {"sub": "system"}, "unresolved_approver",
                    f"节点「{node_name}」指定审批人未匹配到在职账号，已挂起（不自动通过）",
                )
                self._queue("empty_auto_approved", node_name, inst)
                return
            if strategy == "terminate":
                await self._complete_instance(inst, "rejected", reason=f"节点「{node_name}」无审批人,流程终止")
                self._log(inst.id, None, None, {"sub": "system"}, "auto_reject", "无审批人,流程终止")
                return
            # auto_approve: 跳过本节点。须落 wf_node_instance，否则流程动态只见首尾（对齐简道云每步可见）。
            now = _now()
            ni = WfNodeInstance(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                node_def_id=node["id"], node_type="approval",
                node_name=node_name, status="completed",
                config={"auto_approve": True, "empty_strategy": strategy},
                started_at=now, completed_at=now,
            )
            self.db.add(ni)
            await self.db.flush()
            self._log(
                inst.id, ni.id, None, {"sub": "system", "real_name": "系统"},
                "auto_approve", f"节点「{node_name}」无审批人，自动通过",
            )
            self._queue("empty_auto_approved", node_name, inst)
            await self._mark_lead_approved_after_intel(inst, node)
            await self._advance(inst, version, node["id"], ctx)
            return

        mode = node.get("multi_mode") or (node.get("config") or {}).get("multi_mode") or "or_sign"
        # and_sign：简道云/历史别名 → 标准会签 countersign
        if mode == "and_sign":
            mode = "countersign"
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
        # 简道云「启用抄送」：进审批节点时同步知会抄送人（对齐通知生产等）
        await self._attach_approval_node_cc(inst, version, node, ni, ctx)
        if inst.biz_type == "lead_reactivation" and inst.biz_id:
            from app.domains.lead.reactivation import sync_reactivation_status_from_wf
            await sync_reactivation_status_from_wf(self.db, self.tenant_id, inst.biz_id)

    async def _attach_approval_node_cc(self, inst, version, node, ni, ctx) -> None:
        """审批节点上的 cc_rule：进节点即抄送（简道云启用抄送）。

        只写 wf_process_cc + 通知，不另记 action=cc 日志，避免流程动态出现两条「抄送」。
        """
        rule = node.get("cc_rule") or (node.get("config") or {}).get("cc_rule")
        if not isinstance(rule, dict) or not rule:
            return
        try:
            users = await self._approver_resolver.resolve(
                {**rule, "node_id": node.get("id")}, ctx,
            )
        except NoApproverError:
            users = []
        if not users:
            return
        seen: set[str] = set()
        for uid in users:
            if not uid or uid in seen:
                continue
            seen.add(uid)
            self.db.add(WfProcessCc(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                node_instance_id=ni.id, user_id=uid, is_read=False,
            ))
        await self.db.flush()
        self._queue("cc_notified", list(seen), node.get("name") or "审批抄送", inst)

    async def _after_lead_reactivation_node_done(self, inst, ni, task) -> None:
        """业务员/内勤节点完成后写入激活单。"""
        from app.domains.lead.models import Lead
        from app.domains.lead.reactivation import (
            REACT_FILLER_FILL_NODE_IDS,
            REACT_NODE_SALES,
            upsert_reactivation_record_for_user,
        )
        if ni.node_def_id != REACT_NODE_SALES and ni.node_def_id not in REACT_FILLER_FILL_NODE_IDS:
            return
        lead = await self.db.get(Lead, inst.biz_id)
        if not lead:
            return
        actor = {
            "sub": task.assignee_id,
            "real_name": getattr(task, "assignee_name", None),
            "username": getattr(task, "assignee_name", None),
        }
        await upsert_reactivation_record_for_user(
            self.db, self.tenant_id, lead, actor,
        )

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
                  transfer_to: str | list[str] | None = None, return_to: str | None = None,
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
            if inst.status not in ("withdrawn", "rejected", "returned"):
                raise BusinessException(code=BUSINESS_ERROR, message="当前状态不可重新提交")
            # 客户已审批通过但旧实例修订待办未清：直接作废，避免「待我修改」悬挂
            if inst.biz_type == "customer" and inst.biz_id:
                from app.domains.customer.models import Customer
                cu = await self.db.get(Customer, inst.biz_id)
                if cu and getattr(cu, "review_status", None) == "approved":
                    await self._cancel_initiator_revise_todos(inst.id)
                    task.status = "cancelled"
                    task.action_at = _now()
                    self._log(inst.id, task.node_instance_id, task.id, actor, "cancel", "客户已审批通过，关闭残留修订待办")
                    await self.db.commit()
                    return
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

        # 线索 / 180天激活：情报节点必须走情报裁定
        if (
            inst.biz_type in ("lead", "lead_reactivation")
            and action in ("approve", "reject")
            and not allow_lead_intel
            and self._is_lead_intel_task_node(node_inst, biz_type=inst.biz_type)
        ):
            msg = (
                "180天激活请使用情报审批（收录/袭击/回退）"
                if inst.biz_type == "lead_reactivation"
                else "线索审核请使用情报审批（收录/袭击/回退/驳回），不可直接通过或驳回"
            )
            raise BusinessException(code=VALIDATION_ERROR, message=msg)

        version = await self.db.get(WfProcessDefinitionVersion, inst.process_version_id)
        ctx = ApprovalContext(initiator_id=inst.initiator_id, form_data=await self._form_data(inst),
                              nominated=inst.nominated_approvers or {})

        node_def_id = node_inst.node_def_id if node_inst else None
        node_def = self._nodes_by_id(version).get(node_def_id or "") or {}
        from app.domains.lowcode.wf_node_actions import node_action_allowed
        _action_gate = {
            "approve": "submit",
            "resubmit": "submit",
            "save": "save",
            "transfer": "transfer",
            "return": "return",
            "reject": "reject",
        }
        gate = _action_gate.get(action)
        if gate and not node_action_allowed(node_def, gate, biz_type=inst.biz_type):
            raise BusinessException(code=VALIDATION_ERROR, message="当前节点未启用该操作")

        # 审批通过：按节点 field_perms 写回业务字段（对齐简道云 optAuth）
        if action == "approve":
            await self._apply_node_field_updates(
                inst, version, task, field_updates, opinion=opinion, action=action, actor=actor,
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

        if action == "save":
            # 暂存：写回本节点可填字段，不推进流程、不完结待办
            await self._apply_node_field_updates(
                inst, version, task, field_updates, opinion=opinion, action=action, actor=actor,
            )
            await self.db.commit()
            return

        if action == "transfer":
            targets = self._normalize_transfer_targets(transfer_to)
            if not targets:
                raise BusinessException(code=VALIDATION_ERROR, message="转交需指定接收人")
            await self._transfer_task(inst, task, actor, targets, opinion)
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
                await self._return_to_initiator_flow(
                    inst, reason=opinion, current_node_id=task.node_instance_id,
                )
                revise_assignee = inst.initiator_id
                # 线索回退：优先给申报人改完再提（对齐业务口径）
                if inst.biz_type == "lead" and inst.biz_id:
                    from app.domains.lead.models import Lead
                    ld = await self.db.get(Lead, inst.biz_id)
                    if ld and getattr(ld, "reporter_id", None):
                        revise_assignee = ld.reporter_id
                await self._create_initiator_revise_todo(
                    inst, reason=opinion, assignee_id=revise_assignee,
                )
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
        from app.domains.lowcode import shipment_notice_events as sne
        await sne.emit_from_process(
            self.db, self.tenant_id, sne.EVENT_ACTED, inst,
            {"action": action, "opinion": opinion},
        )
        await self.db.commit()
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "approve")

    async def sync_lead_owner_confirm_after_qualify(
        self, lead_id: str, actor: dict, *, opinion: str | None = None,
    ) -> bool:
        """线索已通过 qualify 转化后，自动完结「业务员确认是否转商机」在途待办。

        顶部「转商机」按钮只调 qualify、不走流程审批时，用此方法消除流程/业务不同步。
        """
        inst = (await self.db.execute(
            select(WfProcessInstance).where(
                WfProcessInstance.tenant_id == self.tenant_id,
                WfProcessInstance.biz_type == "lead",
                WfProcessInstance.biz_id == lead_id,
                WfProcessInstance.status == "running",
            ).order_by(WfProcessInstance.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if not inst:
            return False

        rows = (await self.db.execute(
            select(WfTaskInstance, WfNodeInstance).join(
                WfNodeInstance, WfTaskInstance.node_instance_id == WfNodeInstance.id,
            ).where(
                WfTaskInstance.tenant_id == self.tenant_id,
                WfTaskInstance.process_instance_id == inst.id,
                WfTaskInstance.status == "pending",
            )
        )).all()

        target_task = None
        for task, ni in rows:
            if self._is_lead_owner_confirm_node({"id": ni.node_def_id, "name": ni.node_name}):
                target_task = task
                break
        if not target_task:
            return False

        op = (opinion or "").strip() or "确认转商机"
        target_task.status = "approved"
        target_task.opinion = op
        target_task.action_at = _now()
        target_task.version += 1
        self._log(inst.id, target_task.node_instance_id, target_task.id, actor, "approve", op)
        self._queue("todo_done_explicit", target_task.assignee_id, getattr(target_task, "dingtalk_todo_id", None))

        version = await self.db.get(WfProcessDefinitionVersion, inst.process_version_id)
        ctx = ApprovalContext(
            initiator_id=inst.initiator_id,
            form_data=await self._form_data(inst),
            nominated=inst.nominated_approvers or {},
        )
        await self._on_task_approved(inst, version, target_task, ctx)
        from app.domains.lowcode import shipment_notice_events as sne
        await sne.emit_from_process(
            self.db, self.tenant_id, sne.EVENT_ACTED, inst,
            {"action": "approve", "opinion": op, "sync_after_qualify": True},
        )
        await self.db.commit()
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "approve")
        return True

    async def _apply_node_field_updates(
        self, inst, version, task, field_updates: dict | None, *,
        opinion: str | None, action: str, actor: dict,
    ) -> None:
        from app.domains.lowcode.wf_field_writeback import (
            apply_field_updates, parse_field_perms, validate_field_updates,
            preview_field_update_changes, audit_resource_for_process,
        )
        node_inst = await self.db.get(WfNodeInstance, task.node_instance_id)
        node_def_id = node_inst.node_def_id if node_inst else None
        node = self._nodes_by_id(version).get(node_def_id or "") or {}
        perms = parse_field_perms(node)
        try:
            from app.domains.lowcode.workflow_service import _published_version
            latest_pub = await _published_version(self.db, self.tenant_id, inst.process_definition_id)
            if latest_pub and (not version or latest_pub.id != version.id):
                by_id = {
                    n.get("id"): n for n in (latest_pub.node_definitions or [])
                    if isinstance(n, dict) and n.get("id")
                }
                by_name = {
                    n.get("name"): n for n in (latest_pub.node_definitions or [])
                    if isinstance(n, dict) and n.get("name")
                }
                latest_node = by_id.get(node_def_id or "") or by_name.get(node.get("name") or "")
                if latest_node:
                    # 在途单冻结旧版 field_perms 时，以最新发布版本节点可填区为准
                    perms = parse_field_perms(latest_node)
                    node = latest_node
        except Exception:
            pass
        from app.domains.lowcode.prod_card_contract_fill import filter_prod_card_legacy_field_perms
        perms = filter_prod_card_legacy_field_perms(perms)
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
        if action == "approve":
            from app.domains.lowcode.wf_submit_validation import assert_node_submit_validations
            assert_node_submit_validations(
                node,
                form_data=form_data,
                field_updates=filtered,
                form_fields=form_fields,
                action=action,
                current_user_name=actor.get("real_name") or actor.get("username") or "",
            )
        if action in ("approve", "save") and filtered:
            await self._assert_person_field_values(inst.biz_type, filtered)
            if action == "approve":
                await self._assert_pickable_scope(inst, filtered)
        if filtered:
            changes = await preview_field_update_changes(
                self.db, self.tenant_id,
                biz_type=inst.biz_type, biz_id=inst.biz_id,
                form_instance_id=inst.form_instance_id,
                updates=filtered,
            )
            await apply_field_updates(
                self.db, self.tenant_id,
                biz_type=inst.biz_type, biz_id=inst.biz_id,
                form_instance_id=inst.form_instance_id,
                updates=filtered,
            )
            if changes:
                try:
                    from app.domains.lowcode.form_audit import log_form_instance_changes
                    node_name = node.get("name") or "审批节点"
                    audit_summary = f"{node_name} 暂存" if action == "save" else f"{node_name} 修改字段"
                    resource_type, resource_id = audit_resource_for_process(
                        form_instance_id=inst.form_instance_id,
                        biz_type=inst.biz_type,
                        biz_id=inst.biz_id,
                        process_instance_id=inst.id,
                    )
                    if resource_type == "form_instance":
                        await log_form_instance_changes(
                            self.db,
                            tenant_id=self.tenant_id,
                            user_id=actor.get("sub"),
                            user_name=actor.get("real_name") or actor.get("username"),
                            form_instance_id=resource_id,
                            field_defs=form_fields,
                            changes=changes,
                            action="update",
                            summary=audit_summary,
                        )
                    else:
                        from app.domains.audit.service import log_action
                        from app.common.audit_diff import enrich_changes_with_labels
                        from app.domains.lowcode.wf_field_writeback import audit_labels_for_biz
                        labeled = enrich_changes_with_labels(
                            changes, audit_labels_for_biz(inst.biz_type, form_fields),
                        )
                        await log_action(
                            self.db, tenant_id=self.tenant_id,
                            user_id=actor.get("sub"),
                            user_name=actor.get("real_name") or actor.get("username"),
                            action="update",
                            resource_type=resource_type,
                            resource_id=resource_id,
                            summary=audit_summary,
                            detail={"changes": labeled},
                        )
                except Exception:
                    pass

    async def _assert_pickable_scope(self, inst, updates: dict) -> None:
        """人员/部门字段若配置了 pickable_scope，所选值必须在范围内。"""
        from sqlalchemy import select
        from app.common.exceptions import BusinessException
        from app.common.error_codes import VALIDATION_ERROR
        from app.domains.auth.models import User, Role, UserRole
        from app.domains.organization.models import Department
        from app.domains.lowcode.pickable_scope import (
            role_codes_from_field, scope_code_from_field, filter_by_fields_from_field,
            dept_ids_from_field, include_children_from_field,
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
                if scode:
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
                else:
                    range_depts = dept_ids_from_field(fd)
                    if not range_depts:
                        continue
                    allowed_depts = await pss.resolve_department_ids(
                        self.db, self.tenant_id,
                        {
                            "kind": "department",
                            "rules": {
                                "dept_ids": range_depts,
                                "include_children": include_children_from_field(fd),
                            },
                        },
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
            skip_dept_filter = key == "design_assignees"
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
                range_depts = dept_ids_from_field(fd)
                if not codes and not range_depts:
                    continue
                allowed = set()
                if codes:
                    role_ids = (
                        await self.db.execute(
                            select(Role.id).where(Role.tenant_id == self.tenant_id, Role.code.in_(codes))
                        )
                    ).scalars().all()
                    if not role_ids and any(c in ("room_leader", "transfer_packaging") for c in codes):
                        from app.common.rbac_sync import ensure_business_roles, ensure_transfer_packaging_role_members
                        if "room_leader" in codes:
                            created = await ensure_business_roles(self.db, self.tenant_id, ["room_leader"])
                            if created:
                                await self.db.flush()
                        if "transfer_packaging" in codes:
                            await ensure_transfer_packaging_role_members(self.db, self.tenant_id)
                            await self.db.flush()
                        role_ids = (
                            await self.db.execute(
                                select(Role.id).where(Role.tenant_id == self.tenant_id, Role.code.in_(codes))
                            )
                        ).scalars().all()
                    if codes and not role_ids and not range_depts:
                        raise BusinessException(
                            code=VALIDATION_ERROR,
                            message=f"「{label}」可选角色未配置，请到「系统管理 → 角色」维护",
                        )
                    if role_ids:
                        allowed |= set(
                            (
                                await self.db.execute(
                                    select(UserRole.user_id).where(
                                        UserRole.tenant_id == self.tenant_id,
                                        UserRole.role_id.in_(role_ids),
                                    )
                                )
                            ).scalars().all()
                        )
                if range_depts:
                    allowed |= await pss._user_ids_in_depts(
                        self.db, self.tenant_id, range_depts, include_children_from_field(fd),
                    )
                if extra_depts:
                    allowed &= await pss._user_ids_in_depts(self.db, self.tenant_id, extra_depts, True)

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

    @staticmethod
    def _normalize_transfer_targets(transfer_to: str | list[str] | None) -> list[str]:
        """转交接收人：兼容单人 string / 多人 list，去重保序。"""
        if transfer_to is None or transfer_to == "":
            return []
        if isinstance(transfer_to, str):
            s = transfer_to.strip()
            return [s] if s else []
        out: list[str] = []
        seen: set[str] = set()
        for item in transfer_to:
            s = str(item).strip() if item is not None else ""
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    async def _transfer_task(
        self,
        inst: WfProcessInstance,
        task: WfTaskInstance,
        actor: dict,
        targets: list[str],
        opinion: str | None,
    ) -> None:
        """转交：支持多人。当前待办改派给首位，其余在同节点新建 pending 待办。"""
        from app.domains.auth.models import User

        # 去掉当前处理人自己（无意义）
        targets = [uid for uid in targets if uid != task.assignee_id]
        if not targets:
            raise BusinessException(code=VALIDATION_ERROR, message="不能转交给自己，请选择其他接收人")

        active = (await self.db.execute(
            select(User.id).where(
                User.tenant_id == self.tenant_id,
                User.id.in_(targets),
                User.is_active.is_(True),
            )
        )).scalars().all()
        active_set = set(active)
        missing = [uid for uid in targets if uid not in active_set]
        if missing:
            raise BusinessException(code=VALIDATION_ERROR, message="转交接收人无效或已停用")
        targets = [uid for uid in targets if uid in active_set]

        siblings = (await self.db.execute(
            select(WfTaskInstance).where(WfTaskInstance.node_instance_id == task.node_instance_id)
        )).scalars().all()
        transfer_intent = list(targets)
        busy = {
            s.assignee_id
            for s in siblings
            if s.id != task.id and s.status in ("pending", "waiting")
        }
        targets = [uid for uid in targets if uid not in busy]
        if not targets:
            raise BusinessException(
                code=VALIDATION_ERROR,
                message="所选人员在本节点已有待办，请另选接收人",
            )

        # 钉钉待办挂在「原」审批人名下，必须先按原审批人完结，再给接收人重新下发
        self._queue("todo_done_explicit", task.assignee_id, getattr(task, "dingtalk_todo_id", None))

        first, *rest = targets
        task.assignee_id = first
        task.dingtalk_todo_id = None
        task.version += 1
        fresh_ids = [task.id]

        max_order = max((s.task_order or 0) for s in siblings) if siblings else 0
        for i, uid in enumerate(rest):
            tid = generate_uuid()
            self.db.add(WfTaskInstance(
                id=tid,
                tenant_id=self.tenant_id,
                process_instance_id=inst.id,
                node_instance_id=task.node_instance_id,
                assignee_id=uid,
                status="pending",
                task_order=max_order + 1 + i,
            ))
            fresh_ids.append(tid)

        note = opinion
        if len(targets) > 1:
            suffix = f"转交给 {len(targets)} 人"
            note = f"{opinion}（{suffix}）" if opinion else suffix
        self._log(
            inst.id, task.node_instance_id, task.id, actor, "transfer", note,
        )
        self._queue("tasks_created", fresh_ids, inst)
        await self.db.flush()
        await self._cancel_or_sign_siblings_except(
            task.node_instance_id, set(transfer_intent), keep_task_ids=set(fresh_ids),
        )

    async def _cancel_or_sign_siblings_except(
        self,
        node_instance_id: str,
        keep_assignee_ids: set[str],
        *,
        keep_task_ids: set[str] | None = None,
    ) -> None:
        """转交后取消同节点非接收人的待办，避免或签角色节点「全员仍待办」。

        简道云转交后仅接收人继续处理；原角色或签产生的其他 pending 应撤销。
        """
        if not keep_assignee_ids:
            return
        siblings = (await self.db.execute(
            select(WfTaskInstance).where(WfTaskInstance.node_instance_id == node_instance_id)
        )).scalars().all()
        cancelled: list[str] = []
        seen_assignee: set[str] = set()
        keep_ids = keep_task_ids or set()
        for s in sorted(
            siblings,
            key=lambda x: (
                0 if x.id in keep_ids else 1,
                0 if x.assignee_id in keep_assignee_ids else 1,
                x.created_at or _now(),
            ),
        ):
            if s.status not in ("pending", "waiting"):
                continue
            if s.assignee_id not in keep_assignee_ids:
                s.status = "cancelled"
                cancelled.append(s.id)
                continue
            if s.assignee_id in seen_assignee:
                s.status = "cancelled"
                cancelled.append(s.id)
                continue
            seen_assignee.add(s.assignee_id)
        if cancelled:
            self._queue("todos_done", cancelled)
        await self.db.flush()

    async def _on_task_approved(self, inst, version, task, ctx) -> None:
        ni = await self.db.get(WfNodeInstance, task.node_instance_id)
        mode = (ni.config or {}).get("mode", "or_sign")
        # and_sign：历史/简道云对齐别名，语义同 countersign（全员通过）
        if mode == "and_sign":
            mode = "countersign"
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
            if inst.biz_type == "lead_reactivation" and inst.biz_id:
                await self._after_lead_reactivation_node_done(inst, ni, task)
            await self._mark_lead_approved_after_intel(inst, ni)
            await self._advance(inst, version, ni.node_def_id, ctx)
            if inst.biz_type == "lead_reactivation" and inst.biz_id:
                from app.domains.lead.reactivation import sync_reactivation_status_from_wf
                await sync_reactivation_status_from_wf(self.db, self.tenant_id, inst.biz_id)

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
        self._mark_reenter_session(inst)
        # 重新激活目标节点（会重新解析审批人并建待办；允许越过「已完成」去重）
        await self._activate_node(inst, version, target, ctx, allow_reenter=True)

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

    async def _return_to_initiator_flow(
        self, inst, reason: str | None = None, *, current_node_id: str | None = None,
    ) -> None:
        """退回发起人：流程置 returned（非 rejected），当前审批节点完成，其它在途节点取消。"""
        tasks = (await self.db.execute(
            select(WfTaskInstance).where(
                WfTaskInstance.process_instance_id == inst.id,
                WfTaskInstance.status.in_(["pending", "waiting"]),
            )
        )).scalars().all()
        for t in tasks:
            t.status = "cancelled"
        self._queue("todos_done", [t.id for t in tasks])
        now = _now()
        nis = (await self.db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.status == "running",
        ))).scalars().all()
        for ni in nis:
            if current_node_id and ni.id == current_node_id:
                ni.status = "completed"
            else:
                ni.status = "cancelled"
            ni.completed_at = now
        inst.status = "returned"
        inst.completed_at = now
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                fi.status = "returned"
        if inst.biz_type and inst.biz_id:
            from app.domains.lowcode.wf_biz_writeback import writeback
            await writeback(
                self.db, self.tenant_id, inst.biz_type, inst.biz_id, "returned", reason=reason,
            )
        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(
            self.db, self.tenant_id, "workflow.returned", inst, {"reason": reason} if reason else None,
        )
        from app.domains.lowcode import shipment_notice_events as sne
        await sne.emit_from_process(
            self.db, self.tenant_id, sne.EVENT_CANCELLED, inst,
            {"reason": reason} if reason else None,
        )
        self._queue("finished", "returned", reason, inst)

    # ---------- 收尾 / 回写 ----------

    async def _flush_deferred_complete(self, inst) -> None:
        """批次全部激活完再收尾：同批还有审批待办则丢弃旁路抄送触发的 completed。"""
        if self._advance_batch_depth > 0:
            return
        pending = self._deferred_complete
        self._deferred_complete = None
        if not pending or inst.status != "running":
            return
        _pinst, status, reason = pending
        if status != "completed":
            return
        if self.db is not None and await self._has_live_work(inst):
            return
        await self._commit_complete_instance(inst, status, reason)

    async def _complete_instance(self, inst, status: str, reason: str | None = None) -> None:
        if status == "completed" and self._advance_batch_depth > 0:
            self._deferred_complete = (inst, status, reason)
            return
        await self._commit_complete_instance(inst, status, reason)

    async def _commit_complete_instance(self, inst, status: str, reason: str | None = None) -> None:
        self._clear_reenter_session(inst)
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
            if status == "completed":
                await self._cancel_biz_stale_revise(
                    inst.biz_type, inst.biz_id, keep_process_id=inst.id,
                )
        # outbox 领域事件必须在 commit 之前入队
        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(
            self.db, self.tenant_id,
            "workflow.approved" if status == "completed" else "workflow.rejected",
            inst, {"reason": reason} if reason else None,
        )
        # 发货通知 → TMS：流程终态
        from app.domains.lowcode import shipment_notice_events as sne
        if status == "completed":
            await sne.emit_from_process(self.db, self.tenant_id, sne.EVENT_COMPLETED, inst)
        else:
            await sne.emit_from_process(
                self.db, self.tenant_id, sne.EVENT_CANCELLED, inst,
                {"reason": reason} if reason else None,
            )
        self._queue("finished", status, reason, inst)

    async def _form_data(self, inst) -> dict:
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                data = dict(fi.form_data or {})
                # 生产卡：审批上下文实时引用合同（区域经理分支等依赖带出字段）
                try:
                    from app.domains.lowcode.models import FormTemplate
                    from app.domains.lowcode.prod_card_contract_fill import (
                        overlay_prod_card_contract_live,
                    )
                    tpl = await self.db.get(FormTemplate, fi.template_id)
                    if tpl and tpl.code == "prod_card_supplement":
                        data = await overlay_prod_card_contract_live(
                            self.db, self.tenant_id, data,
                        )
                except Exception:
                    pass
                # 人员多选路由：表单存 user_id，条件常写 username —— 补别名便于 in 命中
                try:
                    data = await self._alias_user_ids_in_form_data(data)
                except Exception:
                    pass
                return data
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

    async def _alias_user_ids_in_form_data(self, form_data: dict) -> dict:
        """把人员字段里的 user_id 列表附带 username，供路由条件 in 匹配。"""
        from app.domains.auth.models import User

        ids: list[str] = []
        for v in form_data.values():
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, str) and x:
                        ids.append(x)
                    elif isinstance(x, dict) and x.get("id"):
                        ids.append(str(x["id"]))
            elif isinstance(v, dict) and v.get("id"):
                ids.append(str(v["id"]))
        if not ids:
            return form_data
        rows = (
            await self.db.execute(
                select(User.id, User.username).where(
                    User.tenant_id == self.tenant_id,
                    User.id.in_(list(dict.fromkeys(ids))),
                )
            )
        ).all()
        uname_by_id = {str(uid): uname for uid, uname in rows if uname}
        if not uname_by_id:
            return form_data
        out = dict(form_data)
        for key, v in list(out.items()):
            if not isinstance(v, list) or not v:
                continue
            extra: list[str] = []
            for x in v:
                uid = str(x.get("id") if isinstance(x, dict) else x or "")
                uname = uname_by_id.get(uid)
                if uname and uname not in v and uname not in extra:
                    extra.append(uname)
            if extra:
                out[key] = [*v, *extra]
        return out

    def _log(self, pid, nid, tid, actor, action, opinion) -> None:
        self.db.add(WfTaskActionLog(
            id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=pid,
            node_instance_id=nid, task_instance_id=tid,
            actor_id=actor.get("sub"), actor_name=actor.get("real_name"),
            action=action, opinion=opinion,
        ))

    # ---------- 激活（对齐简道云：已结束实例选节点重开） ----------

    _ACTIVATABLE_STATUSES = frozenset({"completed", "rejected", "withdrawn"})

    async def activate(
        self, process_instance_id: str, actor: dict, to_node_id: str,
    ) -> WfProcessInstance:
        """已结束流程选节点重新激活（同实例，非新建）。

        - start：置 withdrawn + 发起人修订待办（改数后走既有重提）
        - approval：置 running + `_return_to_node` 重建待办
        """
        to_node_id = (to_node_id or "").strip()
        if not to_node_id:
            raise BusinessException(code=VALIDATION_ERROR, message="请选择激活节点")

        inst = (await self.db.execute(
            select(WfProcessInstance).where(
                WfProcessInstance.id == process_instance_id,
                WfProcessInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if not inst:
            raise BusinessException(code=NOT_FOUND, message="流程不存在")

        from app.domains.lowcode.workflow_activate_policy import (
            PROD_CARD_SUPPLEMENT_PROCESS_CODE,
            activatable_statuses,
        )
        from app.domains.lowcode.workflow_models import WfProcessDefinition

        dfn = await self.db.get(WfProcessDefinition, inst.process_definition_id)
        proc_code = dfn.code if dfn else None
        allowed = activatable_statuses(proc_code)
        if inst.status not in allowed:
            if inst.status == "running" and proc_code != PROD_CARD_SUPPLEMENT_PROCESS_CODE:
                raise BusinessException(
                    code=BUSINESS_ERROR, message="流程进行中，请使用退回；仅已结束流程可激活",
                )
            raise BusinessException(code=BUSINESS_ERROR, message="当前状态不可激活流程")

        version = (await self.db.execute(select(WfProcessDefinitionVersion).where(
            WfProcessDefinitionVersion.tenant_id == self.tenant_id,
            WfProcessDefinitionVersion.process_definition_id == inst.process_definition_id,
            WfProcessDefinitionVersion.status == "published",
        ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()
        if not version:
            version = await self.db.get(WfProcessDefinitionVersion, inst.process_version_id)
        if not version:
            raise BusinessException(code=BUSINESS_ERROR, message="流程定义缺失，无法激活")

        # 激活时尽量吃最新发布版
        if version.id != inst.process_version_id:
            inst.process_version_id = version.id

        target = self._nodes_by_id(version).get(to_node_id)
        if not target:
            raise BusinessException(code=VALIDATION_ERROR, message="激活节点不存在")
        ntype = target.get("type")
        if ntype not in ("start", "approval"):
            raise BusinessException(code=VALIDATION_ERROR, message="仅可激活开始节点或审批节点")

        node_label = (target.get("name") or ntype or to_node_id).strip()
        await self._cancel_initiator_revise_todos(inst.id)

        # 作废残留待办 / running 节点
        tasks = (await self.db.execute(select(WfTaskInstance).where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status.in_(["pending", "waiting"]),
        ))).scalars().all()
        for t in tasks:
            t.status = "cancelled"
        if tasks:
            self._queue("todos_done", [t.id for t in tasks])
        nis = (await self.db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.status == "running",
        ))).scalars().all()
        for ni in nis:
            ni.status = "cancelled"

        self._log(
            inst.id, None, None, actor, "activate",
            f"激活至「{node_label}」",
        )

        ctx = ApprovalContext(
            initiator_id=inst.initiator_id,
            form_data=await self._form_data(inst),
            nominated=inst.nominated_approvers or {},
        )

        if ntype == "start":
            # 对齐「递呈信息」：发起人改数后重提（复用 withdrawn + 修订待办）
            inst.status = "withdrawn"
            inst.completed_at = _now()
            if inst.form_instance_id:
                fi = await self.db.get(FormInstance, inst.form_instance_id)
                if fi:
                    fi.status = "draft"
            if inst.biz_type and inst.biz_id:
                from app.domains.lowcode.wf_biz_writeback import writeback
                await writeback(self.db, self.tenant_id, inst.biz_type, inst.biz_id, "withdrawn")
            await self.db.flush()
            await self._create_initiator_revise_todo(
                inst, reason=f"流程已激活至「{node_label}」，请修改后重新提交",
            )
        else:
            inst.status = "running"
            inst.completed_at = None
            if not inst.started_at:
                inst.started_at = _now()
            if inst.form_instance_id:
                fi = await self.db.get(FormInstance, inst.form_instance_id)
                if fi:
                    fi.status = "running"
                    fi.process_instance_id = inst.id
            if inst.biz_type and inst.biz_id:
                from app.domains.lowcode.wf_biz_writeback import writeback
                await writeback(self.db, self.tenant_id, inst.biz_type, inst.biz_id, "submitted")
            self._mark_reenter_session(inst)
            await self.db.flush()
            await self._activate_node(inst, version, target, ctx, allow_reenter=True)
            if inst.form_instance_id:
                from app.domains.lowcode import shipment_notice_events as sne
                fi = await self.db.get(FormInstance, inst.form_instance_id)
                if fi:
                    await sne.emit_submitted(
                        self.db, self.tenant_id, fi,
                        extra={"reactivated": True, "node_id": to_node_id},
                    )

        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(self.db, self.tenant_id, "workflow.activated", inst)
        await self.db.commit()
        await self.db.refresh(inst)
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "activate")
        return inst

    async def abort_deleted_form(
        self, process_instance_id: str, actor: dict | None = None,
        *, reason: str = "关联表单已删除，流程作废",
    ) -> bool:
        """作废进行中流程与待办，不回写草稿、不建修订待办。"""
        inst = (await self.db.execute(
            select(WfProcessInstance).where(
                WfProcessInstance.id == process_instance_id,
                WfProcessInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if not inst:
            return False
        actor = actor or {"sub": "system", "real_name": "系统"}
        tasks = (await self.db.execute(
            select(WfTaskInstance).where(
                WfTaskInstance.process_instance_id == inst.id,
                WfTaskInstance.status.in_(["pending", "waiting"]),
            )
        )).scalars().all()
        now = _now()
        for t in tasks:
            t.status = "cancelled"
            t.action_at = now
        nis = (await self.db.execute(
            select(WfNodeInstance).where(
                WfNodeInstance.process_instance_id == inst.id,
                WfNodeInstance.status == "running",
            )
        )).scalars().all()
        for ni in nis:
            ni.status = "cancelled"
            ni.completed_at = now
        if inst.status in ("running", "draft") or tasks or nis:
            inst.status = "cancelled"
            inst.completed_at = now
            self._log(inst.id, None, None, actor, "abort", reason)
        if tasks:
            self._queue("todos_done", [t.id for t in tasks])
        await self.db.commit()
        if tasks:
            await self.flush_notifications(inst)
        return True

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
        from app.domains.lowcode import shipment_notice_events as sne
        await sne.emit_from_process(self.db, self.tenant_id, sne.EVENT_CANCELLED, inst)
        await self.db.commit()
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "withdraw")

    async def end_process(self, process_instance_id: str, actor: dict, *, reason: str | None = None) -> None:
        """手动结束流程（对齐简道云记录内「结束流程」）。

        - running：终止进行中流程，关闭全部待办，表单/业务回写为已驳回。
        - rejected/withdrawn/returned：清掉「修改并重新提交」修订待办，不改业务态。
        """
        inst = (await self.db.execute(
            select(WfProcessInstance).where(
                WfProcessInstance.id == process_instance_id,
                WfProcessInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if not inst:
            raise BusinessException(code=NOT_FOUND, message="流程不存在")
        if inst.status == "running":
            await self._terminate_running_process(inst, actor, reason=reason)
            return
        if inst.status not in ("rejected", "withdrawn", "returned"):
            raise BusinessException(code=BUSINESS_ERROR, message="当前流程状态不可结束")

        uid = actor.get("sub")
        revise_assignees = (await self.db.execute(
            select(WfTaskInstance.assignee_id).join(
                WfNodeInstance, WfTaskInstance.node_instance_id == WfNodeInstance.id,
            ).where(
                WfTaskInstance.process_instance_id == inst.id,
                WfTaskInstance.status == "pending",
                (
                    (WfNodeInstance.node_type == "revise")
                    | (WfNodeInstance.node_def_id == REVISE_NODE_DEF_ID)
                ),
            )
        )).scalars().all()
        allowed = {inst.initiator_id, *(a for a in revise_assignees if a)}
        if uid not in allowed:
            raise BusinessException(code=FORBIDDEN, message="仅发起人或修订待办人可手动结束")

        await self._cancel_initiator_revise_todos(inst.id)
        self._log(
            inst.id, None, None, actor, "end_process",
            reason or "发起人手动结束流程",
        )
        await self.db.commit()
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "end_process")

    async def _terminate_running_process(
        self, inst, actor: dict, *, reason: str | None = None,
    ) -> None:
        """进行中流程手动终止：关闭待办，流程标 terminated，表单/业务标 rejected。"""
        uid = actor.get("sub")
        perms = set(actor.get("permissions") or [])
        is_admin = (
            "workflow:manage" in perms
            or "workflow:activate" in perms
            or "form_data:delete" in perms
        )
        if inst.initiator_id != uid and not is_admin:
            raise BusinessException(
                code=FORBIDDEN, message="仅发起人或流程/数据管理员可结束进行中的流程",
            )

        now = _now()
        nis = (await self.db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.status == "running",
        ))).scalars().all()
        for ni in nis:
            ni.status = "cancelled"
            ni.completed_at = now

        tasks = (await self.db.execute(select(WfTaskInstance).where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status.in_(["pending", "waiting"]),
        ))).scalars().all()
        pending_assignees = [t.assignee_id for t in tasks if t.status == "pending" and t.assignee_id]
        for t in tasks:
            t.status = "cancelled"
        if tasks:
            self._queue("todos_done", [t.id for t in tasks])

        inst.status = "terminated"
        inst.completed_at = now
        inst.pending_joins = None
        await self.db.flush()

        term_reason = reason or "手动结束流程"
        if inst.form_instance_id:
            from app.domains.lowcode.models import FormInstance
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                fi.status = "rejected"
        if inst.biz_type and inst.biz_id:
            from app.domains.lowcode.wf_biz_writeback import writeback
            await writeback(
                self.db, self.tenant_id, inst.biz_type, inst.biz_id, "terminated", reason=term_reason,
            )

        self._log(inst.id, None, None, actor, "terminate", term_reason)
        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(
            self.db, self.tenant_id, "workflow.rejected", inst, {"reason": term_reason},
        )
        from app.domains.lowcode import shipment_notice_events as sne
        await sne.emit_from_process(
            self.db, self.tenant_id, sne.EVENT_CANCELLED, inst, {"reason": term_reason},
        )
        if pending_assignees:
            self._queue("withdrawn", pending_assignees, actor, inst)
        self._queue("finished", "terminated", term_reason, inst)

        await self.db.commit()
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "terminate")

    async def end_process_by_task(self, task_id: str, actor: dict, *, reason: str | None = None) -> None:
        """从修订待办入口结束流程（线索修订页等仅持有 task_id 的场景）。"""
        task = (await self.db.execute(
            select(WfTaskInstance).where(
                WfTaskInstance.id == task_id,
                WfTaskInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if not task:
            raise BusinessException(code=NOT_FOUND, message="待办不存在")
        inst = (await self.db.execute(
            select(WfProcessInstance).where(
                WfProcessInstance.id == task.process_instance_id,
                WfProcessInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if inst and inst.status == "running":
            raise BusinessException(
                code=BUSINESS_ERROR, message="审批待办不可结束进行中的流程，请从记录详情操作",
            )
        await self.end_process(task.process_instance_id, actor, reason=reason)

    async def resubmit(self, process_instance_id: str, actor: dict) -> WfProcessInstance:
        """已撤回/已驳回流程由发起人重新提交：复用同一流程实例，从起始节点重新推进。"""
        inst = (await self.db.execute(
            select(WfProcessInstance).where(
                WfProcessInstance.id == process_instance_id,
                WfProcessInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if not inst:
            raise BusinessException(code=NOT_FOUND, message="流程不存在")
        if inst.initiator_id != actor.get("sub"):
            raise BusinessException(code=FORBIDDEN, message="仅发起人可重新提交")
        if inst.status not in ("withdrawn", "rejected", "returned"):
            raise BusinessException(code=BUSINESS_ERROR, message="仅已撤回、已退回或已驳回的流程可重新提交")

        # 清掉发起人修订待办（若从「我发起的」直接重提，也可能仍挂着）
        await self._cancel_initiator_revise_todos(inst.id)
        if inst.biz_type and inst.biz_id:
            await self._cancel_biz_stale_revise(
                inst.biz_type, inst.biz_id, keep_process_id=inst.id,
            )

        # 防重：同一表单/业务已有其它进行中流程则直接返回
        if inst.form_instance_id:
            existing = (await self.db.execute(select(WfProcessInstance).where(
                WfProcessInstance.tenant_id == self.tenant_id,
                WfProcessInstance.form_instance_id == inst.form_instance_id,
                WfProcessInstance.status == "running",
                WfProcessInstance.id != inst.id,
            ).limit(1))).scalar_one_or_none()
            if existing:
                return existing
        if inst.biz_type and inst.biz_id:
            existing = (await self.db.execute(select(WfProcessInstance).where(
                WfProcessInstance.tenant_id == self.tenant_id,
                WfProcessInstance.biz_type == inst.biz_type,
                WfProcessInstance.biz_id == inst.biz_id,
                WfProcessInstance.status == "running",
                WfProcessInstance.id != inst.id,
            ).limit(1))).scalar_one_or_none()
            if existing:
                return existing

        # 优先用当前已发布版本，保证重新提交吃到最新流程设计
        version = (await self.db.execute(select(WfProcessDefinitionVersion).where(
            WfProcessDefinitionVersion.tenant_id == self.tenant_id,
            WfProcessDefinitionVersion.process_definition_id == inst.process_definition_id,
            WfProcessDefinitionVersion.status == "published",
        ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()
        if not version:
            version = await self.db.get(WfProcessDefinitionVersion, inst.process_version_id)
        if not version:
            raise BusinessException(code=BUSINESS_ERROR, message="流程未发布，无法重新提交")

        form_data = await self._form_data(inst)
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                inst.title = (fi.title or "").strip() or inst.title
                form_data = dict(fi.form_data or {}) or form_data
                fi.status = "running"
                fi.process_instance_id = inst.id
        if inst.biz_type and inst.biz_id:
            from app.domains.lowcode.wf_biz_writeback import writeback
            await writeback(self.db, self.tenant_id, inst.biz_type, inst.biz_id, "submitted")

        # 作废残留待办 / running 节点，清并行汇聚状态（对齐 activate / return_to_node）
        tasks = (await self.db.execute(select(WfTaskInstance).where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status.in_(["pending", "waiting"]),
        ))).scalars().all()
        for t in tasks:
            t.status = "cancelled"
        if tasks:
            self._queue("todos_done", [t.id for t in tasks])
        nis = (await self.db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.status == "running",
        ))).scalars().all()
        for ni in nis:
            ni.status = "cancelled"
            ni.completed_at = _now()
        inst.pending_joins = None
        try:
            flag_modified(inst, "pending_joins")
        except Exception:
            pass
        self._mark_reenter_session(inst)

        if version.id != inst.process_version_id:
            inst.process_version_id = version.id
        inst.status = "running"
        inst.completed_at = None
        if not inst.started_at:
            inst.started_at = _now()

        self._log(inst.id, None, None, actor, "resubmit", "重新提交")
        await self.db.flush()

        ctx = ApprovalContext(
            initiator_id=inst.initiator_id,
            form_data=form_data,
            nominated=dict(inst.nominated_approvers or {}) or {},
        )
        from app.domains.lowcode import wf_notify
        await wf_notify.enqueue_wf_event(self.db, self.tenant_id, "workflow.submitted", inst)

        start = self._start_node(version)
        if not start:
            raise BusinessException(code=VALIDATION_ERROR, message="流程缺少开始节点")
        prev_resubmit_reenter = self._resubmit_reenter
        self._resubmit_reenter = True
        try:
            await self._advance(inst, version, start["id"], ctx, force_reenter=True)
        finally:
            self._resubmit_reenter = prev_resubmit_reenter

        # 发货通知等表单流：重新提交后通知 TMS 继续同步（同一 form_instance）
        if inst.form_instance_id:
            from app.domains.lowcode import shipment_notice_events as sne
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                await sne.emit_submitted(self.db, self.tenant_id, fi, extra={"resubmit": True})

        await self.db.commit()
        await self.db.refresh(inst)
        await self.flush_notifications(inst)
        await self._audit(inst, actor, "resubmit")
        return inst

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
