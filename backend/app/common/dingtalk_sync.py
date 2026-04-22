"""
DingTalk OA Integration — Department and User Sync.

Uses DingTalk enterprise internal app (企业内部应用) API to sync
departments and users into the local CRM database.

Config is stored in IntegrationEndpoint with system_code='dingtalk_oa':
    auth_config_json = {
        "app_key": "...",
        "app_secret": "...",
        "default_password": "Changeme@123",  # initial password for new users
        "root_dept_id": 1,                   # DingTalk root dept ID (default 1)
    }
"""
import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

import bcrypt
import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# Max concurrent DingTalk API calls. DingTalk enforces QPS limits per app
# (typical quota is 20 qps for 通讯录 APIs); 10 keeps us well under the ceiling
# while cutting wall time for 100+ departments from minutes to ~20s.
_DT_CONCURRENCY = 10

ProgressCb = Optional[Callable[[str, int, int], Awaitable[None]]]

from app.database import generate_uuid
from app.domains.organization.models import Department, UserDepartment
from app.domains.auth.models import User, UserRole

logger = logging.getLogger("spt_crm.dingtalk_sync")

_BASE = "https://oapi.dingtalk.com"
_BASE_V2 = "https://api.dingtalk.com"


# ─────────────── OAuth2 SSO (一键登录) ───────────────

async def exchange_oauth_code(
    app_key: str,
    app_secret: str,
    code: str,
    redirect_uri: str,
) -> dict:
    """Exchange an OAuth2 authorization code for a user access token.

    Uses DingTalk new API (api.dingtalk.com/v1.0/oauth2/userAccessToken).
    Returns dict with keys: accessToken, openId, unionId, corpId.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_BASE_V2}/v1.0/oauth2/userAccessToken",
            json={
                "clientId": app_key,
                "clientSecret": app_secret,
                "code": code,
                "redirectUri": redirect_uri,
                "grantType": "authorization_code",
            },
        )
    data = resp.json()
    if "accessToken" not in data:
        raise ValueError(f"钉钉OAuth换取token失败: {data}")
    return data


async def get_dingtalk_user_info(user_access_token: str) -> dict:
    """Get the current user's profile using their access token.

    Returns dict with keys: nick, mobile, openId, unionId, avatarUrl, email.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_BASE_V2}/v1.0/contact/users/me",
            headers={"x-acs-dingtalk-access-token": user_access_token},
        )
    data = resp.json()
    if "openId" not in data:
        raise ValueError(f"获取钉钉用户信息失败: {data}")
    return data


# ─────────────── DingTalk API helpers ───────────────

async def get_access_token(app_key: str, app_secret: str) -> str:
    """Fetch a short-lived access token for the corp app."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_BASE}/gettoken",
            params={"appkey": app_key, "appsecret": app_secret},
        )
    data = resp.json()
    if data.get("errcode", -1) != 0:
        raise ValueError(f"获取钉钉Token失败 [{data.get('errcode')}]: {data.get('errmsg')}")
    return data["access_token"]


async def fetch_all_departments(token: str) -> list[dict]:
    """Return flat list of all departments. fetch_child=true gets all levels."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_BASE}/department/list",
            params={"access_token": token, "fetch_child": "true"},
        )
    data = resp.json()
    if data.get("errcode", -1) != 0:
        raise ValueError(f"获取部门列表失败: {data.get('errmsg')}")
    return data.get("department", [])


