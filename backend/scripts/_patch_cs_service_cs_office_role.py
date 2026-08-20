"""客服落实：指定人员 → 指定角色 cs_office；同步角色成员；升级本地系统流。"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GEN = ROOT / "app" / "domains" / "lowcode" / "_customer_service_jdy_generated.py"
WANT = {
    "type": "specified_role",
    "value": "cs_office",
    "exclude_initiator": True,
    "jdy_role_hint": "230902客服内勤",
}


def patch_generated() -> int:
    text = GEN.read_text(encoding="utf-8")
    m = re.search(
        r"(CUSTOMER_SERVICE_JDY = json\.loads\(r''')(.*)('''\))",
        text,
        re.S,
    )
    if not m:
        raise SystemExit("cannot parse CUSTOMER_SERVICE_JDY")
    prefix, body, suffix = m.group(1), m.group(2), m.group(3)
    data = json.loads(body)
    changed = 0
    for n in data["cs_service_request"]["flow_nodes"]:
        if n.get("type") != "approval":
            continue
        if n.get("id") == "n2" or n.get("name") == "客服落实":
            n["approver_rule"] = dict(WANT)
            changed += 1
            print("patched node", n.get("id"), n.get("name"))
    GEN.write_text(
        f"{prefix}{json.dumps(data, ensure_ascii=False, separators=(',', ':'))}{suffix}\n",
        encoding="utf-8",
    )
    return changed


async def sync_local() -> None:
    from sqlalchemy import select

    # 先加载组织模型，避免 User.UserDepartment 关系未注册
    import app.domains.organization.models  # noqa: F401
    from app.common.rbac_sync import ensure_cs_office_role_members
    from app.database import async_session_factory
    from app.domains.auth.models import Role, User, UserRole
    from app.domains.lowcode import service as lc_svc
    from app.domains.lowcode.workflow_models import (
        WfProcessDefinition,
        WfProcessDefinitionVersion,
    )

    tenant_id = "00000000-0000-0000-0000-000000000001"
    async with async_session_factory() as db:
        info = await ensure_cs_office_role_members(db, tenant_id)
        await db.commit()
        print("role_members", info)

        user = {"sub": None, "roles": ["admin"]}
        tpl = await lc_svc.ensure_builtin_form(db, tenant_id, "cs_service_request", user)
        await db.commit()
        print("ensured form", getattr(tpl, "id", None), getattr(tpl, "code", None))

        role = (
            await db.execute(
                select(Role).where(Role.tenant_id == tenant_id, Role.code == "cs_office")
            )
        ).scalar_one_or_none()
        if role:
            rows = (
                await db.execute(
                    select(User.username, User.real_name)
                    .select_from(UserRole)
                    .join(User, User.id == UserRole.user_id)
                    .where(UserRole.role_id == role.id)
                )
            ).all()
            print("cs_office members:", [(r[0], r[1]) for r in rows])

        d = (
            await db.execute(
                select(WfProcessDefinition).where(
                    WfProcessDefinition.tenant_id == tenant_id,
                    WfProcessDefinition.code == "SYS_CS_SERVICE_REQUEST",
                )
            )
        ).scalar_one_or_none()
        if d:
            ver = (
                await db.execute(
                    select(WfProcessDefinitionVersion).where(
                        WfProcessDefinitionVersion.process_definition_id == d.id,
                        WfProcessDefinitionVersion.status == "published",
                    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1)
                )
            ).scalar_one_or_none()
            print("def", d.id, "ver", getattr(ver, "version_number", None))
            for n in (ver.node_definitions or []) if ver else []:
                if n.get("name") == "客服落实" or n.get("id") == "n2":
                    print("published 客服落实:", n.get("approver_rule"))


if __name__ == "__main__":
    n = patch_generated()
    print("generated patched", n)
    asyncio.run(sync_local())
