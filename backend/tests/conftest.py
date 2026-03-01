"""Shared test fixtures for API integration tests.

Recreates the SQLAlchemy engine per test with NullPool to avoid
asyncpg connection pool conflicts across event loops.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


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
