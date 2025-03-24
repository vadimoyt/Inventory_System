from fastapi import FastAPI, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from backend import auth
from routes import agreement, counterparty, manufacturer, product, report, stock, sale
from dependencies import get_current_user

app = FastAPI(
    title="Stock Management System",
    description="A system for managing products, sales, and stock with email notifications.",
    version="1.0.0"
)
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router, prefix="")
app.include_router(manufacturer.router, prefix="/manufacturer")
app.include_router(counterparty.router, prefix="/counterparty")
app.include_router(agreement.router, prefix="/agreement")
app.include_router(product.router, prefix="/product")
app.include_router(sale.router, prefix="/sales")
app.include_router(stock.router, prefix="/stocks")
app.include_router(report.router, prefix="/report")

@app.get("/", summary="Главная страница", description="Отображает главную страницу для авторизованного пользователя")
async def read_root(request: Request, user=Depends(get_current_user)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})