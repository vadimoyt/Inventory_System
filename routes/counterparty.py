from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models import Counterparty
from dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("", summary="Список контрагентов")
async def get_counterparty(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
        counterparties = result.scalars().all()
        return templates.TemplateResponse("counterparties.html", {"request": request, "counterparties": counterparties})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/create", summary="Форма создания контрагента")
async def create_counterparty(request: Request):
    try:
        return templates.TemplateResponse("create_counterparty.html", {"request": request})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.post("/create", summary="Создание контрагента")
async def create_counterparty_post(
    request: Request,
    name: str = Form(...),
    address: str = Form(...),
    phone_number: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        new_counterparty = Counterparty(name=name, address=address, phone_number=phone_number, user_id=user.id)
        db.add(new_counterparty)
        await db.commit()
        return RedirectResponse(url="/counterparty", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/edit/{counterparty_id}", summary="Форма редактирования контрагента")
async def edit_counterparty(request: Request, counterparty_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
        counterparty = result.scalar_one_or_none()
        if counterparty is None:
            raise HTTPException(status_code=404, detail="Counterparty not found or you don't have permission")
        return templates.TemplateResponse("edit_counterparty.html", {"request": request, "counterparty": counterparty})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.post("/edit/{counterparty_id}", summary="Редактирование контрагента")
async def edit_counterparty_post(
    request: Request,
    counterparty_id: int,
    name: str = Form(...),
    address: str = Form(...),
    phone_number: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
        counterparty = result.scalar_one_or_none()
        if counterparty is None:
            raise HTTPException(status_code=404, detail="Counterparty not found or you don't have permission")
        counterparty.name = name
        counterparty.address = address
        counterparty.phone_number = phone_number
        await db.commit()
        return RedirectResponse(url="/counterparty", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/delete/{counterparty_id}", summary="Удаление контрагента")
async def delete_counterparty(
    request: Request,
    counterparty_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
        counterparty = result.scalar_one_or_none()
        if counterparty is None:
            raise HTTPException(status_code=404, detail="Counterparty not found or you don't have permission")
        await db.delete(counterparty)
        await db.commit()
        return RedirectResponse(url="/counterparty", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})