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

# 离职人员一般被企业归档到名称含"离职"的部门；同步时跳过这些部门，只同步在职人员。
_RESIGNED_DEPT_KEYWORDS = ("离职", "已离职", "离任", "停用")


def _is_resigned_dept(name: str | None) -> bool:
    n = name or ""
    return any(k in n for k in _RESIGNED_DEPT_KEYWORDS)


def _filter_active_depts(depts: list[dict]) -> list[dict]:
    """剔除离职归档部门，只保留在职部门。"""
    return [d for d in depts if not _is_resigned_dept(d.get("name", ""))]


def _topo_sort_dingtalk_depts(dt_depts: list[dict]) -> list[dict]:
    """父部门排在子部门之前。

    旧实现按 parentid 数值排序：当「子部门的 parentid」小于「父部门的 parentid」时，
    子部门会先入队，本地 parent 尚未建立 → parent_id=None，整棵子树被甩到顶层
    （例如技术总工下的研发中心/设计室跑到组织树外面）。
    """
    by_id: dict[int, dict] = {}
    for d in dt_depts:
        try:
            by_id[int(d["id"])] = d
        except (KeyError, TypeError, ValueError):
            continue
    children: dict[int, list[dict]] = {}
    roots: list[dict] = []
    for d in by_id.values():
        try:
            pid = int(d.get("parentid") or 0)
        except (TypeError, ValueError):
            pid = 0
        if pid in by_id:
            children.setdefault(pid, []).append(d)
        else:
            roots.append(d)

    def order_key(d: dict) -> tuple:
        try:
            return (-int(d.get("order") or 0), int(d["id"]))
        except (TypeError, ValueError):
            return (0, 0)

    out: list[dict] = []

    def walk(nodes: list[dict]) -> None:
        for n in sorted(nodes, key=order_key):
            out.append(n)
            try:
                nid = int(n["id"])
            except (KeyError, TypeError, ValueError):
                continue
            walk(children.get(nid, []))

    walk(roots)
    seen = {int(d["id"]) for d in out if d.get("id") is not None}
    for d in dt_depts:
        try:
            did = int(d["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if did not in seen:
            out.append(d)
    return out


def _dept_path(name: str, parent: Optional["Department"]) -> str:
    if parent and parent.path:
        return parent.path.rstrip("/") + "/" + name + "/"
    return f"/{name}/"


def _rebuild_department_paths(existing: list["Department"]) -> int:
    """按 parent_id 重算全部 path（父节点挪动后子树 path 也要对齐）。"""
    by_id = {d.id: d for d in existing}
    changed = 0

    def compute(d: Department, stack: set[str]) -> str:
        if d.id in stack:
            return f"/{d.name}/"
        if not d.parent_id or d.parent_id not in by_id:
            return f"/{d.name}/"
        stack.add(d.id)
        parent_path = compute(by_id[d.parent_id], stack)
        stack.discard(d.id)
        return parent_path.rstrip("/") + "/" + d.name + "/"

    for d in existing:
        new_path = compute(d, set())
        if d.path != new_path:
            d.path = new_path
            changed += 1
    return changed


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


async def get_userinfo_by_auth_code(app_key: str, app_secret: str, auth_code: str) -> dict:
    """容器内免登：用 JSAPI requestAuthCode 得到的临时授权码换取用户身份。

    与 OAuth2 扫码登录不同——这里用「企业应用 access_token + topapi/v2/user/getuserinfo」
    直接换 userid，再用 topapi/v2/user/get 补全手机号/unionId 供匹配本地账号。
    返回 {userid, name, mobile, unionid}。
    """
    token = await get_access_token(app_key, app_secret)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_BASE}/topapi/v2/user/getuserinfo",
            params={"access_token": token},
            json={"code": auth_code},
        )
    data = resp.json()
    if data.get("errcode", -1) != 0:
        raise ValueError(f"钉钉免登换取用户失败 [{data.get('errcode')}]: {data.get('errmsg')}")
    result = data.get("result", {}) or {}
    userid = result.get("userid")
    if not userid:
        raise ValueError("钉钉免登未返回 userid")
    info = {"userid": userid, "name": result.get("name"), "mobile": None, "unionid": None}
    # 补全手机号/unionId（用于按手机号匹配本地账号）
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp2 = await client.post(
                f"{_BASE}/topapi/v2/user/get",
                params={"access_token": token},
                json={"userid": userid},
            )
        d2 = resp2.json()
        if d2.get("errcode", -1) == 0:
            r2 = d2.get("result", {}) or {}
            info["mobile"] = r2.get("mobile") or r2.get("telephone")
            info["unionid"] = r2.get("unionid")
            info["name"] = info["name"] or r2.get("name")
    except Exception as e:
        logger.warning("钉钉免登补全用户详情失败: %s", e)
    return info


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


