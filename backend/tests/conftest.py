"""Shared test fixtures for API integration tests.

Recreates the SQLAlchemy engine per test with NullPool to avoid
asyncpg connection pool conflicts across event loops.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import generate_uuid

from tests.lead_intel_helpers import DEMO_TENANT


ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


@pytest.fixture
async def client():
    import app.database as db_module

    # NullPool: each connection is created/closed per use, no pool lingering across event loops
    new_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    new_factory = async_sessionmaker(new_engine, expire_on_commit=False)

    db_module.engine = new_engine
    db_module.async_session_factory = new_factory

    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await new_engine.dispose()


@pytest.fixture
async def auth_headers(client: AsyncClient):
    """Login as admin and return auth headers."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": ADMIN_USER, "password": ADMIN_PASS,
    })
    data = resp.json()
    assert data["code"] == 0, f"Login failed: {data}"
    token = data["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def db():
    """独立 DB 会话（与 client 同库，供直接查表/调 service 的用例）。"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def lead_intel_user(db):
    """与兜底流程指定人员 username 对齐的测试情报审批人，用完清理。"""
    from app.domains.auth.models import User
    from app.domains.lowcode.workflow_service import _LEAD_INTEL_APPROVER_USERNAMES

    test_username = _LEAD_INTEL_APPROVER_USERNAMES[0]
    existing = (await db.execute(select(User).where(
        User.tenant_id == DEMO_TENANT, User.username == test_username,
    ))).scalar_one_or_none()
    if existing is not None:
        was_active = existing.is_active
        existing.is_active = True
        await db.commit()
        yield existing.id
        existing.is_active = was_active
        await db.commit()
        return

    u = User(
        id=generate_uuid(), tenant_id=DEMO_TENANT, username=test_username,
        real_name="测试内勤", password_hash="x", is_active=True,
    )
    db.add(u)
    await db.commit()

    yield u.id

    await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": u.id})
    await db.commit()
