from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db
from app.db.models import User
from app.services.token_blacklist import revoke_token, token_is_revoked

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserCreate(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int


SECRET_KEY = settings.jwt_secret
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expires_minutes
token_auth_scheme = HTTPBearer()


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    import datetime

    to_encode = data.copy()
    to_encode.update({"jti": uuid4().hex})
    expire = datetime.datetime.utcnow() + (
        expires_delta or datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(token_auth_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        jti = payload.get("jti")
        if subject is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        if jti and await token_is_revoked(jti):
            raise HTTPException(status_code=401, detail="Token revoked")
    except JWTError as err:
        raise HTTPException(status_code=401, detail="Invalid token") from err

    result = await db.execute(select(User).where(User.email == subject))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


@router.post("/signup")
async def signup(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.username))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    db_user = User(
        email=user.username,
        hashed_password=pwd_context.hash(user.password),
        is_active=True,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return {"msg": "User created successfully", "user_id": db_user.id}


@router.post("/login", response_model=Token)
async def login(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.username))
    db_user = result.scalar_one_or_none()
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "user_id": db_user.id}


class ProfileUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    current_password: str


@router.get("/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "is_active": current_user.is_active}


@router.put("/me")
async def update_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not pwd_context.verify(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if payload.email:
        current_user.email = payload.email
    if payload.password:
        current_user.hashed_password = pwd_context.hash(payload.password)
    await db.commit()
    return {"msg": "Profile updated"}


@router.post("/signout")
async def signout(
    credentials: HTTPAuthorizationCredentials = Depends(token_auth_scheme),
):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            raise HTTPException(status_code=400, detail="Invalid token")
    except JWTError as err:
        raise HTTPException(status_code=401, detail="Invalid token") from err
    await revoke_token(jti, exp)
    return {"msg": "Signed out"}
