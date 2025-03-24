from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models import User
from dependencies import get_current_user, manager
from dependencies import hash_password, verify_password
from datetime import timedelta

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/register", summary="Форма регистрации")
async def show_register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register", summary="Регистрация пользователя")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    result = await db.execute(select(User).filter(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")
    new_user = User(username=username, email=email, hashed_password=hash_password(password))
    db.add(new_user)
    await db.commit()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/login", summary="Форма входа")
async def show_login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", summary="Вход в систему")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        response = RedirectResponse(url="/login?error=1", status_code=303)
        return response
    access_token = manager.create_access_token(data={"sub": user.username}, expires=timedelta(hours=1))
    response = RedirectResponse(url="/", status_code=303)
    manager.set_cookie(response, access_token)
    return response

@router.get("/logout", summary="Выход из системы")
async def logout(user: User = Depends(get_current_user)):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("auth_token")
    return response