import logging
from fastapi import FastAPI, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from backend.database import get_db
from backend.models import Manufacturer, Counterparty, Agreement, Product, Sale, Stock, User
import datetime
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from fastapi_login import LoginManager
from backend.auth import hash_password, verify_password
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from datetime import timedelta
from jose import jwt, ExpiredSignatureError
from dotenv import load_dotenv
from celery import Celery
from typing import List
from pydantic import BaseModel


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Stock Management System",
    description="A system for managing products, sales, and stock with email notifications.",
    version="1.0.0"
)
templates = Jinja2Templates(directory="templates")

celery_app = Celery(
    "your_project",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

SECRET = os.getenv('SECRET_KEY', 'your-secret-key-here')
manager = LoginManager(SECRET, token_url="/login", use_cookie=True, cookie_name="auth_token")

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.mail.ru")
EMAIL_PORT = os.getenv("EMAIL_PORT", "587")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")

class ProductResponse(BaseModel):
    id: int
    name: str
    price: float

logger.info(f"EMAIL_HOST: {EMAIL_HOST}")
logger.info(f"EMAIL_PORT: {EMAIL_PORT}")
logger.info(f"EMAIL_USER: {EMAIL_USER}")
logger.info(f"EMAIL_PASSWORD: {EMAIL_PASSWORD}")
logger.info(f"EMAIL_FROM: {EMAIL_FROM}")

@manager.user_loader()
async def load_user(username: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalar_one_or_none()
    return user

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("auth_token")
    if not token:
        return RedirectResponse(url="/login", status_code=303)
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        username = payload.get("sub")
        if not username:
            return RedirectResponse(url="/login", status_code=303)
        user = await load_user(username, db)
        if user is None:
            return RedirectResponse(url="/login", status_code=303)
        return user
    except ExpiredSignatureError:
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("auth_token")
        return response
    except Exception as e:
        return RedirectResponse(url="/login", status_code=303)

def send_stock_alert_email(user_email: str, product_name: str, quantity: int, minimum_quantity: int = 10):
    """Отправка email-уведомления о низком остатке товара с использованием TLS."""
    if not user_email:
        logger.warning("Email пользователя не указан")
        return

    subject = "Уведомление о низких остатках"
    body = (
        f"Внимание! Остаток товара '{product_name}' упал ниже {minimum_quantity}. "
        f"Текущее количество: {quantity}."
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = user_email

    try:
        with smtplib.SMTP(EMAIL_HOST, int(EMAIL_PORT)) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email успешно отправлен на {user_email}")
    except Exception as e:
        logger.error(f"Ошибка при отправке email: {str(e)}")
        raise

@celery_app.task
def send_stock_alert_email_task(user_email: str, product_name: str, quantity: int):
    send_stock_alert_email(user_email, product_name, quantity)

@app.get("/", summary="Главная страница", description="Отображает главную страницу для авторизованного пользователя")
async def read_root(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/register", summary="Форма регистрации", description="Отображает форму для регистрации нового пользователя")
async def show_register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", summary="Регистрация пользователя", description="Создает нового пользователя")
async def register(
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    result = await db.execute(select(User).filter(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")
    new_user = User(username=username, email=email, hashed_password=hash_password(password))
    db.add(new_user)
    await db.commit()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/login", summary="Форма входа", description="Отображает форму для входа в систему")
async def show_login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", summary="Вход в систему", description="Аутентифицирует пользователя и выдает токен")
async def login(
        username: str = Form(...),
        password: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        response = RedirectResponse(url="/login?error=1", status_code=303)
        return response
    access_token = manager.create_access_token(data={"sub": user.username}, expires=timedelta(hours=1))
    response = RedirectResponse(url="/", status_code=303)
    manager.set_cookie(response, access_token)
    return response

@app.get("/logout", summary="Выход из системы", description="Удаляет токен и перенаправляет на страницу входа")
async def logout(user: User = Depends(get_current_user)):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("auth_token")
    return response

@app.get("/manufacturer", summary="Список производителей", description="Отображает список производителей пользователя")
async def get_manufacturer(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Manufacturer).filter(Manufacturer.user_id == user.id))
    manufacturers = result.scalars().all()
    return templates.TemplateResponse("manufacturers.html", {"request": request, "manufacturers": manufacturers})

@app.get("/manufacturer/create", summary="Форма создания производителя", description="Отображает форму для создания производителя")
async def create_manufacturer(request: Request):
    return templates.TemplateResponse("create_manufacturer.html", {"request": request})

@app.post("/manufacturer/create", summary="Создание производителя", description="Добавляет нового производителя")
async def create_manufacturer_post(
        name: str = Form(...),
        address: str = Form(...),
        manager: str = Form(...),
        phone_number: str = Form(...),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    new_manufacturer = Manufacturer(
        name=name,
        address=address,
        manager=manager,
        phone_number=phone_number,
        user_id=user.id
    )
    db.add(new_manufacturer)
    await db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)

@app.get(
    "/manufacturer/edit/{manufacturer_id}",
    summary="Форма редактирования производителя",
    description="Отображает форму редактирования"
)
async def edit_manufacturer(
        request: Request,
        manufacturer_id: int,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Manufacturer).
        filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id)
    )
    manufacturer = result.scalar_one_or_none()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found or you don't have permission")
    return templates.TemplateResponse("edit_manufacturer.html", {"request": request, "manufacturer": manufacturer})

@app.post(
    "/manufacturer/edit/{manufacturer_id}",
    summary="Редактирование производителя",
    description="Обновляет данные производителя"
)
async def edit_manufacturer_post(
        manufacturer_id: int,
        name: str = Form(...),
        address: str = Form(...),
        manager: str = Form(...),
        phone_number: str = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Manufacturer).
        filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id)
    )
    manufacturer = result.scalar_one_or_none()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found or you don't have permission")
    manufacturer.name = name
    manufacturer.address = address
    manufacturer.manager = manager
    manufacturer.phone_number = phone_number
    await db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)

@app.get(
    "/manufacturer/delete/{manufacturer_id}",
    summary="Удаление производителя",
    description="Удаляет производителя"
)
async def delete_manufacturer(
        manufacturer_id: int,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Manufacturer).
        filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id)
    )
    manufacturer = result.scalar_one_or_none()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found or you don't have permission")
    await db.delete(manufacturer)
    await db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)