async def _apply_dept_managers_from_dingtalk(
    db: AsyncSession,
    tenant_id: str,
    token: str,
    dt_depts: list[dict],
    dt_to_local: dict[int, str],
    progress_cb: ProgressCb = None,
) -> int:
    """按钉钉部门详情 manager_userid_list 写本地 departments.leader_id。

    匹配规则：钉钉 userid == 本地 User.username（用户同步建号即用 userid）。
    返回本次更新的部门数。
    """
    if not dt_depts or not dt_to_local:
        return 0

    sem = asyncio.Semaphore(_DT_CONCURRENCY)

    async def _fetch(dt: dict) -> tuple[int, dict]:
        async with sem:
            try:
                return int(dt["id"]), await fetch_dept_detail(token, int(dt["id"]))
            except Exception as e:
                logger.warning(f"获取部门 {dt.get('id')} 主管失败: {e}")
                return int(dt.get("id") or 0), {}

    total = len(dt_depts)
    done = 0
    if progress_cb:
        await progress_cb("同步部门主管", done, total)
    chunk_size = _DT_CONCURRENCY * 4
    results: list[tuple[int, dict]] = []
    for i in range(0, total, chunk_size):
        chunk = dt_depts[i : i + chunk_size]
        chunk_results = await asyncio.gather(*(_fetch(d) for d in chunk))
        results.extend(chunk_results)
        done += len(chunk)
        if progress_cb:
            await progress_cb("同步部门主管", done, total)

    existing = (await db.execute(
        select(Department).where(Department.tenant_id == tenant_id)
    )).scalars().all()
    by_id = {d.id: d for d in existing}

    leader_updated = 0
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
        local_dept = by_id.get(local_dept_id)
        if local_dept and local_dept.leader_id != leader.id:
            local_dept.leader_id = leader.id
            leader_updated += 1

    if leader_updated:
        await db.commit()
    return leader_updated


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

    Matching strategy: same name + same parent first; else unclaimed same-name
    (and re-parent to DingTalk parent). Always refresh parent_id / path / sort_order.
    Creates new depts for unmatched ones.
    If sync_leaders=True also fetches dept detail to set leader_id.

    Returns: { created, updated, total, dt_to_local: {dt_dept_id: local_dept_id} }
    """
    if progress_cb:
        await progress_cb("拉取部门列表", 0, 0)
    dt_depts = _topo_sort_dingtalk_depts(
        _filter_active_depts(await fetch_all_departments(token))
    )

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
    claimed_local: set[str] = set()

    created = updated = 0

    for dt in dt_depts:
        try:
            dt_id = int(dt["id"])
        except (KeyError, TypeError, ValueError):
            continue
        dt_name: str = dt.get("name") or ""
        if not dt_name:
            continue
        try:
            dt_parentid = int(dt.get("parentid") or 0)
        except (TypeError, ValueError):
            dt_parentid = 0
        try:
            dt_order = int(dt.get("order") or 0)
        except (TypeError, ValueError):
            dt_order = 0

        # Find local parent（钉钉根 parentid=1/0 且不在列表中 → 本地顶层）
        local_parent_id: Optional[str] = dt_to_local.get(dt_parentid)
        parent_obj = next((d for d in existing if d.id == local_parent_id), None) if local_parent_id else None

        # Try to match by name (prefer same parent, skip already claimed)
        matched: Optional[Department] = None
        candidates = name_to_local.get(dt_name, [])
        for c in candidates:
            if c.id in claimed_local:
                continue
            if c.parent_id == local_parent_id:
                matched = c
                break
        if not matched:
            for c in candidates:
                if c.id not in claimed_local:
                    matched = c
                    break

        if matched:
            changed = False
            if matched.parent_id != local_parent_id:
                matched.parent_id = local_parent_id
                changed = True
            new_path = _dept_path(matched.name, parent_obj)
            if matched.path != new_path:
                matched.path = new_path
                changed = True
            if matched.sort_order != dt_order:
                matched.sort_order = dt_order
                changed = True
            if changed:
                updated += 1
            dt_to_local[dt_id] = matched.id
            claimed_local.add(matched.id)
        else:
            dept = Department(
                id=generate_uuid(), tenant_id=tenant_id,
                name=dt_name, parent_id=local_parent_id,
                path=_dept_path(dt_name, parent_obj),
                sort_order=dt_order,
            )
            db.add(dept)
            await db.flush()
            existing.append(dept)
            name_to_local.setdefault(dt_name, []).append(dept)
            dt_to_local[dt_id] = dept.id
            claimed_local.add(dept.id)
            created += 1

    # 祖先被挪动后，整棵子树 path 再扫一遍
    path_fixed = _rebuild_department_paths(existing)
    if path_fixed:
        updated += path_fixed

    await db.commit()

    # Sync leaders: parallel fetch of dept detail, then sequential DB update
    leader_updated = 0
    if sync_leaders:
        leader_updated = await _apply_dept_managers_from_dingtalk(
            db, tenant_id, token, dt_depts, dt_to_local, progress_cb=progress_cb,
        )

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
    sync_leaders: bool = True,
    progress_cb: ProgressCb = None,
) -> dict:
    """
    Sync DingTalk users into local User table.

    Matching: mobile phone number → local User.phone
    New users get default_password (must be changed on first login).
    Department memberships are synced.
    If sync_leaders=True, dept leaders are set from listbypage `isLeader`
    (and isLeaderInDepts if present), then backfilled via department detail
    manager_userid_list after users exist. Timed auto-sync should pass False
    so local manual leader_id is preserved.

    Returns: { created, updated, skipped, failed: [{userid, reason}], total }
    """
    if progress_cb:
        await progress_cb("拉取部门列表", 0, 0)
    dt_depts = _filter_active_depts(await fetch_all_departments(token))

    # Build dept mapping if not provided
    if dt_to_local_dept is None:
        existing_depts = (await db.execute(
            select(Department).where(Department.tenant_id == tenant_id)
        )).scalars().all()
        # 与部门同步同一套：按钉钉父子拓扑 + 同名优先同父匹配，避免重名部门挂错
        name_to_local: dict[str, list[Department]] = {}
        for d in existing_depts:
            name_to_local.setdefault(d.name, []).append(d)
        dt_to_local_dept = {}
        claimed: set[str] = set()
        for dd in _topo_sort_dingtalk_depts(dt_depts):
            try:
                did = int(dd["id"])
                pid = int(dd.get("parentid") or 0)
            except (KeyError, TypeError, ValueError):
                continue
            local_parent = dt_to_local_dept.get(pid)
            name = dd.get("name") or ""
            matched = None
            for c in name_to_local.get(name, []):
                if c.id in claimed:
                    continue
                if c.parent_id == local_parent:
                    matched = c
                    break
            if not matched:
                for c in name_to_local.get(name, []):
                    if c.id not in claimed:
                        matched = c
                        break
            if matched:
                dt_to_local_dept[did] = matched.id
                claimed.add(matched.id)

    # Parallel fetch of users per department with bounded concurrency.
    # Serial fetch of 100+ depts took ~4 min in prod; gather drops this to ~20s.
    sem = asyncio.Semaphore(_DT_CONCURRENCY)

    async def _fetch_dept_users(dd: dict) -> tuple[int, list[dict]]:
        async with sem:
            try:
                did = int(dd["id"])
            except (KeyError, TypeError, ValueError):
                return 0, []
            try:
                return did, await fetch_users_by_dept(token, did)
            except Exception as e:
                logger.warning(f"跳过部门 {did} 用户同步: {e}")
                return did, []

    total_depts = len(dt_depts)
    done_depts = 0
    all_dt_users: dict[str, dict] = {}
    # listbypage 返回的是当前部门维度的 isLeader(bool)，不是 isLeaderInDepts；
    # 同一人在多部门会出现多次，需按「userid → 其担任主管的部门 id 集合」累积。
    leader_dept_ids_by_user: dict[str, set[int]] = {}
    if progress_cb:
        await progress_cb("拉取部门成员", done_depts, total_depts)
    chunk_size = _DT_CONCURRENCY * 4
    for i in range(0, total_depts, chunk_size):
        chunk = dt_depts[i : i + chunk_size]
        chunk_results = await asyncio.gather(*(_fetch_dept_users(dd) for dd in chunk))
        for did, users in chunk_results:
            for u in users:
                uid = u.get("userid", "")
                if not uid:
                    continue
                if uid not in all_dt_users:
                    all_dt_users[uid] = u
                # 部门用户详情接口：isLeader 表示是否为本部门主管
                if did and u.get("isLeader"):
                    leader_dept_ids_by_user.setdefault(uid, set()).add(did)
                # 用户详情才有的 isLeaderInDepts（若将来换接口仍兼容）
                raw = u.get("isLeaderInDepts")
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except Exception:
                        raw = {}
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if not v:
                            continue
                        try:
                            leader_dept_ids_by_user.setdefault(uid, set()).add(int(k))
                        except (TypeError, ValueError):
                            pass
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
    # 部门成员同步完成后，按「部门→角色」规则给这些用户补角色
    synced_user_ids: set[str] = set()

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

            # Parse isLeaderInDepts (may be dict or JSON string) — 用户详情接口才稳定有
            is_leader_raw = dt_user.get("isLeaderInDepts", {})
            if isinstance(is_leader_raw, str):
                try:
                    is_leader_raw = json.loads(is_leader_raw)
                except Exception:
                    is_leader_raw = {}
            if not isinstance(is_leader_raw, dict):
                is_leader_raw = {}
            # listbypage 累积的本部门 isLeader
            leader_from_list = leader_dept_ids_by_user.get(userid) or set()

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
                # 刻意不在这里回补 must_change_password：靠「hash 是否等于默认密码」
                # 反推「用户没设过密码」既慢又不准——bcrypt 每次校验约 250ms（cost 12），
                # 全员跑一遍会把事件循环卡死好几分钟；而管理员手动建号时如果用了同一个
                # 默认密码，会被误判成系统代建、从而放开免原密码通道。
                # 该标记只在下面「确实由本函数代写密码」时置位。存量账号由管理员在
                # 用户管理里「重置密码 + 要求用户自行设置」显式处理。
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
                    # 上面写入的是全租户共享的默认密码，本人无从知晓；
                    # 标记后其首次「修改密码」免填原密码，否则改密路径不可达。
                    must_change_password=True,
                )
                db.add(local_user)
                await db.flush()
                phone_to_user[mobile] = local_user
                username_to_user[uname] = local_user
                created += 1

            if local_user is None:
                continue

            synced_user_ids.add(local_user.id)

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
                    if sync_leaders and (
                        is_leader_raw.get(str(dt_did))
                        or is_leader_raw.get(dt_did)
                        or dt_did in leader_from_list
                    ):
                        dept_leaders[local_dept_id] = local_user.id

        except Exception as e:
            logger.error(f"同步用户 {userid} 失败: {e}")
            failed.append({"userid": userid, "reason": str(e)})

        processed += 1
        # Tick every 50 users to avoid flooding the progress store
        if progress_cb and (processed % 50 == 0 or processed == total_users):
            await progress_cb("写入本地用户", processed, total_users)

    await db.commit()

    # Apply dept leaders collected from user list (isLeader / isLeaderInDepts)
    leader_updated = 0
    if sync_leaders and dept_leaders:
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

    # 兜底：用部门详情 manager_userid_list 再补一轮。
    # 推荐流程是「先部门后用户」，首次同步部门时本地还没有 userid→用户，主管会全空；
    # 用户落库后再按钉钉 userid(=CRM username) 匹配主管即可补齐。
    # 定时自动同步传 sync_leaders=False，跳过以免覆盖本地手工指定。
    if sync_leaders:
        if progress_cb:
            await progress_cb("补全部门主管", 0, len(dt_depts))
        extra_leaders = await _apply_dept_managers_from_dingtalk(
            db, tenant_id, token, dt_depts, dt_to_local_dept or {}, progress_cb=progress_cb,
        )
        leader_updated += extra_leaders

    # 依「部门→角色」规则给同步进来的用户自动补角色(仅新增，不覆盖已有角色)
    roles_added = 0
    if synced_user_ids:
        try:
            from app.common.dept_role_auto import apply_dept_role_rules_bulk
            res = await apply_dept_role_rules_bulk(db, tenant_id, list(synced_user_ids))
            roles_added = res.get("roles_added", 0)
        except Exception as e:
            logger.warning("钉钉同步后自动补部门角色失败: %s", e)

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": len(all_dt_users),
        "leader_updated": leader_updated,
        "roles_added": roles_added,
        "failed": failed,
    }
