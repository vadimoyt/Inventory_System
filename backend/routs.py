from fastapi import FastAPI, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from backend.database import get_db
from backend.models import Manufacturer, Counterparty, Agreement, Product, Sale, Stock, User
import datetime
import os
from fastapi_login import LoginManager
from backend.auth import hash_password, verify_password
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from datetime import timedelta
from jose import jwt, ExpiredSignatureError


app = FastAPI()
templates = Jinja2Templates(directory="templates")

SECRET = os.getenv('SECRET_KEY', 'your-secret-key-here')
manager = LoginManager(SECRET, token_url="/login", use_cookie=True, cookie_name="auth_token")

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

@app.get("/")
async def read_root(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/register")
async def show_register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
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

@app.get("/login")
async def show_login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
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

@app.get("/logout")
async def logout(user: User = Depends(get_current_user)):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("auth_token")
    return response

@app.get("/manufacturer", dependencies=[Depends(get_current_user)])
async def get_manufacturer(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Manufacturer).filter(Manufacturer.user_id == user.id))
    manufacturers = result.scalars().all()
    return templates.TemplateResponse("manufacturers.html", {"request": request, "manufacturers": manufacturers})

@app.get("/manufacturer/create", dependencies=[Depends(get_current_user)])
async def create_manufacturer(request: Request):
    return templates.TemplateResponse("create_manufacturer.html", {"request": request})

@app.post("/manufacturer/create", dependencies=[Depends(get_current_user)])
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

@app.get("/manufacturer/edit/{manufacturer_id}", dependencies=[Depends(get_current_user)])
async def edit_manufacturer(request: Request, manufacturer_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Manufacturer).filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id))
    manufacturer = result.scalar_one_or_none()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found or you don't have permission")
    return templates.TemplateResponse("edit_manufacturer.html", {"request": request, "manufacturer": manufacturer})

@app.post("/manufacturer/edit/{manufacturer_id}", dependencies=[Depends(get_current_user)])
async def edit_manufacturer_post(
    manufacturer_id: int,
    name: str = Form(...),
    address: str = Form(...),
    manager: str = Form(...),
    phone_number: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = await db.execute(select(Manufacturer).filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id))
    manufacturer = result.scalar_one_or_none()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found or you don't have permission")
    manufacturer.name = name
    manufacturer.address = address
    manufacturer.manager = manager
    manufacturer.phone_number = phone_number
    await db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)

@app.get("/manufacturer/delete/{manufacturer_id}", dependencies=[Depends(get_current_user)])
async def delete_manufacturer(manufacturer_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Manufacturer).filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id))
    manufacturer = result.scalar_one_or_none()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found or you don't have permission")
    await db.delete(manufacturer)
    await db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)


