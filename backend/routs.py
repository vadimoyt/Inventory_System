from fastapi import FastAPI, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from backend.auth import hash_password
from backend.database import get_db
from backend.models import Manufacturer, Counterparty, Agreement, Product, Sale, Stock, User

app = FastAPI()

templates = Jinja2Templates(directory="templates")


@app.get("/manufacturer")
async def get_manufacturer(request: Request, db: Session = Depends(get_db)):
    manufacturers = db.query(Manufacturer).all()
    return templates.TemplateResponse("manufacturers.html", {"request": request, "manufacturers": manufacturers})


@app.get("/manufacturer/create")
async def create_manufacturer(request: Request):
    return templates.TemplateResponse("create_manufacturer.html", {"request": request})


@app.post("/manufacturer/create")
async def create_manufacturer_post(name: str = Form(...),
                                   address: str = Form(...),
                                   manager: str = Form(...),
                                   phone_number: str = Form(...),
                                   db: Session = Depends(get_db)):
    new_manufacturer = Manufacturer(
        name=name, address=address, manager=manager, phone_number=phone_number
    )
    db.add(new_manufacturer)
    db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)


@app.get("/manufacturer/edit/{manufacturer_id}")
async def edit_manufacturer(request: Request, manufacturer_id: int, db: Session = Depends(get_db)):
    manufacturer = db.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).first()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found")
    return templates.TemplateResponse("edit_manufacturer.html", {"request": request, "manufacturer": manufacturer})


@app.post("/manufacturer/edit/{manufacturer_id}")
async def edit_manufacturer_post(manufacturer_id: int, name: str = Form(...), address: str = Form(...),
                                 manager: str = Form(...), phone_number: str = Form(...),
                                 db: Session = Depends(get_db)):
    manufacturer = db.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).first()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found")

    manufacturer.name = name
    manufacturer.address = address
    manufacturer.manager = manager
    manufacturer.phone_number = phone_number
    db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)


@app.get("/manufacturer/delete/{manufacturer_id}")
async def delete_manufacturer(manufacturer_id: int, db: Session = Depends(get_db)):
    manufacturer = db.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).first()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found")

    db.delete(manufacturer)
    db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)


@app.get("/counterparty")
async def get_counterparty(request: Request, db: Session = Depends(get_db)):
    counterparties = db.query(Counterparty).all()
    return templates.TemplateResponse("counterparties.html", {"request": request, "counterparties": counterparties})


@app.get("/counterparty/create")
async def create_counterparty(request: Request):
    return templates.TemplateResponse("create_counterparty.html", {"request": request})


@app.post("/counterparty/create")
async def create_counterparty_post(name: str = Form(...),
                                   address: str = Form(...),
                                   phone_number: str = Form(...),
                                   db: Session = Depends(get_db)):
    new_counterparty = Counterparty(
        name=name, address=address, phone_number=phone_number
    )
    db.add(new_counterparty)
    db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)


@app.get("/counterparty/edit/{counterparty_id}")
async def edit_counterparty(request: Request, counterparty_id: int, db: Session = Depends(get_db)):
    counterparty = db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    return templates.TemplateResponse("edit_counterparty.html", {"request": request, "counterparty": counterparty})


@app.post("/counterparty/edit/{counterparty_id}")
async def edit_counterparty_post(counterparty_id: int, name: str = Form(...), address: str = Form(...),
                                  phone_number: str = Form(...), db: Session = Depends(get_db)):
    counterparty = db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    counterparty.name = name
    counterparty.address = address
    counterparty.phone_number = phone_number
    db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)


@app.get("/counterparty/delete/{counterparty_id}")
async def delete_counterparty(counterparty_id: int, db: Session = Depends(get_db)):
    counterparty = db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    db.delete(counterparty)
    db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)


@app.get("/agreement")
async def get_agreement(request: Request, db: Session = Depends(get_db)):
    agreements = db.query(Agreement).all()
    return templates.TemplateResponse("agreements.html", {"request": request, "agreements": agreements})


@app.get("/agreement/create")
async def create_agreement(request: Request, db: Session = Depends(get_db)):
    counterparties = db.query(Counterparty).all()
    return templates.TemplateResponse("create_agreement.html", {"request": request, "counterparties": counterparties})


