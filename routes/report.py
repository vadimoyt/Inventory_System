from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from backend.database import get_db
from backend.models import Sale, Stock
from dependencies import get_current_user
import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("", summary="Генерация отчета")
async def generate_report(request: Request, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        result_sales = await db.execute(
            select(Sale)
            .filter(Sale.user_id == user.id)
            .options(joinedload(Sale.product))
        )
        sales = result_sales.scalars().all()
        result_stocks = await db.execute(
            select(Stock)
            .filter(Stock.user_id == user.id)
            .options(joinedload(Stock.product))
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
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})