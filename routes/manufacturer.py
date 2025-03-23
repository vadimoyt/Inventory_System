from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models import Manufacturer
from dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("", summary="Список производителей")
async def get_manufacturer(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Manufacturer).filter(Manufacturer.user_id == user.id))
    manufacturers = result.scalars().all()
    return templates.TemplateResponse("manufacturers.html", {"request": request, "manufacturers": manufacturers})

@router.get("/create", summary="Форма создания производителя")
async def create_manufacturer(request: Request):
    return templates.TemplateResponse("create_manufacturer.html", {"request": request})

@router.post("/create", summary="Создание производителя")
async def create_manufacturer_post(
    name: str = Form(...),
    address: str = Form(...),
    manager: str = Form(...),
    phone_number: str = Form(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_manufacturer = Manufacturer(name=name, address=address, manager=manager, phone_number=phone_number, user_id=user.id)
    db.add(new_manufacturer)
    await db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)

@router.get("/edit/{manufacturer_id}", summary="Форма редактирования производителя")
async def edit_manufacturer(
    request: Request,
    manufacturer_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    result = await db.execute(
        select(Manufacturer).filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id)
    )
    manufacturer = result.scalar_one_or_none()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found or you don't have permission")
    return templates.TemplateResponse("edit_manufacturer.html", {"request": request, "manufacturer": manufacturer})

@router.post("/edit/{manufacturer_id}", summary="Редактирование производителя")
async def edit_manufacturer_post(
    manufacturer_id: int,
    name: str = Form(...),
    address: str = Form(...),
    manager: str = Form(...),
    phone_number: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    result = await db.execute(
        select(Manufacturer).filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id)
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

@router.get("/delete/{manufacturer_id}", summary="Удаление производителя")
async def delete_manufacturer(
    manufacturer_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    result = await db.execute(
        select(Manufacturer).filter(Manufacturer.id == manufacturer_id, Manufacturer.user_id == user.id)
    )
    manufacturer = result.scalar_one_or_none()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found or you don't have permission")
    await db.delete(manufacturer)
    await db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)