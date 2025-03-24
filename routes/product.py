from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from backend.database import get_db
from backend.models import Product, Manufacturer, Counterparty, Agreement
from dependencies import get_current_user
from typing import List
from pydantic import BaseModel

router = APIRouter()
templates = Jinja2Templates(directory="templates")

class ProductResponse(BaseModel):
    id: int
    name: str
    price: float

@router.get("", summary="Список продуктов")
async def get_products(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
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
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/api/products", response_model=List[ProductResponse], summary="Получить список продуктов (API)")
async def get_products_api(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await db.execute(select(Product).filter(Product.user_id == user.id))
        products = result.scalars().all()
        return [{"id": p.id, "name": p.name, "price": p.price} for p in products]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # API endpoint keeps HTTP exception

@router.get("/create", summary="Форма создания продукта")
async def create_product(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        manufacturers = (await db.execute(select(Manufacturer).filter(Manufacturer.user_id == user.id))).scalars().all()
        counterparties = (await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))).scalars().all()
        agreements = (await db.execute(select(Agreement).filter(Agreement.user_id == user.id))).scalars().all()
        return templates.TemplateResponse("create_product.html", {
            "request": request,
            "manufacturers": manufacturers,
            "counterparties": counterparties,
            "agreements": agreements
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.post("/create", summary="Создание продукта")
async def create_product_post(
    request: Request,
    name: str = Form(...),
    price: float = Form(...),
    manufacturer_id: int = Form(...),
    counterparty_id: int = Form(...),
    agreement_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
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
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/edit/{product_id}", summary="Форма редактирования продукта")
async def edit_product(request: Request, product_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
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
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.post("/edit/{product_id}", summary="Редактирование продукта")
async def edit_product_post(
    request: Request,
    product_id: int,
    name: str = Form(...),
    price: float = Form(...),
    manufacturer_id: int = Form(...),
    counterparty_id: int = Form(...),
    agreement_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
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
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/delete/{product_id}", summary="Удаление продукта")
async def delete_product(
    request: Request,
    product_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        result = await db.execute(select(Product).filter(Product.id == product_id, Product.user_id == user.id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found or you don't have permission")
        await db.delete(product)
        await db.commit()
        return RedirectResponse(url="/product", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})