@app.post("/agreement/create")
async def create_agreement_post(contract_number: str = Form(...),
                                date_signed: str = Form(...),
                                counterparty_id: int = Form(...),
                                db: Session = Depends(get_db)):
    new_agreement = Agreement(
        contract_number=contract_number,
        date_signed=date_signed,
        counterparty_id=counterparty_id
    )
    db.add(new_agreement)
    db.commit()
    return RedirectResponse(url="/agreement", status_code=303)


@app.get("/agreement/edit/{agreement_id}")
async def edit_agreement(request: Request, agreement_id: int, db: Session = Depends(get_db)):
    agreement = db.query(Agreement).filter(Agreement.id == agreement_id).first()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    counterparties = db.query(Counterparty).all()
    return templates.TemplateResponse("edit_agreement.html", {"request": request, "agreement": agreement, "counterparties": counterparties})


@app.post("/agreement/edit/{agreement_id}")
async def edit_agreement_post(agreement_id: int, contract_number: str = Form(...),
                               date_signed: str = Form(...), counterparty_id: int = Form(...),
                               db: Session = Depends(get_db)):
    agreement = db.query(Agreement).filter(Agreement.id == agreement_id).first()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found")

    agreement.contract_number = contract_number
    agreement.date_signed = date_signed
    agreement.counterparty_id = counterparty_id
    db.commit()
    return RedirectResponse(url="/agreement", status_code=303)


@app.get("/agreement/delete/{agreement_id}")
async def delete_agreement(agreement_id: int, db: Session = Depends(get_db)):
    agreement = db.query(Agreement).filter(Agreement.id == agreement_id).first()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found")

    db.delete(agreement)
    db.commit()
    return RedirectResponse(url="/agreement", status_code=303)


