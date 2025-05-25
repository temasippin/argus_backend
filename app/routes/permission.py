from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.depends import PermissionServiceDependency
from app.models.user import User
from app.models.permission import (
    PermissionCreate, PermissionResponse, PermissionUpdate, PermissionDelete
)
from app.pkg.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/permission",
    tags=["permission"],
    dependencies=[Depends(get_current_user)]  # Все роуты требуют аутентификации
)


@router.post("/grant", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def grant_permission(
    data: PermissionCreate,
    service: PermissionServiceDependency,
    current_user: User = Depends(get_current_user)
):
    """Выдать право доступа пользователю к устройству или зоне."""
    return await service.create_permission(data, current_user)


@router.get("/get/{permission_id}", response_model=PermissionResponse)
async def get_permission_by_id(
    permission_id: UUID,
    service: PermissionServiceDependency,
    current_user: User = Depends(get_current_user)
):
    """Получить информацию о конкретном праве доступа."""
    return await service.get_permission(permission_id, current_user)


@router.get("/user/{user_id_to_view}", response_model=List[PermissionResponse])
async def get_permissions_for_user_route(  # Изменено имя функции
    user_id_to_view: UUID,
    service: PermissionServiceDependency,
    current_user: User = Depends(get_current_user)
):
    """Получить все права доступа для указанного пользователя."""
    return await service.get_permissions_for_user(user_id_to_view, current_user)


@router.get("/all", response_model=List[PermissionResponse])
async def get_all_permissions_route(  # Изменено имя функции
    service: PermissionServiceDependency,
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Получить все права доступа в системе (только для Admin/Root)."""
    return await service.get_all_permissions(current_user, limit, offset)


@router.patch("/update/{permission_id}", response_model=PermissionResponse)
async def update_permission_route(  # Изменено имя функции
    permission_id: UUID,
    data: PermissionUpdate,
    service: PermissionServiceDependency,
    current_user: User = Depends(get_current_user)
):
    """Обновить сроки действия права доступа."""
    return await service.update_permission(permission_id, data, current_user)


@router.post("/revoke", status_code=status.HTTP_200_OK)  # Используем POST для удаления по телу запроса
async def revoke_permission(  # Изменено имя функции
    data: PermissionDelete,
    service: PermissionServiceDependency,
    current_user: User = Depends(get_current_user)
):
    """Отозвать (удалить) право доступа."""
    return await service.delete_permission(data.permission_id, current_user)
