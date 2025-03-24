from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models import Sale, Product, Stock
from dependencies import get_current_user
from tasks import send_stock_alert_email_task
from config import logger
import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("", summary="Список продаж")
async def get_sales(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await db.execute(select(Sale).filter(Sale.user_id == user.id))
        sales = result.scalars().all()
        return templates.TemplateResponse("sales.html", {"request": request, "sales": sales})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/create", summary="Форма создания продажи")
async def create_sale(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
        return templates.TemplateResponse("create_sale.html", {"request": request, "products": products})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.post("/create", summary="Создание продажи")
async def create_sale_post(
    request: Request,
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
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
        new_sale = Sale(product_id=product_id, quantity=quantity, total_price=total_price, user_id=user.id, date_sold=datetime.datetime.utcnow())
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
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/edit/{sale_id}", summary="Форма редактирования продажи")
async def edit_sale(request: Request, sale_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await db.execute(select(Sale).filter(Sale.id == sale_id, Sale.user_id == user.id))
        sale = result.scalar_one_or_none()
        if sale is None:
            raise HTTPException(status_code=404, detail="Sale not found or you don't have permission")
        products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
        return templates.TemplateResponse("edit_sale.html", {"request": request, "sale": sale, "products": products})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.post("/edit/{sale_id}", summary="Редактирование продажи")
async def edit_sale_post(
    request: Request,
    sale_id: int,
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
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
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/delete/{sale_id}", summary="Удаление продажи")
async def delete_sale(
    request: Request,
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
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
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})