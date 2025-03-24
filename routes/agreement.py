from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models import Agreement, Counterparty
from dependencies import get_current_user
from pydantic import BaseModel, validator
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

class AgreementCreate(BaseModel):
    contract_number: str
    date_signed: str
    counterparty_id: int

    @validator("date_signed")
    def validate_date(cls, v):
        try:
            return datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

class AgreementUpdate(AgreementCreate):
    pass

@router.get("")
async def get_agreement(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await db.execute(select(Agreement).filter(Agreement.user_id == user.id))
        agreements = result.scalars().all()
        return templates.TemplateResponse("agreements.html", {"request": request, "agreements": agreements})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.get("/create")
async def create_agreement(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
        counterparties = result.scalars().all()
        return templates.TemplateResponse("create_agreement.html", {"request": request, "counterparties": counterparties})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.post("/create")
async def create_agreement_post(
    contract_number: str = Form(...),
    date_signed: str = Form(...),
    counterparty_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        agreement_data = AgreementCreate(contract_number=contract_number, date_signed=date_signed, counterparty_id=counterparty_id)
        result = await db.execute(select(Counterparty).filter(Counterparty.id == agreement_data.counterparty_id, Counterparty.user_id == user.id))
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="You don't have permission to use this counterparty")
        new_agreement = Agreement(
            contract_number=agreement_data.contract_number,
            date_signed=agreement_data.date_signed,
            counterparty_id=agreement_data.counterparty_id,
            user_id=user.id
        )
        db.add(new_agreement)
        await db.commit()
        return RedirectResponse(url="/agreement", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": Request, "error": str(e)})

@router.get("/edit/{agreement_id}")
async def edit_agreement(request: Request, agreement_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
        agreement = result.scalar_one_or_none()
        if agreement is None:
            raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
        result_counterparties = await db.execute(select(Counterparty).filter(Counterparty.user_id == user.id))
        counterparties = result_counterparties.scalars().all()
        return templates.TemplateResponse("edit_agreement.html", {"request": request, "agreement": agreement, "counterparties": counterparties})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@router.post("/edit/{agreement_id}")
async def edit_agreement_post(
    agreement_id: int,
    contract_number: str = Form(...),
    date_signed: str = Form(...),
    counterparty_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        agreement_data = AgreementUpdate(contract_number=contract_number, date_signed=date_signed, counterparty_id=counterparty_id)
        result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
        agreement = result.scalar_one_or_none()
        if agreement is None:
            raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
        result = await db.execute(select(Counterparty).filter(Counterparty.id == agreement_data.counterparty_id, Counterparty.user_id == user.id))
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="You don't have permission to use this counterparty")
        agreement.contract_number = agreement_data.contract_number
        agreement.date_signed = agreement_data.date_signed
        agreement.counterparty_id = agreement_data.counterparty_id
        await db.commit()
        return RedirectResponse(url="/agreement", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": Request, "error": str(e)})

@router.get("/delete/{agreement_id}")
async def delete_agreement(agreement_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result = await db.execute(select(Agreement).filter(Agreement.id == agreement_id, Agreement.user_id == user.id))
        agreement = result.scalar_one_or_none()
        if agreement is None:
            raise HTTPException(status_code=404, detail="Agreement not found or you don't have permission")
        await db.delete(agreement)
        await db.commit()
        return RedirectResponse(url="/agreement", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": Request, "error": str(e)})