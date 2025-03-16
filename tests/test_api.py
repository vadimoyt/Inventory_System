import pytest
from httpx import AsyncClient
from backend.routs import app, get_db
from backend.models import Base, User, Manufacturer
from backend.auth import hash_password
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import asyncio
import pytest_asyncio



pytestmark = pytest.mark.asyncio

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/test_db"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=True)
TestSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def init_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

@pytest_asyncio.fixture
async def db_session(init_db):
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        return db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()

async def test_show_register_form(client):
    response = await client.get("/register")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

async def test_register_user(client):
    response = await client.post("/register", data={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass"
    })
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

async def test_register_existing_username(client, db_session):
    new_user = User(username="testuser", email="unique@example.com", hashed_password=hash_password("testpass"))
    db_session.add(new_user)
    await db_session.commit()

    response = await client.post("/register", data={
        "username": "testuser",
        "email": "new@example.com",
        "password": "testpass"
    })
    assert response.status_code == 400
    assert "Username already exists" in response.text

async def test_show_login_form(client):
    response = await client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

async def test_login(client, db_session):
    new_user = User(username="testuser", email="test@example.com", hashed_password=hash_password("testpass"))
    db_session.add(new_user)
    await db_session.commit()

    response = await client.post("/login", data={
        "username": "testuser",
        "password": "testpass"
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "auth_token" in response.cookies

async def test_login_wrong_password(client, db_session):
    new_user = User(username="testuser", email="test@example.com", hashed_password=hash_password("testpass"))
    db_session.add(new_user)
    await db_session.commit()

    response = await client.post("/login", data={
        "username": "testuser",
        "password": "wrongpass"
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=1"
    assert "auth_token" not in response.cookies

async def test_logout(client, db_session):
    new_user = User(username="testuser", email="test@example.com", hashed_password=hash_password("testpass"))
    db_session.add(new_user)
    await db_session.commit()

    login_response = await client.post("/login", data={
        "username": "testuser",
        "password": "testpass"
    }, follow_redirects=False)
    assert "auth_token" in login_response.cookies
    auth_token = login_response.cookies["auth_token"]

    response = await client.get("/logout", cookies={"auth_token": auth_token}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "auth_token" in response.headers["Set-Cookie"]
    assert "Max-Age=0" in response.headers["Set-Cookie"]

async def test_get_manufacturer(client, db_session):
    new_user = User(username="testuser", email="test@example.com", hashed_password=hash_password("testpass"))
    db_session.add(new_user)
    await db_session.commit()

    manufacturer = Manufacturer(
        name="Test Manufacturer",
        address="123 Test St",
        phone_number="1234567890",
        user_id=new_user.id
    )
    db_session.add(manufacturer)
    await db_session.commit()

    login_response = await client.post("/login", data={
        "username": "testuser",
        "password": "testpass"
    }, follow_redirects=False)
    auth_token = login_response.cookies["auth_token"]

    response = await client.get("/manufacturer", cookies={"auth_token": auth_token})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Test Manufacturer" in response.text