async def fetch_dept_detail(token: str, dept_id: int) -> dict:
    """Get department detail including manager_userid_list."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_BASE}/department/get",
            params={"access_token": token, "id": dept_id},
        )
    data = resp.json()
    if data.get("errcode", -1) != 0:
        return {}
    return data.get("department", {})


async def fetch_users_by_dept(token: str, dept_id: int) -> list[dict]:
    """Return all users in a department (paginated)."""
    users: list[dict] = []
    offset = 0
    while True:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{_BASE}/user/listbypage",
                params={
                    "access_token": token,
                    "department_id": dept_id,
                    "offset": offset,
                    "size": 100,
                },
            )
        data = resp.json()
        if data.get("errcode", -1) != 0:
            logger.warning(f"获取部门 {dept_id} 用户失败: {data.get('errmsg')}")
            break
        batch = data.get("userlist", [])
        users.extend(batch)
        if not data.get("hasMore", False):
            break
        offset += 100
    return users


# ─────────────── Sync: Departments ───────────────

async def sync_departments(
    db: AsyncSession,
    tenant_id: str,
    token: str,
    sync_leaders: bool = True,
    progress_cb: ProgressCb = None,
) -> dict:
    """
    Sync DingTalk department tree into local Department table.

    Matching strategy: dept name + parent name combo.
    Creates new depts for unmatched ones; updates sort_order.
    If sync_leaders=True also fetches dept detail to set leader_id.

    Returns: { created, updated, total, dt_to_local: {dt_dept_id: local_dept_id} }
    """
    if progress_cb:
        await progress_cb("拉取部门列表", 0, 0)
    dt_depts = await fetch_all_departments(token)
    # Sort: root (parentid=1 or 0) first, then by parentid asc
    dt_depts.sort(key=lambda d: (d.get("parentid", 0) not in (0, 1), d.get("parentid", 0), d.get("order", 0)))

    # Load existing local depts
    existing = (await db.execute(
        select(Department).where(Department.tenant_id == tenant_id)
    )).scalars().all()
    # Map: name -> list of local depts
    name_to_local: dict[str, list[Department]] = {}
    for d in existing:
        name_to_local.setdefault(d.name, []).append(d)

    # dt_dept_id (int) -> local dept id (str)
    dt_to_local: dict[int, str] = {}

    created = updated = 0

    for dt in dt_depts:
        dt_id: int = dt["id"]
        dt_name: str = dt["name"]
        dt_parentid: int = dt.get("parentid", 0)
        dt_order: int = dt.get("order", 0)

        # Find local parent
        local_parent_id: Optional[str] = dt_to_local.get(dt_parentid)

        # Try to match by name (prefer same parent)
        matched: Optional[Department] = None
        candidates = name_to_local.get(dt_name, [])
        for c in candidates:
            if c.parent_id == local_parent_id:
                matched = c
                break
        if not matched and candidates:
            matched = candidates[0]  # fallback: first by same name

        if matched:
            # Update sort_order if changed
            if matched.sort_order != dt_order:
                matched.sort_order = dt_order
                updated += 1
            dt_to_local[dt_id] = matched.id
        else:
            # Compute path
            parent_path = "/"
            if local_parent_id:
                parent_dept = next((d for d in existing if d.id == local_parent_id), None)
                if parent_dept:
                    parent_path = parent_dept.path.rstrip("/") + "/" if parent_dept.path else "/"
            dept = Department(
                id=generate_uuid(), tenant_id=tenant_id,
                name=dt_name, parent_id=local_parent_id,
                path=parent_path + dt_name + "/",
                sort_order=dt_order,
            )
            db.add(dept)
            await db.flush()
            existing.append(dept)
            name_to_local.setdefault(dt_name, []).append(dept)
            dt_to_local[dt_id] = dept.id
            created += 1

    await db.commit()

    # Sync leaders: parallel fetch of dept detail, then sequential DB update
    leader_updated = 0
    if sync_leaders:
        sem = asyncio.Semaphore(_DT_CONCURRENCY)

        async def _fetch(dt: dict) -> tuple[int, dict]:
            async with sem:
                try:
                    return dt["id"], await fetch_dept_detail(token, dt["id"])
                except Exception as e:
                    logger.warning(f"获取部门 {dt['id']} 主管失败: {e}")
                    return dt["id"], {}

        total = len(dt_depts)
        done = 0
        if progress_cb:
            await progress_cb("同步部门主管", done, total)
        # Gather in chunks so we can report progress periodically
        chunk_size = _DT_CONCURRENCY * 4
        results: list[tuple[int, dict]] = []
        for i in range(0, total, chunk_size):
            chunk = dt_depts[i : i + chunk_size]
            chunk_results = await asyncio.gather(*(_fetch(d) for d in chunk))
            results.extend(chunk_results)
            done += len(chunk)
            if progress_cb:
                await progress_cb("同步部门主管", done, total)

        for dt_id, detail in results:
            local_dept_id = dt_to_local.get(dt_id)
            if not local_dept_id or not detail:
                continue
            manager_list: list[str] = detail.get("manager_userid_list") or []
            if not manager_list:
                continue
            first_manager_userid = manager_list[0]
            leader = (await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.username == first_manager_userid,
                )
            )).scalar_one_or_none()
            if not leader:
                continue
            local_dept = next((d for d in existing if d.id == local_dept_id), None)
            if local_dept and local_dept.leader_id != leader.id:
                local_dept.leader_id = leader.id
                leader_updated += 1

        if leader_updated:
            await db.commit()

    return {
        "created": created,
        "updated": updated,
        "total": len(dt_depts),
        "leader_updated": leader_updated,
        "dt_to_local": {str(k): v for k, v in dt_to_local.items()},
    }


# ─────────────── Sync: Users ───────────────

async def sync_users(
    db: AsyncSession,
    tenant_id: str,
    token: str,
    default_password: str = "Changeme@123",
    dt_to_local_dept: Optional[dict[int, str]] = None,
    progress_cb: ProgressCb = None,
) -> dict:
    """
    Sync DingTalk users into local User table.

    Matching: mobile phone number → local User.phone
    New users get default_password (must be changed on first login).
    Department memberships are synced.
    Dept leaders are set via isLeaderInDepts field.

    Returns: { created, updated, skipped, failed: [{userid, reason}], total }
    """
    if progress_cb:
        await progress_cb("拉取部门列表", 0, 0)
    dt_depts = await fetch_all_departments(token)

    # Build dept mapping if not provided
    if dt_to_local_dept is None:
        existing_depts = (await db.execute(
            select(Department).where(Department.tenant_id == tenant_id)
        )).scalars().all()
        name_to_local = {d.name: d.id for d in existing_depts}
        dt_to_local_dept = {}
        for dd in dt_depts:
            local_id = name_to_local.get(dd["name"])
            if local_id:
                dt_to_local_dept[dd["id"]] = local_id

    # Parallel fetch of users per department with bounded concurrency.
    # Serial fetch of 100+ depts took ~4 min in prod; gather drops this to ~20s.
    sem = asyncio.Semaphore(_DT_CONCURRENCY)

    async def _fetch_dept_users(dd: dict) -> list[dict]:
        async with sem:
            try:
                return await fetch_users_by_dept(token, dd["id"])
            except Exception as e:
                logger.warning(f"跳过部门 {dd['id']} 用户同步: {e}")
                return []

    total_depts = len(dt_depts)
    done_depts = 0
    all_dt_users: dict[str, dict] = {}
    if progress_cb:
        await progress_cb("拉取部门成员", done_depts, total_depts)
    chunk_size = _DT_CONCURRENCY * 4
    for i in range(0, total_depts, chunk_size):
        chunk = dt_depts[i : i + chunk_size]
        chunk_results = await asyncio.gather(*(_fetch_dept_users(dd) for dd in chunk))
        for users in chunk_results:
            for u in users:
                uid = u.get("userid", "")
                if uid and uid not in all_dt_users:
                    all_dt_users[uid] = u
        done_depts += len(chunk)
        if progress_cb:
            await progress_cb("拉取部门成员", done_depts, total_depts)

    # Load existing local users indexed by phone and username
    existing_users = (await db.execute(
        select(User).where(User.tenant_id == tenant_id)
    )).scalars().all()
    phone_to_user: dict[str, User] = {u.phone: u for u in existing_users if u.phone}
    username_to_user: dict[str, User] = {u.username: u for u in existing_users}

    created = updated = skipped = 0
    failed: list[dict] = []
    # Track dept leaders: local_dept_id -> local_user_id
    dept_leaders: dict[str, str] = {}

    total_users = len(all_dt_users)
    processed = 0
    if progress_cb:
        await progress_cb("写入本地用户", processed, total_users)
    for userid, dt_user in all_dt_users.items():
        try:
            mobile: str = dt_user.get("mobile") or dt_user.get("telephone") or ""
            name: str = dt_user.get("name") or userid
            email: str = dt_user.get("email") or dt_user.get("orgEmail") or ""
            is_active: bool = dt_user.get("active", True)
            dt_dept_ids: list[int] = dt_user.get("department", [])

            # Parse isLeaderInDepts (may be dict or JSON string)
            is_leader_raw = dt_user.get("isLeaderInDepts", {})
            if isinstance(is_leader_raw, str):
                try:
                    is_leader_raw = json.loads(is_leader_raw)
                except Exception:
                    is_leader_raw = {}

            # Match to local user
            local_user: Optional[User] = None
            if mobile:
                local_user = phone_to_user.get(mobile)
            if not local_user:
                local_user = username_to_user.get(userid)

            if local_user:
                # Update fields if changed
                changed = False
                if name and local_user.real_name != name:
                    local_user.real_name = name
                    changed = True
                if email and local_user.email != email:
                    local_user.email = email
                    changed = True
                if mobile and local_user.phone != mobile:
                    local_user.phone = mobile
                    changed = True
                if local_user.is_active != is_active:
                    local_user.is_active = is_active
                    changed = True
                if changed:
                    updated += 1
                else:
                    skipped += 1
            else:
                # Create new user
                if not mobile:
                    failed.append({"userid": userid, "reason": "无手机号，跳过创建"})
                    continue
                # Check username uniqueness; use userid or mobile as fallback
                uname = userid if userid not in username_to_user else f"dt_{mobile}"
                if uname in username_to_user:
                    failed.append({"userid": userid, "reason": f"用户名 {uname} 已存在"})
                    continue
                pwd_hash = bcrypt.hashpw(default_password.encode(), bcrypt.gensalt()).decode()
                local_user = User(
                    id=generate_uuid(), tenant_id=tenant_id,
                    username=uname, password_hash=pwd_hash,
                    real_name=name, phone=mobile or None,
                    email=email or None, is_active=is_active,
                )
                db.add(local_user)
                await db.flush()
                phone_to_user[mobile] = local_user
                username_to_user[uname] = local_user
                created += 1

            if local_user is None:
                continue

            # Sync dept memberships: replace with current DT assignments
            await db.execute(
                delete(UserDepartment).where(
                    UserDepartment.user_id == local_user.id,
                    UserDepartment.tenant_id == tenant_id,
                )
            )
            for dt_did in dt_dept_ids:
                local_dept_id = dt_to_local_dept.get(dt_did)
                if local_dept_id:
                    db.add(UserDepartment(
                        id=generate_uuid(), tenant_id=tenant_id,
                        user_id=local_user.id, department_id=local_dept_id,
                    ))
                    # Check if this user is a leader in this dept
                    if is_leader_raw.get(str(dt_did)) or is_leader_raw.get(dt_did):
                        dept_leaders[local_dept_id] = local_user.id

        except Exception as e:
            logger.error(f"同步用户 {userid} 失败: {e}")
            failed.append({"userid": userid, "reason": str(e)})

        processed += 1
        # Tick every 50 users to avoid flooding the progress store
        if progress_cb and (processed % 50 == 0 or processed == total_users):
            await progress_cb("写入本地用户", processed, total_users)

    await db.commit()

    # Apply dept leaders
    leader_updated = 0
    if dept_leaders:
        depts = (await db.execute(
            select(Department).where(
                Department.id.in_(dept_leaders.keys()),
                Department.tenant_id == tenant_id,
            )
        )).scalars().all()
        for dept in depts:
            new_leader = dept_leaders.get(dept.id)
            if new_leader and dept.leader_id != new_leader:
                dept.leader_id = new_leader
                leader_updated += 1
        if leader_updated:
            await db.commit()

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": len(all_dt_users),
        "leader_updated": leader_updated,
        "failed": failed,
    }
