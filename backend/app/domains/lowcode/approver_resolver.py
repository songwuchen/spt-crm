"""审批人计算引擎(approver resolver)。

移植/适配自 spt-lowcode services/workflow/approver_resolver.py。CRM 组织差异:
- 部门负责人为 Department.leader_id(单一),无独立 dept_manager 表;
- UserDepartment 无 is_primary,取用户全部部门;
- Role 无分管部门(division),specified_role = 拥有该角色的全部成员;
- 岗位用本项目新增 Post/UserPost;代理委托用 UserAgent(在流程引擎发待办时应用)。

输入: 节点审批人规则 rule({type, value, ...}) + 上下文(发起人/表单数据/自选人)。
输出: 审批人 user_id(str) 列表(去重保序,已过滤停用用户)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import Role, User, UserRole
from app.domains.organization.models import Department, UserDepartment, UserPost


@dataclass
class ApprovalContext:
    initiator_id: str
    form_data: dict[str, Any] = field(default_factory=dict)
    # 发起人自选审批人: {node_def_id: [user_id, ...]}
    nominated: dict[str, Any] = field(default_factory=dict)


class NoApproverError(Exception):
    pass


class ApproverResolver:
    def __init__(self, db: AsyncSession, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self._dept_cache: dict[str, Department] | None = None
        self._children: dict[str, list[str]] | None = None
        self._active_ids: set[str] | None = None

    # ---------- 组织快照(按需加载,单次 resolve 复用) ----------

    async def _load_depts(self) -> None:
        if self._dept_cache is not None:
            return
        rows = (await self.db.execute(
            select(Department).where(Department.tenant_id == self.tenant_id)
        )).scalars().all()
        self._dept_cache = {d.id: d for d in rows}
        children: dict[str, list[str]] = {}
        for d in rows:
            if d.parent_id:
                children.setdefault(d.parent_id, []).append(d.id)
        self._children = children

    async def _active_user_ids(self) -> set[str]:
        if self._active_ids is None:
            rows = (await self.db.execute(
                select(User.id).where(User.tenant_id == self.tenant_id, User.is_active == True)  # noqa: E712
            )).scalars().all()
            self._active_ids = set(rows)
        return self._active_ids

    async def _user_dept_ids(self, user_id: str) -> list[str]:
        rows = (await self.db.execute(
            select(UserDepartment.department_id).where(
                UserDepartment.tenant_id == self.tenant_id,
                UserDepartment.user_id == user_id,
            )
        )).scalars().all()
        return list(rows)

    def _dept_leader(self, dept_id: str) -> str | None:
        d = (self._dept_cache or {}).get(dept_id)
        return d.leader_id if d else None

    def _descendants(self, root: str) -> set[str]:
        out: set[str] = set()
        stack = [root]
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.add(cur)
            stack.extend((self._children or {}).get(cur, []))
        return out

    async def _resolve_user_identifier(self, ident: str) -> str | None:
        """值可能是 user_id,或用户名。优先当作 id;否则按 username 查。"""
        ident = str(ident).strip()
        if not ident:
            return None
        active = await self._active_user_ids()
        if ident in active:
            return ident
        # 可能是停用用户 id(仍是有效 id,但会在末尾被过滤);或用户名
        uid = (await self.db.execute(
            select(User.id).where(User.tenant_id == self.tenant_id, User.username == ident)
        )).scalar_one_or_none()
        if uid:
            return uid
        # 作为 id 透传(末尾统一按 active 过滤)
        return ident

    # ---------- 主入口 ----------

    async def resolve(self, rule: dict[str, Any], ctx: ApprovalContext) -> list[str]:
        await self._load_depts()
        t = rule.get("type", "")
        fn = getattr(self, f"_r_{t}", None)
        if fn is None:
            raise NoApproverError(f"不支持的审批人类型: {t}")
        ids = await fn(rule, ctx)
        active = await self._active_user_ids()
        # exclude_initiator: 把发起人从审批人里剔除，避免「自己审自己」。
        # 显式开关而非默认行为——creator 类型就是刻意以发起人为审批人，
        # 全局默认排除会直接废掉该类型，也会改变线上已发布流程的行为。
        exclude_initiator = bool(rule.get("exclude_initiator")) and t != "creator"
        # 去重保序 + 过滤停用
        seen: set[str] = set()
        out: list[str] = []
        for u in ids:
            if exclude_initiator and u == ctx.initiator_id:
                continue
            if u and u in active and u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def _as_list(self, v: Any) -> list[str]:
        if v is None or v == "":
            return []
        return [str(x) for x in v] if isinstance(v, list) else [str(v)]

    # ---------- 各审批人类型策略 ----------

    async def _r_specified_user(self, rule: dict, _ctx: ApprovalContext) -> list[str]:
        out = []
        for v in self._as_list(rule.get("value")):
            uid = await self._resolve_user_identifier(v)
            if uid:
                out.append(uid)
        return out

    async def _r_creator(self, _rule: dict, ctx: ApprovalContext) -> list[str]:
        return [ctx.initiator_id]

    async def _r_initiator_self_select(self, rule: dict, ctx: ApprovalContext) -> list[str]:
        node_id = rule.get("node_id")
        out = []
        for v in self._as_list(ctx.nominated.get(node_id)):
            uid = await self._resolve_user_identifier(v)
            if uid:
                out.append(uid)
        return out

    async def _r_dept_head(self, _rule: dict, ctx: ApprovalContext) -> list[str]:
        out = []
        for dept_id in await self._user_dept_ids(ctx.initiator_id):
            leader = self._dept_leader(dept_id)
            if leader:
                out.append(leader)
        return out

    async def _r_direct_supervisor(self, _rule: dict, ctx: ApprovalContext) -> list[str]:
        """发起人各部门向上找第一个有负责人(≠发起人)的部门,取其负责人。"""
        out: list[str] = []
        for dept_id in await self._user_dept_ids(ctx.initiator_id):
            cur: str | None = dept_id
            visited: set[str] = set()
            while cur and cur not in visited:
                visited.add(cur)
                leader = self._dept_leader(cur)
                if leader and leader != ctx.initiator_id:
                    out.append(leader)
                    break
                d = (self._dept_cache or {}).get(cur)
                cur = d.parent_id if d else None
        return out

    async def _r_multi_level_superior(self, rule: dict, ctx: ApprovalContext) -> list[str]:
        """逐级上级: 从发起人部门沿部门树向上,逐级收集负责人(≠发起人),最多 levels 级。"""
        try:
            max_levels = int(rule.get("levels") or 99)
        except (TypeError, ValueError):
            max_levels = 99
        out: list[str] = []
        seen: set[str] = set()
        for dept_id in await self._user_dept_ids(ctx.initiator_id):
            cur: str | None = dept_id
            visited: set[str] = set()
            levels = 0
            while cur and cur not in visited and levels < max_levels:
                visited.add(cur)
                leader = self._dept_leader(cur)
                if leader and leader != ctx.initiator_id and leader not in seen:
                    seen.add(leader)
                    out.append(leader)
                    levels += 1
                d = (self._dept_cache or {}).get(cur)
                cur = d.parent_id if d else None
        return out

    async def _r_dept_members(self, rule: dict, _ctx: ApprovalContext) -> list[str]:
        dept_ids = self._as_list(rule.get("value"))
        if not dept_ids:
            return []
        if rule.get("include_sub"):
            expanded: set[str] = set()
            for d in dept_ids:
                expanded |= self._descendants(d)
            dept_ids = list(expanded)
        rows = (await self.db.execute(
            select(UserDepartment.user_id).where(
                UserDepartment.tenant_id == self.tenant_id,
                UserDepartment.department_id.in_(dept_ids),
            )
        )).scalars().all()
        return list(rows)

    async def _r_specified_role(self, rule: dict, _ctx: ApprovalContext) -> list[str]:
        role_codes = self._as_list(rule.get("value"))
        if not role_codes:
            return []
        rows = (await self.db.execute(
            select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(
                UserRole.tenant_id == self.tenant_id,
                Role.code.in_(role_codes),
            )
        )).scalars().all()
        return list(rows)

    async def _r_specified_post(self, rule: dict, _ctx: ApprovalContext) -> list[str]:
        post_ids = self._as_list(rule.get("value"))
        if not post_ids:
            return []
        rows = (await self.db.execute(
            select(UserPost.user_id).where(
                UserPost.tenant_id == self.tenant_id,
                UserPost.post_id.in_(post_ids),
            )
        )).scalars().all()
        return list(rows)

    async def _r_form_field_person(self, rule: dict, ctx: ApprovalContext) -> list[str]:
        value = ctx.form_data.get(rule.get("value", ""))
        out = []
        for v in self._as_list(value):
            uid = await self._resolve_user_identifier(v)
            if uid:
                out.append(uid)
        return out

    async def _r_form_field_dept(self, rule: dict, ctx: ApprovalContext) -> list[str]:
        value = ctx.form_data.get(rule.get("value", ""))
        out = []
        for dept_id in self._as_list(value):
            leader = self._dept_leader(dept_id)
            if leader:
                out.append(leader)
        return out

    async def _r_mixed(self, rule: dict, ctx: ApprovalContext) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        node_id = rule.get("node_id")
        for sub in rule.get("value") or []:
            if not isinstance(sub, dict) or not sub.get("type"):
                continue
            sub_rule = {**sub, "node_id": sub.get("node_id", node_id)}
            try:
                for uid in await self.resolve(sub_rule, ctx):
                    if uid not in seen:
                        seen.add(uid)
                        out.append(uid)
            except NoApproverError:
                continue
        return out
