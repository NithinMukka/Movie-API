"""
Async test harness.

Tests run against an in-memory SQLite database (no remote Postgres needed).
We create a dedicated async engine, build the schema from the models' metadata,
and override the app's `get_db` dependency to use it. The real asyncpg engine in
database.py is never connected to during tests.
"""
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker
# pyrefly: ignore [missing-import]
from sqlalchemy.pool import StaticPool

import main
import models
from database import Base, get_db
from auth import hash_password, create_access_token

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Local Docker Postgres (see docker-compose.test.yml). Override via env var.
DEFAULT_PG_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/booking_test"
TEST_PG_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_PG_URL)


@pytest_asyncio.fixture
async def session_factory():
    # StaticPool keeps a single shared connection, so the in-memory DB and its
    # tables persist across every session within a test.
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield factory

    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    main.app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    main.app.dependency_overrides.clear()


async def _make_user(session_factory, name, email, password, role):
    async with session_factory() as session:
        user = models.User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


@pytest_asyncio.fixture
async def admin_headers(session_factory):
    uid = await _make_user(session_factory, "Admin", "admin@test.com", "admin123", "admin")
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


@pytest_asyncio.fixture
async def customer_headers(session_factory):
    uid = await _make_user(session_factory, "Cust", "cust@test.com", "cust123", "customer")
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


# ---------------------------------------------------------------------------
# Postgres tier — for concurrency/locking tests that SQLite cannot exercise.
# Auto-skipped when the test DB is unreachable, so the SQLite suite still runs
# on a machine with nothing started.
# ---------------------------------------------------------------------------

def _pg_reachable() -> bool:
    import psycopg2  # sync driver, only used here for a quick liveness probe
    sync_url = TEST_PG_URL.replace("+asyncpg", "")
    try:
        conn = psycopg2.connect(sync_url, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    if _pg_reachable():
        return
    skip_pg = pytest.mark.skip(
        reason="Postgres test DB unreachable — run: docker compose -f docker-compose.test.yml up -d"
    )
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip_pg)


@pytest_asyncio.fixture
async def pg_engine():
    # Normal pool (NOT StaticPool) so concurrent requests get distinct
    # connections / transactions — required for SELECT ... FOR UPDATE to mean
    # anything. pool_size comfortably exceeds the concurrency we test.
    engine = create_async_engine(TEST_PG_URL, pool_size=20, max_overflow=10)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)   # clean any leftover schema
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session_factory(pg_engine):
    return sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def pg_client(pg_session_factory):
    async def override_get_db():
        async with pg_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    main.app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    main.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def pg_admin_headers(pg_session_factory):
    uid = await _make_user(pg_session_factory, "Admin", "admin@test.com", "admin123", "admin")
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


@pytest_asyncio.fixture
async def pg_customer_headers(pg_session_factory):
    uid = await _make_user(pg_session_factory, "Cust", "cust@test.com", "cust123", "customer")
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}
