import pytest
from httpx import AsyncClient
from backend.database import get_db
from main import app
from backend.models import Base, User, Sale, Product, Stock, Manufacturer, Counterparty, Agreement
from datetime import datetime
from backend.auth import hash_password
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import asyncio
from sqlalchemy import select
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

@pytest_asyncio.fixture
async def authenticated_client(client, db_session):
    user = User(username="testuser", email="test@example.com", hashed_password=hash_password("testpass"))
    db_session.add(user)
    await db_session.commit()
    login_response = await client.post("/login", data={"username": "testuser", "password": "testpass"})
    return client, user

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
    user = User(username="testuser", email="unique@example.com", hashed_password=hash_password("testpass"))
    db_session.add(user)
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
    user = User(username="testuser", email="test@example.com", hashed_password=hash_password("testpass"))
    db_session.add(user)
    await db_session.commit()
    response = await client.post("/login", data={"username": "testuser", "password": "testpass"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "auth_token" in response.cookies

async def test_login_wrong_password(client, db_session):
    user = User(username="testuser", email="test@example.com", hashed_password=hash_password("testpass"))
    db_session.add(user)
    await db_session.commit()
    response = await client.post("/login", data={"username": "testuser", "password": "wrongpass"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=1"
    assert "auth_token" not in response.cookies

async def test_logout(authenticated_client):
    client, _ = authenticated_client
    response = await client.get("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "auth_token" in response.headers["Set-Cookie"]
    assert "Max-Age=0" in response.headers["Set-Cookie"]

async def test_create_product_form(authenticated_client):
    client, _ = authenticated_client
    response = await client.get("/product/create")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

async def test_create_product(authenticated_client, db_session):
    client, user = authenticated_client
    manufacturer = Manufacturer(name="Test Man", address="123 St", phone_number="12345", user_id=user.id)
    counterparty = Counterparty(name="Test Counter", address="456 St", phone_number="67890", user_id=user.id)
    agreement = Agreement(
        contract_number="A1",
        date_signed=datetime.utcnow(),
        counterparty_id=1,
        user_id=user.id
    )
    db_session.add_all([manufacturer, counterparty])
    await db_session.commit()
    agreement.counterparty_id = counterparty.id
    db_session.add(agreement)
    await db_session.commit()
    response = await client.post("/product/create", data={
        "name": "Test Product",
        "price": 100.0,
        "manufacturer_id": manufacturer.id,
        "counterparty_id": counterparty.id,
        "agreement_id": agreement.id,
        "user_id": user.id
    })
    assert response.status_code == 303
    assert response.headers["location"] == "/product"
    product = await db_session.execute(select(Product).filter(Product.name == "Test Product"))
    assert product.scalar_one_or_none() is not None

async def test_add_stock(authenticated_client, db_session):
    client, user = authenticated_client
    manufacturer = Manufacturer(name="Test Man", address="123 St", phone_number="12345", user_id=user.id)
    counterparty = Counterparty(name="Test Counter", address="456 St", phone_number="67890", user_id=user.id)
    agreement = Agreement(
        contract_number="A1",
        date_signed=datetime.utcnow(),
        counterparty_id=1,
        user_id=user.id
    )
    db_session.add_all([manufacturer, counterparty])
    await db_session.commit()
    agreement.counterparty_id = counterparty.id
    db_session.add(agreement)
    await db_session.commit()
    product = Product(
        name="Test Product",
        price=100.0,
        manufacturer_id=manufacturer.id,
        counterparty_id=counterparty.id,
        agreement_id=agreement.id,
        user_id=user.id
    )
    db_session.add(product)
    await db_session.commit()
    response = await client.post("/stocks/create", data={
        "product_id": product.id,
        "quantity": 50,
        "user_id": user.id
    })
    assert response.status_code == 303
    stock = await db_session.execute(select(Stock).filter(Stock.product_id == product.id))
    assert stock.scalar_one_or_none().quantity == 50

async def test_get_sales(authenticated_client):
    client, user = authenticated_client
    response = await client.get("/sales")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

async def test_create_sale(authenticated_client, db_session):
    client, user = authenticated_client
    manufacturer = Manufacturer(name="Test Man", address="123 St", phone_number="12345", user_id=user.id)
    counterparty = Counterparty(name="Test Counter", address="456 St", phone_number="67890", user_id=user.id)
    agreement = Agreement(
        contract_number="A1",
        date_signed=datetime.utcnow(),
        counterparty_id=1,
        user_id=user.id
    )
    db_session.add_all([manufacturer, counterparty])
    await db_session.commit()
    agreement.counterparty_id = counterparty.id
    db_session.add(agreement)
    await db_session.commit()
    product = Product(
        name="Test Product",
        price=100.0,
        manufacturer_id=manufacturer.id,
        counterparty_id=counterparty.id,
        agreement_id=agreement.id,
        user_id=user.id
    )
    stock = Stock(product_id=1, quantity=20, user_id=user.id)
    db_session.add(product)
    await db_session.commit()
    stock.product_id = product.id
    db_session.add(stock)
    await db_session.commit()
    response = await client.post("/sales/create", data={
        "product_id": product.id,
        "quantity": 10
    })
    assert response.status_code == 303
    assert response.headers["location"] == "/sales"
    sale = await db_session.execute(select(Sale).filter(Sale.product_id == product.id))
    sale_obj = sale.scalar_one_or_none()
    assert sale_obj.quantity == 10
    assert sale_obj.total_price == 1000.0
    stock = await db_session.execute(select(Stock).filter(Stock.product_id == product.id))
    assert stock.scalar_one_or_none().quantity == 10

async def test_create_sale_not_enough_stock(authenticated_client, db_session):
    client, user = authenticated_client
    manufacturer = Manufacturer(name="Test Man", address="123 St", phone_number="12345", user_id=user.id)
    counterparty = Counterparty(name="Test Counter", address="456 St", phone_number="67890", user_id=user.id)
    agreement = Agreement(
        contract_number="A1",
        date_signed=datetime.utcnow(),
        counterparty_id=1,
        user_id=user.id
    )
    db_session.add_all([manufacturer, counterparty])
    await db_session.commit()
    agreement.counterparty_id = counterparty.id
    db_session.add(agreement)
    await db_session.commit()
    product = Product(
        name="Test Product",
        price=100.0,
        manufacturer_id=manufacturer.id,
        counterparty_id=counterparty.id,
        agreement_id=agreement.id,
        user_id=user.id
    )
    stock = Stock(product_id=1, quantity=5, user_id=user.id)
    db_session.add(product)
    await db_session.commit()
    stock.product_id = product.id
    db_session.add(stock)
    await db_session.commit()
    response = await client.post("/sales/create", data={
        "product_id": product.id,
        "quantity": 10
    })
    assert response.status_code == 400
    assert "Not enough stock available" in response.text

async def test_delete_sale(authenticated_client, db_session):
    client, user = authenticated_client
    manufacturer = Manufacturer(name="Test Man", address="123 St", phone_number="12345", user_id=user.id)
    counterparty = Counterparty(name="Test Counter", address="456 St", phone_number="67890", user_id=user.id)
    agreement = Agreement(
        contract_number="A1",
        date_signed=datetime.utcnow(),
        counterparty_id=1,
        user_id=user.id
    )
    db_session.add_all([manufacturer, counterparty])
    await db_session.commit()
    agreement.counterparty_id = counterparty.id
    db_session.add(agreement)
    await db_session.commit()
    product = Product(
        name="Test Product",
        price=100.0,
        manufacturer_id=manufacturer.id,
        counterparty_id=counterparty.id,
        agreement_id=agreement.id,
        user_id=user.id
    )
    stock = Stock(product_id=1, quantity=10, user_id=user.id)
    sale = Sale(product_id=1, quantity=5, total_price=500.0, user_id=user.id)
    db_session.add(product)
    await db_session.commit()
    stock.product_id = product.id
    sale.product_id = product.id
    db_session.add_all([stock, sale])
    await db_session.commit()
    response = await client.get(f"/sales/delete/{sale.id}")
    assert response.status_code == 303
    assert response.headers["location"] == "/sales"
    deleted_sale = await db_session.execute(select(Sale).filter(Sale.id == sale.id))
    assert deleted_sale.scalar_one_or_none() is None
    updated_stock = await db_session.execute(select(Stock).filter(Stock.product_id == product.id))
    assert updated_stock.scalar_one().quantity == 15