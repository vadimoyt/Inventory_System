from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from fastapi_login import LoginManager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models import User
from config import SECRET, logger
from passlib.context import CryptContext  # Add this for hashing
from datetime import timedelta
from jose import jwt, ExpiredSignatureError


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

manager = LoginManager(SECRET, token_url="/login", use_cookie=True, cookie_name="auth_token")

@manager.user_loader()
async def load_user(username: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalar_one_or_none()
    return user

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("auth_token")
    if not token:
        return RedirectResponse(url="/login", status_code=303)
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        username = payload.get("sub")
        if not username:
            return RedirectResponse(url="/login", status_code=303)
        user = await load_user(username, db)
        if user is None:
            return RedirectResponse(url="/login", status_code=303)
        return user
    except ExpiredSignatureError:
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("auth_token")
        return response
    except Exception as e:
        return RedirectResponse(url="/login", status_code=303)