@app.get("/counterparty", dependencies=[Depends(get_current_user)])
async def get_counterparty(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
    counterparties = result.scalars().all()
    return templates.TemplateResponse("counterparties.html", {"request": request, "counterparties": counterparties})

@app.get("/counterparty/create", dependencies=[Depends(get_current_user)])
async def create_counterparty(request: Request):
    return templates.TemplateResponse("create_counterparty.html", {"request": request})

@app.post("/counterparty/create", dependencies=[Depends(get_current_user)])
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

@app.get("/counterparty/edit/{counterparty_id}", dependencies=[Depends(get_current_user)])
async def edit_counterparty(request: Request, counterparty_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    counterparty = result.scalar_one_or_none()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found or you don't have permission")
    return templates.TemplateResponse("edit_counterparty.html", {"request": request, "counterparty": counterparty})

@app.post("/counterparty/edit/{counterparty_id}", dependencies=[Depends(get_current_user)])
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

@app.get("/counterparty/delete/{counterparty_id}", dependencies=[Depends(get_current_user)])
async def delete_counterparty(counterparty_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    counterparty = result.scalar_one_or_none()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found or you don't have permission")
    await db.delete(counterparty)
    await db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)

@app.get("/agreement", dependencies=[Depends(get_current_user)])
async def get_agreement(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agreement).filter(Agreement.user_id == user.id))
    agreements = result.scalars().all()
    return templates.TemplateResponse("agreements.html", {"request": request, "agreements": agreements})

@app.get("/agreement/create", dependencies=[Depends(get_current_user)])
async def create_agreement(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
    counterparties = result.scalars().all()
    return templates.TemplateResponse("create_agreement.html", {"request": request, "counterparties": counterparties})


@app.post("/agreement/create", dependencies=[Depends(get_current_user)])
async def create_agreement_post(
        contract_number: str = Form(...),
        date_signed: str = Form(...),
        counterparty_id: int = Form(...),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
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

@app.get("/agreement/edit/{agreement_id}", dependencies=[Depends(get_current_user)])
async def edit_agreement(request: Request, agreement_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
    agreement = result.scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
    result_counterparties = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
    counterparties = result_counterparties.scalars().all()
    return templates.TemplateResponse("edit_agreement.html", {"request": request, "agreement": agreement, "counterparties": counterparties})

@app.post("/agreement/edit/{agreement_id}", dependencies=[Depends(get_current_user)])
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

@app.get("/agreement/delete/{agreement_id}", dependencies=[Depends(get_current_user)])
async def delete_agreement(agreement_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
    agreement = result.scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
    await db.delete(agreement)
    await db.commit()
    return RedirectResponse(url="/agreement", status_code=303)

@app.get("/product", dependencies=[Depends(get_current_user)])
async def get_products(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    print(f"Entering /product for user: {user.id}")
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
    print(f"Found {len(products)} products: {[p.name for p in products]}")
    return templates.TemplateResponse("products.html", {"request": request, "products": products})

@app.get("/product/create", dependencies=[Depends(get_current_user)])
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

@app.post("/product/create", dependencies=[Depends(get_current_user)])
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

@app.get("/product/edit/{product_id}", dependencies=[Depends(get_current_user)])
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

@app.post("/product/edit/{product_id}", dependencies=[Depends(get_current_user)])
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

@app.get("/product/delete/{product_id}", dependencies=[Depends(get_current_user)])
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Product).filter(Product.id == product_id, Product.user_id == user.id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or you don't have permission")
    await db.delete(product)
    await db.commit()
    return RedirectResponse(url="/product", status_code=303)

@app.get("/sales", dependencies=[Depends(get_current_user)])
async def get_sales(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Sale).filter(Sale.user_id == user.id))
    sales = result.scalars().all()
    return templates.TemplateResponse("sales.html", {"request": request, "sales": sales})

@app.get("/sale/create", dependencies=[Depends(get_current_user)])
async def create_sale(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("create_sale.html", {"request": request, "products": products})

@app.post("/sale/create", dependencies=[Depends(get_current_user)])
async def create_sale_post(
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
    product_on_stock = result_stock.scalar_one_or_none()
    if not product_on_stock:
        raise HTTPException(status_code=404, detail="Product not found in stock or you don't have permission")
    if product_on_stock.quantity < quantity:
        raise HTTPException(status_code=400, detail="Not enough stock available")
    total_price = product.price * quantity
    new_sale = Sale(product_id=product_id, quantity=quantity, total_price=total_price, user_id=user.id)
    db.add(new_sale)
    product_on_stock.quantity -= quantity
    await db.commit()
    db.refresh(product_on_stock)
    return RedirectResponse(url="/sales", status_code=303)

@app.get("/sale/edit/{sale_id}", dependencies=[Depends(get_current_user)])
async def edit_sale(request: Request, sale_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Sale).filter(Sale.id == sale_id, Sale.user_id == user.id))
    sale = result.scalar_one_or_none()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found or you don't have permission")
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("edit_sale.html", {"request": request, "sale": sale, "products": products})

@app.post("/sale/edit/{sale_id}", dependencies=[Depends(get_current_user)])
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
        db.refresh(old_product_on_stock)
    db.refresh(new_product_on_stock)
    db.refresh(sale)
    return RedirectResponse(url="/sales", status_code=303)

@app.get("/sale/delete/{sale_id}", dependencies=[Depends(get_current_user)])
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

@app.get("/stocks", dependencies=[Depends(get_current_user)])
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

@app.get("/stock/create", dependencies=[Depends(get_current_user)])
async def create_stock(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("create_stock.html", {"request": request, "products": products})

@app.post("/stock/create", dependencies=[Depends(get_current_user)])
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

@app.get("/stock/edit/{stock_id}", dependencies=[Depends(get_current_user)])
async def edit_stock(request: Request, stock_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Stock).filter(Stock.id == stock_id, Stock.user_id == user.id))
    stock = result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found or you don't have permission")
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("edit_stock.html", {"request": request, "stock": stock, "products": products})

@app.post("/stock/edit/{stock_id}", dependencies=[Depends(get_current_user)])
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

@app.get("/stock/delete/{stock_id}", dependencies=[Depends(get_current_user)])
async def delete_stock(stock_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Stock).filter(Stock.id == stock_id, Stock.user_id == user.id))
    stock = result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found or you don't have permission")
    await db.delete(stock)
    await db.commit()
    return RedirectResponse(url="/stocks", status_code=303)