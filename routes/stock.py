from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from backend.database import get_db
from backend.models import Stock, Product
from dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("", summary="Список остатков")
async def get_stocks(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
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

@router.get("/create", summary="Форма создания остатка")
async def create_stock(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("create_stock.html", {"request": request, "products": products})

@router.post("/create", summary="Создание остатка")
async def create_stock_post(
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
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

@router.get("/edit/{stock_id}", summary="Форма редактирования остатка")
async def edit_stock(request: Request, stock_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Stock).filter(Stock.id == stock_id, Stock.user_id == user.id))
    stock = result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found or you don't have permission")
    products = (await db.execute(select(Product).filter(Product.user_id == user.id))).scalars().all()
    return templates.TemplateResponse("edit_stock.html", {"request": request, "stock": stock, "products": products})

@router.post("/edit/{stock_id}", summary="Редактирование остатка")
async def edit_stock_post(
    stock_id: int,
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
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

@router.get("/delete/{stock_id}", summary="Удаление остатка")
async def delete_stock(stock_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Stock).filter(Stock.id == stock_id, Stock.user_id == user.id))
    stock = result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found or you don't have permission")
    await db.delete(stock)
    await db.commit()
    return RedirectResponse(url="/stocks", status_code=303)