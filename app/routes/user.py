import random  # Не используется
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse  # Не используется напрямую в этих роутах
from fastapi.security import OAuth2PasswordRequestForm  # Не используется в этих роутах
from starlette.status import (HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED,  # Не используются напрямую
                              HTTP_403_FORBIDDEN, HTTP_201_CREATED)  # Добавлен HTTP_201_CREATED

from app.depends import UserServiceDependency
# from app.models.auth import AuthForm, Token, TokenData # Не используются в этих роутах
from app.models.user import (AccessLevel, User, UserCreate, UserDelete,
                             UserLogin, UserResponse, UserUpdate)  # AccessLevel, UserLogin не используются
from app.pkg.auth import get_current_user  # authenticate, refresh_account_token не используются
# from app.pkg.hasher import Hasher # Не используется в этих роутах

router = APIRouter(
    prefix='/api/v1/user',
    tags=['user'],
    dependencies=[Depends(get_current_user)]  # Все роуты требуют пользователя
)


@router.post("/create", response_model=UserResponse, status_code=HTTP_201_CREATED)
async def create_user(
    user_service: UserServiceDependency,
    user_data: UserCreate,
    current_user: User = Depends(get_current_user)
):
    return await user_service.create_user(user_data, current_user)


@router.post("/update", response_model=UserResponse)  # Можно path("/update/{user_id_to_update}")
async def update_user(
    user_service: UserServiceDependency,
    user_data: UserUpdate,  # user_id передается в теле
    current_user: User = Depends(get_current_user)
):
    return await user_service.update_user(user_data, current_user)


@router.post("/delete")  # Можно path("/delete/{user_id_to_delete}")
async def delete_user(
    user_service: UserServiceDependency,
    user_data: UserDelete,  # user_id передается в теле
    current_user: User = Depends(get_current_user)
):
    # service.delete_user возвращает {"message": "..."} или кидает исключение
    return await user_service.delete_user(user_data, current_user)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user)
):
    # FastAPI автоматически преобразует User в UserResponse, если поля совпадают
    # или если UserResponse.model_validate(current_user) отработает
    # Для явности можно сделать так:
    return UserResponse.model_validate(current_user)


@router.get("/select", response_model=List[UserResponse])
async def select_all_users(
    user_service: UserServiceDependency,
    current_user: User = Depends(get_current_user)
):
    return await user_service.select_all_users(current_user)


@router.get("/select/{user_id_to_view}", response_model=UserResponse)  # Новый роут
async def select_user_by_id(
    user_id_to_view: UUID,
    user_service: UserServiceDependency,
    current_user: User = Depends(get_current_user)  # Для проверки прав, кто может смотреть какого юзера
):
    # В UserService нужно будет добавить метод select_one_user(user_id_to_view, current_user)
    # который проверит права current_user на просмотр user_id_to_view
    # и вернет UserResponse
    # Пока заглушка:
    await user_service.user_repo.min_admin_access_level(current_user)  # Пример: только админ смотрит по ID
    user_internal = await user_service.user_repo.select_user(user_id=user_id_to_view)
    return UserResponse.model_validate(user_internal)