@app.get(
    "/counterparty",
    summary="Список контрагентов",
    description="Отображает список контрагентов пользователя"
)
async def get_counterparty(
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
    counterparties = result.scalars().all()
    return templates.TemplateResponse("counterparties.html", {"request": request, "counterparties": counterparties})

@app.get("/counterparty/create", summary="Форма создания контрагента", description="Отображает форму для создания контрагента")
async def create_counterparty(request: Request):
    return templates.TemplateResponse("create_counterparty.html", {"request": request})

@app.post("/counterparty/create", summary="Создание контрагента", description="Добавляет нового контрагента")
async def create_counterparty_post(
        name: str = Form(...),
        address: str = Form(...),
        phone_number: str = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    new_counterparty = Counterparty(name=name, address=address, phone_number=phone_number, user_id=user.id)
    db.add(new_counterparty)
    await db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)

@app.get("/counterparty/edit/{counterparty_id}", summary="Форма редактирования контрагента", description="Отображает форму редактирования")
async def edit_counterparty(request: Request, counterparty_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    counterparty = result.scalar_one_or_none()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found or you don't have permission")
    return templates.TemplateResponse("edit_counterparty.html", {"request": request, "counterparty": counterparty})

@app.post("/counterparty/edit/{counterparty_id}", summary="Редактирование контрагента", description="Обновляет данные контрагента")
async def edit_counterparty_post(
        counterparty_id: int,
        name: str = Form(...),
        address: str = Form(...),
        phone_number: str = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    counterparty = result.scalar_one_or_none()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found or you don't have permission")
    counterparty.name = name
    counterparty.address = address
    counterparty.phone_number = phone_number
    await db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)

@app.get("/counterparty/delete/{counterparty_id}", summary="Удаление контрагента", description="Удаляет контрагента")
async def delete_counterparty(counterparty_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    counterparty = result.scalar_one_or_none()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found or you don't have permission")
    await db.delete(counterparty)
    await db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)

@app.get("/agreement", summary="Список соглашений", description="Отображает список соглашений пользователя")
async def get_agreement(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agreement).filter(Agreement.user_id == user.id))
    agreements = result.scalars().all()
    return templates.TemplateResponse("agreements.html", {"request": request, "agreements": agreements})

@app.get("/agreement/create", summary="Форма создания соглашения", description="Отображает форму для создания соглашения")
async def create_agreement(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
    counterparties = result.scalars().all()
    return templates.TemplateResponse("create_agreement.html", {"request": request, "counterparties": counterparties})

@app.post("/agreement/create", summary="Создание соглашения", description="Добавляет новое соглашение")
async def create_agreement_post(
        contract_number: str = Form(...),
        date_signed: str = Form(...),
        counterparty_id: int = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You don't have permission to use this counterparty")
    try:
        date_signed_dt = datetime.datetime.strptime(date_signed, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    new_agreement = Agreement(
        contract_number=contract_number,
        date_signed=date_signed_dt,
        counterparty_id=counterparty_id,
        user_id=user.id
    )
    db.add(new_agreement)
    await db.commit()
    return RedirectResponse(url="/agreement", status_code=303)

@app.get("/agreement/edit/{agreement_id}", summary="Форма редактирования соглашения", description="Отображает форму редактирования")
async def edit_agreement(request: Request, agreement_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
    agreement = result.scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
    result_counterparties = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
    counterparties = result_counterparties.scalars().all()
    return templates.TemplateResponse("edit_agreement.html", {"request": request, "agreement": agreement, "counterparties": counterparties})

@app.post("/agreement/edit/{agreement_id}", summary="Редактирование соглашения", description="Обновляет данные соглашения")
async def edit_agreement_post(
        agreement_id: int,
        contract_number: str = Form(...),
        date_signed: str = Form(...),
        counterparty_id: int = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
    agreement = result.scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You don't have permission to use this counterparty")
    try:
        date_signed_dt = datetime.datetime.strptime(date_signed, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    agreement.contract_number = contract_number
    agreement.date_signed = date_signed_dt
    agreement.counterparty_id = counterparty_id
    await db.commit()
    return RedirectResponse(url="/agreement", status_code=303)

@app.get("/agreement/delete/{agreement_id}", summary="Удаление соглашения", description="Удаляет соглашение")
async def delete_agreement(agreement_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
    agreement = result.scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
    await db.delete(agreement)
    await db.commit()
    return RedirectResponse(url="/agreement", status_code=303)

@app.get("/product", summary="Список продуктов", description="Отображает список продуктов пользователя")
async def get_products(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Product)
        .filter(Product.user_id == user.id)
        .options(
            joinedload(Product.manufacturer),
            joinedload(Product.counterparty),
            joinedload(Product.agreement),
            joinedload(Product.user)
        )
    )
    products = result.scalars().all()
    return templates.TemplateResponse("products.html", {"request": request, "products": products})

@app.get("/api/products", response_model=List[ProductResponse], summary="Получить список продуктов (API)", description="Возвращает список продуктов в формате JSON")
async def get_products_api(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Product).filter(Product.user_id == user.id))
    products = result.scalars().all()
    return [{"id": p.id, "name": p.name, "price": p.price} for p in products]

@app.get("/product/create", summary="Форма создания продукта", description="Отображает форму для создания продукта")
async def create_product(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    manufacturers = (await db.execute(select(Manufacturer).filter(Manufacturer.user_id == user.id))).scalars().all()
    counterparties = (await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))).scalars().all()
    agreements = (await db.execute(select(Agreement).filter(Agreement.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("create_product.html", {
        "request": request,
        "manufacturers": manufacturers,
        "counterparties": counterparties,
        "agreements": agreements
    })

@app.post("/product/create", summary="Создание продукта", description="Добавляет новый продукт")
async def create_product_post(
        name: str = Form(...),
        price: float = Form(...),
        manufacturer_id: int = Form(...),
        counterparty_id: int = Form(...),
        agreement_id: int = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(select(Manufacturer).filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You don't have permission to use this manufacturer")
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You don't have permission to use this counterparty")
    result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You don't have permission to use this agreement")
    new_product = Product(
        name=name,
        price=price,
        manufacturer_id=manufacturer_id,
        counterparty_id=counterparty_id,
        agreement_id=agreement_id,
        user_id=user.id
    )
    db.add(new_product)
    await db.commit()
    return RedirectResponse(url="/product", status_code=303)

@app.get("/product/edit/{product_id}", summary="Форма редактирования продукта", description="Отображает форму редактирования")
async def edit_product(request: Request, product_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Product).filter(Product.id == product_id, Product.user_id == user.id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or you don't have permission")
    manufacturers = (await db.execute(select(Manufacturer).filter(Manufacturer.user_id == user.id))).scalars().all()
    counterparties = (await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))).scalars().all()
    agreements = (await db.execute(select(Agreement).filter(Agreement.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("edit_product.html", {
        "request": request,
        "product": product,
        "manufacturers": manufacturers,
        "counterparties": counterparties,
        "agreements": agreements
    })

@app.post("/product/edit/{product_id}", summary="Редактирование продукта", description="Обновляет данные продукта")
async def edit_product_post(
        product_id: int,
        name: str = Form(...),
        price: float = Form(...),
        manufacturer_id: int = Form(...),
        counterparty_id: int = Form(...),
        agreement_id: int = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(select(Product).filter(Product.id == product_id, Product.user_id == user.id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or you don't have permission")
    result = await db.execute(select(Manufacturer).filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You don't have permission to use this manufacturer")
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You don't have permission to use this counterparty")
    result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You don't have permission to use this agreement")
    product.name = name
    product.price = price
    product.manufacturer_id = manufacturer_id
    product.counterparty_id = counterparty_id
    product.agreement_id = agreement_id
    await db.commit()
    return RedirectResponse(url="/product", status_code=303)

@app.get("/product/delete/{product_id}", summary="Удаление продукта", description="Удаляет продукт")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Product).filter(Product.id == product_id, Product.user_id == user.id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or you don't have permission")
    await db.delete(product)
    await db.commit()
    return RedirectResponse(url="/product", status_code=303)

@app.get("/sales", summary="Список продаж", description="Отображает список продаж пользователя")
async def get_sales(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Sale).filter(Sale.user_id == user.id))
    sales = result.scalars().all()
    return templates.TemplateResponse("sales.html", {"request": request, "sales": sales})

@app.get("/sale/create", summary="Форма создания продажи", description="Отображает форму для создания продажи")
async def create_sale(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("create_sale.html", {"request": request, "products": products})

@app.post("/sale/create", summary="Создание продажи", description="Добавляет новую продажу и отправляет уведомление о низком остатке через Celery")
async def create_sale_post(
        product_id: int = Form(...),
        quantity: int = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    logger.info(f"Начало создания продажи: product_id={product_id}, quantity={quantity}, user_id={user.id}")

    result_product = await db.execute(select(Product).filter(Product.id == product_id, Product.user_id == user.id))
    product = result_product.scalar_one_or_none()
    if not product:
        logger.error(f"Продукт не найден: product_id={product_id}, user_id={user.id}")
        raise HTTPException(status_code=404, detail="Product not found or you don't have permission")

    result_stock = await db.execute(select(Stock).filter(Stock.product_id == product_id, Stock.user_id == user.id))
    product_on_stock = result_stock.scalar_one_or_none()
    if not product_on_stock:
        logger.error(f"Товар не найден на складе: product_id={product_id}, user_id={user.id}")
        raise HTTPException(status_code=404, detail="Product not found in stock or you don't have permission")
    if product_on_stock.quantity < quantity:
        logger.error(f"Недостаточно товара на складе: stock_quantity={product_on_stock.quantity}, requested={quantity}")
        raise HTTPException(status_code=400, detail="Not enough stock available")

    total_price = product.price * quantity
    new_sale = Sale(
        product_id=product_id,
        quantity=quantity,
        total_price=total_price,
        user_id=user.id,
        date_sold=datetime.datetime.utcnow()
    )
    db.add(new_sale)
    product_on_stock.quantity -= quantity
    await db.commit()
    await db.refresh(product_on_stock)

    logger.info(f"Продажа создана, остаток: {product_on_stock.quantity}")

    if product_on_stock.quantity < 10:
        logger.info(f"Остаток меньше 10, отправка email через Celery на {user.email}")
        send_stock_alert_email_task.delay(user.email, product.name, product_on_stock.quantity)
    else:
        logger.info(f"Остаток {product_on_stock.quantity} >= 10, email не отправляется")

    return RedirectResponse(url="/sales", status_code=303)

@app.get("/sale/edit/{sale_id}", summary="Форма редактирования продажи", description="Отображает форму редактирования")
async def edit_sale(request: Request, sale_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Sale).filter(Sale.id == sale_id, Sale.user_id == user.id))
    sale = result.scalar_one_or_none()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found or you don't have permission")
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("edit_sale.html", {"request": request, "sale": sale, "products": products})

@app.post("/sale/edit/{sale_id}", summary="Редактирование продажи", description="Обновляет данные продажи и отправляет уведомления через Celery")
async def edit_sale_post(
        sale_id: int,
        product_id: int = Form(...),
        quantity: int = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result_sale = await db.execute(select(Sale).filter(Sale.id == sale_id, Sale.user_id == user.id))
    sale = result_sale.scalar_one_or_none()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found or you don't have permission")

    result_old_stock = await db.execute(select(Stock).filter(Stock.product_id == sale.product_id, Stock.user_id == user.id))
    old_product_on_stock = result_old_stock.scalar_one_or_none()

    result_new_stock = await db.execute(select(Stock).filter(Stock.product_id == product_id, Stock.user_id == user.id))
    new_product_on_stock = result_new_stock.scalar_one_or_none()
    if not new_product_on_stock:
        raise HTTPException(status_code=404, detail="New product not found in stock or you don't have permission")

    result_product = await db.execute(select(Product).filter(Product.id == product_id, Product.user_id == user.id))
    new_product = result_product.scalar_one_or_none()
    if not new_product:
        raise HTTPException(status_code=404, detail="New product not found or you don't have permission")

    quantity_difference = quantity - sale.quantity
    if quantity_difference > 0 and new_product_on_stock.quantity < quantity_difference:
        raise HTTPException(status_code=400, detail="Not enough stock available for new product")

    if old_product_on_stock:
        old_product_on_stock.quantity += sale.quantity

    if quantity_difference > 0:
        new_product_on_stock.quantity -= quantity_difference
    elif quantity_difference < 0:
        if old_product_on_stock:
            old_product_on_stock.quantity += abs(quantity_difference)

    total_price = new_product.price * quantity
    sale.product_id = product_id
    sale.quantity = quantity
    sale.total_price = total_price
    await db.commit()

    if old_product_on_stock:
        await db.refresh(old_product_on_stock)
    await db.refresh(new_product_on_stock)
    await db.refresh(sale)

    if new_product_on_stock.quantity < 10:
        send_stock_alert_email_task.delay(user.email, new_product.name, new_product_on_stock.quantity)
    if old_product_on_stock and old_product_on_stock.quantity < 10 and old_product_on_stock.product_id != new_product_on_stock.product_id:
        old_product = (await db.execute(select(Product).filter(Product.id == old_product_on_stock.product_id))).scalar_one()
        send_stock_alert_email_task.delay(user.email, old_product.name, old_product_on_stock.quantity)

    return RedirectResponse(url="/sales", status_code=303)

@app.get("/sale/delete/{sale_id}", summary="Удаление продажи", description="Удаляет продажу")
async def delete_sale(sale_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result_sale = await db.execute(select(Sale).filter(Sale.id == sale_id, Sale.user_id == user.id))
    sale = result_sale.scalar_one_or_none()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found or you don't have permission")
    result_stock = await db.execute(select(Stock).filter(Stock.product_id == sale.product_id, Stock.user_id == user.id))
    product_on_stock = result_stock.scalar_one_or_none()
    if product_on_stock is None:
        raise HTTPException(status_code=404, detail="Product not found in stock or you don't have permission")
    product_on_stock.quantity += sale.quantity
    await db.delete(sale)
    await db.commit()
    return RedirectResponse(url="/sales", status_code=303)

@app.get("/stocks", summary="Список остатков", description="Отображает список остатков пользователя")
async def get_stocks(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Stock)
        .filter(Stock.user_id == user.id)
        .options(
            joinedload(Stock.product).joinedload(Product.manufacturer),
            joinedload(Stock.product).joinedload(Product.counterparty),
            joinedload(Stock.product).joinedload(Product.agreement),
            joinedload(Stock.product).joinedload(Product.user),
            joinedload(Stock.user)
        )
    )
    stocks = result.scalars().all()
    return templates.TemplateResponse("stocks.html", {"request": request, "stocks": stocks})

@app.get("/stock/create", summary="Форма создания остатка", description="Отображает форму для создания остатка")
async def create_stock(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("create_stock.html", {"request": request, "products": products})

@app.post("/stock/create", summary="Создание остатка", description="Добавляет новый остаток")
async def create_stock_post(
        product_id: int = Form(...),
        quantity: int = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result_product = await db.execute(select(Product).filter(Product.id == product_id, Product.user_id == user.id))
    product = result_product.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or you don't have permission")
    result_stock = await db.execute(select(Stock).filter(Stock.product_id == product_id, Stock.user_id == user.id))
    stock = result_stock.scalar_one_or_none()
    if stock:
        stock.quantity += quantity
    else:
        new_stock = Stock(product_id=product_id, quantity=quantity, user_id=user.id)
        db.add(new_stock)
    await db.commit()
    return RedirectResponse(url="/stocks", status_code=303)

@app.get("/stock/edit/{stock_id}", summary="Форма редактирования остатка", description="Отображает форму редактирования")
async def edit_stock(request: Request, stock_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Stock).filter(Stock.id == stock_id, Stock.user_id == user.id))
    stock = result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found or you don't have permission")
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("edit_stock.html", {"request": request, "stock": stock, "products": products})

@app.post("/stock/edit/{stock_id}", summary="Редактирование остатка", description="Обновляет данные остатка")
async def edit_stock_post(
        stock_id: int,
        product_id: int = Form(...),
        quantity: int = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(select(Stock).filter(Stock.id == stock_id, Stock.user_id == user.id))
    stock = result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found or you don't have permission")
    result_product = await db.execute(select(Product).filter(Product.id == product_id, Product.user_id == user.id))
    product = result_product.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or you don't have permission")
    if stock.product_id != product_id:
        stock.product_id = product_id
    stock.quantity = quantity
    await db.commit()
    return RedirectResponse(url="/stocks", status_code=303)

@app.get("/stock/delete/{stock_id}", summary="Удаление остатка", description="Удаляет остаток")
async def delete_stock(stock_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Stock).filter(Stock.id == stock_id, Stock.user_id == user.id))
    stock = result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found or you don't have permission")
    await db.delete(stock)
    await db.commit()
    return RedirectResponse(url="/stocks", status_code=303)


@app.get("/report", summary="Генерация отчета", description="Создает отчет по продажам и остаткам")
async def generate_report(
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result_sales = await db.execute(
        select(Sale)
        .filter(Sale.user_id == user.id)
        .options(
            joinedload(Sale.product)
        )
    )
    sales = result_sales.scalars().all()

    result_stocks = await db.execute(
        select(Stock)
        .filter(Stock.user_id == user.id)
        .options(
            joinedload(Stock.product)
        )
    )
    stocks = result_stocks.scalars().all()
    total_sales = sum(sale.total_price for sale in sales)
    total_stock = sum(stock.quantity for stock in stocks)
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return templates.TemplateResponse("report.html", {
        "request": request,
        "user": user,
        "sales": sales,
        "stocks": stocks,
        "total_sales": total_sales,
        "total_stock": total_stock,
        "current_date": current_date
    })