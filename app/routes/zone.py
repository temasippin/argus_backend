from typing import List
from uuid import UUID  # Добавлено

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app.depends import ZoneServiceDependency
from app.models.user import User
from app.models.zone import Zone, ZoneCreate, ZoneDelete, ZoneUpdate
from app.pkg.auth import get_current_user

router = APIRouter(
    prefix='/api/v1/zone',
    tags=['zone'],
    dependencies=[Depends(get_current_user)]
)


@router.post("/create", response_model=Zone, status_code=status.HTTP_201_CREATED)
async def create_zone(
    zone_service: ZoneServiceDependency,
    zone_data: ZoneCreate,
    current_user: User = Depends(get_current_user)
):
    return await zone_service.create_zone(zone_data, current_user)


@router.post("/update", response_model=Zone)  # Можно path("/update/{zone_id}")
async def update_zone(
    zone_service: ZoneServiceDependency,
    zone_data: ZoneUpdate,  # zone_id передается в теле
    current_user: User = Depends(get_current_user)
):
    return await zone_service.update_zone(zone_data, current_user)


@router.post("/delete")  # Можно path("/delete/{zone_id}")
async def delete_zone(
    zone_service: ZoneServiceDependency,
    zone_data: ZoneDelete,  # zone_id передается в теле
    current_user: User = Depends(get_current_user)
):
    return await zone_service.delete_zone(zone_data, current_user)


@router.get("/select", response_model=List[Zone])
async def select_all_zones(
    zone_service: ZoneServiceDependency,
    current_user: User = Depends(get_current_user)
):
    return await zone_service.select_all_zones(current_user)


@router.get("/select/{zone_id}", response_model=Zone)  # Новый роут
async def select_zone_by_id(
    zone_id: UUID,
    zone_service: ZoneServiceDependency,
    current_user: User = Depends(get_current_user)
):
    return await zone_service.get_zone_by_id(zone_id, current_user)
