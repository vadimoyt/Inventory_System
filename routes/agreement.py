from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models import Agreement, Counterparty
from dependencies import get_current_user
import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("", summary="Список соглашений")
async def get_agreement(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Agreement).filter(Agreement.user_id == user.id))
    agreements = result.scalars().all()
    return templates.TemplateResponse("agreements.html", {"request": request, "agreements": agreements})

@router.get("/create", summary="Форма создания соглашения")
async def create_agreement(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
    counterparties = result.scalars().all()
    return templates.TemplateResponse("create_agreement.html", {"request": request, "counterparties": counterparties})

@router.post("/create", summary="Создание соглашения")
async def create_agreement_post(
    contract_number: str = Form(...),
    date_signed: str = Form(...),
    counterparty_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    result = await db.execute(select(Counterparty).filter(Counterparty.id == counterparty_id, Counterparty.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="You don't have permission to use this counterparty")
    try:
        date_signed_dt = datetime.datetime.strptime(date_signed, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    new_agreement = Agreement(contract_number=contract_number, date_signed=date_signed_dt, counterparty_id=counterparty_id, user_id=user.id)
    db.add(new_agreement)
    await db.commit()
    return RedirectResponse(url="/agreement", status_code=303)

@router.get("/edit/{agreement_id}", summary="Форма редактирования соглашения")
async def edit_agreement(request: Request, agreement_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
    agreement = result.scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
    result_counterparties = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
    counterparties = result_counterparties.scalars().all()
    return templates.TemplateResponse("edit_agreement.html", {"request": request, "agreement": agreement, "counterparties": counterparties})

@router.post("/edit/{agreement_id}", summary="Редактирование соглашения")
async def edit_agreement_post(
    agreement_id: int,
    contract_number: str = Form(...),
    date_signed: str = Form(...),
    counterparty_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
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

@router.get("/delete/{agreement_id}", summary="Удаление соглашения")
async def delete_agreement(agreement_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
    agreement = result.scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
    await db.delete(agreement)
    await db.commit()
    return RedirectResponse(url="/agreement", status_code=303)