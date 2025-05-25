from datetime import datetime

import jwt
import pytz
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.config import settings
from app.models.auth import TokenData
from app.pkg.hasher import Hasher
from app.repositories.user import UserRepo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")


async def authenticate(login: str, password: str):
    db_user = await UserRepo.select_user(login=login)
    check_verify = Hasher.verify_password(password, db_user.password)
    if check_verify:
        return db_user
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    access_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token type, expected access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.hasher.hash_key, algorithms=[settings.hasher.algorithm])

        expiration_date: str = payload.get("expire", {})
        if expiration_date is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нет срока жизни(")
        expiration_date = datetime.fromisoformat(expiration_date)
        if expiration_date < datetime.now(tz=pytz.timezone('Europe/Moscow')):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Время жизни токена истекло")

        token_type: str = payload.get("type")
        if token_type != 'access':
            raise access_exception
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
        token_data = TokenData(uuid=user_id)
    except jwt.PyJWTError:
        raise credentials_exception
    user = await UserRepo.select_user(user_id=token_data.uuid)
    if not user:
        raise credentials_exception
    return user


async def refresh_account_token(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    refresh_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token type, expected refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.hasher.hash_key, algorithms=[settings.hasher.algorithm])

        expiration_date: str = payload.get("expire", {})
        if expiration_date is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нет срока жизни(")
        expiration_date = datetime.fromisoformat(expiration_date)
        if expiration_date < datetime.now(tz=pytz.timezone('Europe/Moscow')):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Время жизни токена истекло")
        token_type: str = payload.get("type")
        if token_type != 'refresh':
            raise refresh_exception
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
        token_data = TokenData(uuid=user_id)
    except jwt.PyJWTError:
        raise credentials_exception
    user = await UserRepo.select_account(uuid=token_data.uuid)
    if not user:
        raise credentials_exception
    return user
