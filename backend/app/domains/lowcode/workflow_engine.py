"""流程推进引擎(统一入口)。

移植思想自 spt-lowcode services/workflow/engine.py,MVP 聚焦核心闭环:
- 节点类型: start / approval / cc / end(条件分支挂在连线 route.condition 上,无需独立 condition 节点);
- 多人模式: or_sign(或签,一人过即过) / countersign(会签,全过才过) / sequential(顺序会签);
- 动作: submit / approve / reject / withdraw / transfer / comment;
- 空审批人策略: auto_approve(跳过) / terminate(终止驳回);
- 待办为独立 WfTaskInstance,version 乐观锁防并发重复审批;全程留痕 WfTaskActionLog。

统一入口保证: 状态推进 + 待办生成/作废 + 日志 + (表单实例)回写 集中处理,避免散落。
高级能力(并行网关/加签/退回指定节点/子流程/超时/代理落地)后续迭代。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
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
        await self._advance(inst, version, start["id"], ctx)
        await self.db.commit()
        await self.db.refresh(inst)
        return inst

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
        # 其它类型(condition/parallel 等)MVP 视为直通
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
            if strategy == "terminate":
                await self._complete_instance(inst, "rejected")
                self._log(inst.id, None, None, {"sub": "system"}, "auto_reject", "无审批人,流程终止")
                return
            # auto_approve: 跳过本节点
            self._log(inst.id, None, None, {"sub": "system"}, "auto_approve", "无审批人,自动通过")
            await self._advance(inst, version, node["id"], ctx)
            return

        mode = node.get("multi_mode") or (node.get("config") or {}).get("multi_mode") or "or_sign"
        ni = WfNodeInstance(
            id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
            node_def_id=node["id"], node_type="approval", node_name=node.get("name") or "审批",
            status="running", config={"mode": mode}, started_at=_now(),
        )
        self.db.add(ni)
        await self.db.flush()

        for idx, uid in enumerate(approvers):
            # 顺序会签: 仅首个待办 pending,其余 waiting;或签/会签: 全部 pending
            status = "pending"
            if mode == "sequential" and idx > 0:
                status = "waiting"
            self.db.add(WfTaskInstance(
                id=generate_uuid(), tenant_id=self.tenant_id, process_instance_id=inst.id,
                node_instance_id=ni.id, assignee_id=uid, status=status, task_order=idx,
            ))
        await self.db.flush()

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

    # ---------- 审批动作 ----------

    async def act(self, task_id: str, actor: dict, action: str, opinion: str | None = None,
                  transfer_to: str | None = None) -> None:
        task = (await self.db.execute(
            select(WfTaskInstance).where(
                WfTaskInstance.id == task_id, WfTaskInstance.tenant_id == self.tenant_id,
            )
        )).scalar_one_or_none()
        if not task:
            raise BusinessException(code=NOT_FOUND, message="待办不存在")
        if task.assignee_id != actor.get("sub"):
            raise BusinessException(code=FORBIDDEN, message="非当前待办的处理人")
        if task.status != "pending":
            raise BusinessException(code=BUSINESS_ERROR, message="该待办已处理")

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
            task.assignee_id = transfer_to
            task.version += 1
            self._log(inst.id, task.node_instance_id, task.id, actor, "transfer", opinion)
            await self.db.commit()
            return

        task.status = "approved" if action == "approve" else "rejected"
        task.opinion = opinion
        task.action_at = _now()
        task.version += 1
        self._log(inst.id, task.node_instance_id, task.id, actor, action, opinion)

        if action == "reject":
            await self._reject_flow(inst)
            await self.db.commit()
            return

        # approve → 判断节点是否完成
        await self._on_task_approved(inst, version, task, ctx)
        await self.db.commit()

    async def _on_task_approved(self, inst, version, task, ctx) -> None:
        ni = await self.db.get(WfNodeInstance, task.node_instance_id)
        mode = (ni.config or {}).get("mode", "or_sign")
        siblings = (await self.db.execute(
            select(WfTaskInstance).where(WfTaskInstance.node_instance_id == ni.id)
        )).scalars().all()

        node_done = False
        if mode == "or_sign":
            for s in siblings:
                if s.id != task.id and s.status in ("pending", "waiting"):
                    s.status = "cancelled"
            node_done = True
        elif mode == "countersign":
            node_done = all(s.status == "approved" for s in siblings)
        elif mode == "sequential":
            nxt = [s for s in siblings if s.status == "waiting"]
            if nxt:
                nxt.sort(key=lambda s: s.task_order)
                nxt[0].status = "pending"
                node_done = False
            else:
                node_done = all(s.status in ("approved", "cancelled") for s in siblings)

        if node_done:
            ni.status = "completed"
            ni.completed_at = _now()
            await self.db.flush()
            await self._advance(inst, version, ni.node_def_id, ctx)

    async def _reject_flow(self, inst) -> None:
        # 作废所有未处理待办,流程置驳回
        tasks = (await self.db.execute(
            select(WfTaskInstance).where(
                WfTaskInstance.process_instance_id == inst.id,
                WfTaskInstance.status.in_(["pending", "waiting"]),
            )
        )).scalars().all()
        for t in tasks:
            t.status = "cancelled"
        await self._complete_instance(inst, "rejected")

    # ---------- 收尾 / 回写 ----------

    async def _complete_instance(self, inst, status: str) -> None:
        inst.status = status
        inst.completed_at = _now()
        await self.db.flush()
        # 回写关联表单实例状态
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                fi.status = status  # completed / rejected
        # 回写既有业务单据(灰度替换旧审批引擎): 按 biz_type 更新业务表状态列
        if inst.biz_type and inst.biz_id:
            from app.domains.lowcode.wf_biz_writeback import writeback
            await writeback(self.db, self.tenant_id, inst.biz_type, inst.biz_id, status)

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
        for t in tasks:
            t.status = "cancelled"
        inst.status = "withdrawn"
        inst.completed_at = _now()
        self._log(inst.id, None, None, actor, "withdraw", None)
        if inst.form_instance_id:
            fi = await self.db.get(FormInstance, inst.form_instance_id)
            if fi:
                fi.status = "withdrawn"
        await self.db.commit()