@app.get("/product")
async def get_products(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return templates.TemplateResponse("products.html", {"request": request, "products": products})


@app.get("/product/create")
async def create_product(request: Request, db: Session = Depends(get_db)):
    manufacturers = db.query(Manufacturer).all()
    counterparties = db.query(Counterparty).all()
    agreements = db.query(Agreement).all()
    return templates.TemplateResponse("create_product.html", {
        "request": request,
        "manufacturers": manufacturers,
        "counterparties": counterparties,
        "agreements": agreements
    })


@app.post("/product/create")
async def create_product_post(
    name: str = Form(...),
    price: float = Form(...),
    manufacturer_id: int = Form(...),
    counterparty_id: int = Form(...),
    agreement_id: int = Form(...),
    db: Session = Depends(get_db)
):
    new_product = Product(
        name=name,
        price=price,
        manufacturer_id=manufacturer_id,
        counterparty_id=counterparty_id,
        agreement_id=agreement_id
    )
    db.add(new_product)
    db.commit()
    return RedirectResponse(url="/product", status_code=303)


@app.get("/product/edit/{product_id}")
async def edit_product(request: Request, product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    manufacturers = db.query(Manufacturer).all()
    counterparties = db.query(Counterparty).all()
    agreements = db.query(Agreement).all()

    return templates.TemplateResponse("edit_product.html", {
        "request": request,
        "product": product,
        "manufacturers": manufacturers,
        "counterparties": counterparties,
        "agreements": agreements
    })


@app.post("/product/edit/{product_id}")
async def edit_product_post(
    product_id: int,
    name: str = Form(...),
    price: float = Form(...),
    manufacturer_id: int = Form(...),
    counterparty_id: int = Form(...),
    agreement_id: int = Form(...),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    product.name = name
    product.price = price
    product.manufacturer_id = manufacturer_id
    product.counterparty_id = counterparty_id
    product.agreement_id = agreement_id
    db.commit()
    return RedirectResponse(url="/product", status_code=303)


@app.get("/product/delete/{product_id}")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    db.delete(product)
    db.commit()
    return RedirectResponse(url="/product", status_code=303)


@app.get("/sales")
async def get_sales(request: Request, db: Session = Depends(get_db)):
    sales = db.query(Sale).all()
    return templates.TemplateResponse("sales.html", {"request": request, "sales": sales})


@app.get("/sale/create")
async def create_sale(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return templates.TemplateResponse("create_sale.html", {"request": request, "products": products})


@app.post("/sale/create")
async def create_sale_post(product_id: int = Form(...), quantity: int = Form(...), db: Session = Depends(get_db)):
    product_on_stock = db.query(Stock).filter(Stock.product_id == product_id).first()
    if not product_on_stock:
        raise HTTPException(status_code=404, detail="Product not found in stock")
    if product_on_stock.quantity < quantity:
        raise HTTPException(status_code=400, detail="Not enough stock available")
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    total_price = product.price * quantity
    new_sale = Sale(product_id=product_id, quantity=quantity, total_price=total_price)
    product_on_stock.quantity -= quantity
    db.add(new_sale)
    db.commit()
    db.refresh(product_on_stock)
    return RedirectResponse(url="/sales", status_code=303)


@app.get("/sale/edit/{sale_id}")
async def edit_sale(request: Request, sale_id: int, db: Session = Depends(get_db)):
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    products = db.query(Product).all()
    return templates.TemplateResponse("edit_sale.html", {"request": request, "sale": sale, "products": products})


@app.post("/sale/edit/{sale_id}")
async def edit_sale_post(sale_id: int, product_id: int = Form(...), quantity: int = Form(...),
                         db: Session = Depends(get_db)):
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    old_product_on_stock = db.query(Stock).filter(Stock.product_id == sale.product_id).first()
    new_product_on_stock = db.query(Stock).filter(Stock.product_id == product_id).first()
    if not new_product_on_stock:
        raise HTTPException(status_code=404, detail="New product not found in stock")
    quantity_difference = quantity - sale.quantity
    if quantity_difference > 0 and new_product_on_stock.quantity < quantity_difference:
        raise HTTPException(status_code=400, detail="Not enough stock available for new product")
    old_product_on_stock.quantity += sale.quantity
    if quantity_difference > 0:
        new_product_on_stock.quantity -= quantity_difference
    if quantity_difference < 0:
        old_product_on_stock.quantity += abs(quantity_difference)
    new_product = db.query(Product).filter(Product.id == product_id).first()
    total_price = new_product.price * quantity
    sale.product_id = product_id
    sale.quantity = quantity
    sale.total_price = total_price
    db.commit()
    db.refresh(old_product_on_stock)
    db.refresh(new_product_on_stock)
    db.refresh(sale)
    return RedirectResponse(url="/sales", status_code=303)


@app.get("/sale/delete/{sale_id}")
async def delete_sale(sale_id: int, db: Session = Depends(get_db)):
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    product_on_stock = db.query(Stock).filter(Stock.product_id == sale.product_id).first()
    if product_on_stock is None:
        raise HTTPException(status_code=404, detail="Product not found in stock")
    product_on_stock.quantity += sale.quantity
    db.delete(sale)
    db.commit()
    return RedirectResponse(url="/sales", status_code=303)


@app.get("/stocks")
async def get_stocks(request: Request, db: Session = Depends(get_db)):
    stocks = db.query(Stock).all()
    return templates.TemplateResponse("stocks.html", {"request": request, "stocks": stocks})


@app.get("/stock/create")
async def create_stock(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return templates.TemplateResponse("create_stock.html", {"request": request, "products": products})


@app.post("/stock/create")
async def create_stock_post(
        product_id: int = Form(...),
        quantity: int = Form(...),
        db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    stock = db.query(Stock).filter(Stock.product_id == product_id).first()
    if stock:
        stock.quantity += quantity
    else:
        new_stock = Stock(product_id=product_id, quantity=quantity)
        db.add(new_stock)
    db.commit()
    return RedirectResponse(url="/stocks", status_code=303)


@app.get("/stock/edit/{stock_id}")
async def edit_stock(request: Request, stock_id: int, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if stock is None:
        raise HTTPException(status_code=404, detail="Товар на складе не найден")
    products = db.query(Product).all()
    return templates.TemplateResponse("edit_stock.html", {"request": request, "stock": stock, "products": products})


@app.post("/stock/edit/{stock_id}")
async def edit_stock_post(stock_id: int, product_id: int = Form(...), quantity: int = Form(...),
                          db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if stock is None:
        raise HTTPException(status_code=404, detail="Товар на складе не найден")
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    stock.product_id = product_id
    stock.quantity = quantity
    db.commit()
    return RedirectResponse(url="/stocks", status_code=303)


@app.get("/stock/delete/{stock_id}")
async def delete_stock(stock_id: int, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if stock is None:
        raise HTTPException(status_code=404, detail="Товар на складе не найден")
    db.delete(stock)
    db.commit()
    return RedirectResponse(url="/stocks", status_code=303)



@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

@app.get("/register")
def show_register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password)
    )
    db.add(new_user)
    db.commit()

    # Перенаправляем пользователя на страницу со списком всех пользователей
    return RedirectResponse(url="/", status_code=303)

