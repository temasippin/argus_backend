import random

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from starlette.status import (HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED,
                              HTTP_403_FORBIDDEN)

from app.depends import UserServiceDependency
from app.models.auth import AuthForm, Token, TokenData
from app.models.user import (AccessLevel, User, UserCreate, UserDelete,
                             UserLogin, UserUpdate)
from app.pkg.auth import authenticate, get_current_user, refresh_account_token
from app.pkg.hasher import Hasher

router = APIRouter(
    prefix='/api/v1/auth',
    tags=['auth']
)


@router.post('/login', response_model=Token, tags=['auth'])
async def login(
    user_service: UserServiceDependency,
    user_data: UserLogin
):
    uuid = await user_service.login(user_data)
    access_token = Hasher.create_access_token(data={"sub": str(uuid), 'type': 'access'})
    refresh_token = Hasher.create_refresh_token(data={"sub": str(uuid), 'type': 'refresh'})
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/token", response_model=Token, tags=['auth'])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = await authenticate(form_data.username, form_data.password)
    access_token = Hasher.create_access_token(data={"sub": str(user.user_id), 'type': 'access'})
    refresh_token = Hasher.create_refresh_token(data={"sub": str(user.user_id), 'type': 'refresh'})
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.get("/token/refresh", response_model=Token, tags=['auth'])
async def refresh_token(
    current_user: Token = Depends(refresh_account_token)
):
    if current_user:
        access_token = Hasher.create_access_token(data={"sub": str(current_user.user_id), 'type': 'access'})
        refresh_token = Hasher.create_refresh_token(data={"sub": str(current_user.user_id), 'type': 'refresh'})
        return Token(access_token=access_token, refresh_token=refresh_token)
