from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Header  # Добавлен Path
from starlette import status

from app.depends import DeviceServiceDependency
from app.models.device import (Device, DeviceCreate, DeviceDelete, DeviceUpdate,
                               DeviceWakeupResponse)  # Добавлена DeviceWakeupResponse
from app.models.user import User
from app.pkg.auth import get_current_user

router = APIRouter(
    prefix='/api/v1/device',
    tags=['device']
)


@router.post("/create", response_model=Device, status_code=status.HTTP_201_CREATED)  # Добавил status_code
async def create_device(
    device_service: DeviceServiceDependency,
    device_data: DeviceCreate,
    current_user: User = Depends(get_current_user)
):
    return await device_service.create_device(device_data, current_user)


@router.post("/update", response_model=Device)  # Можно path("/update/{device_id}") и брать device_id из пути
async def update_device(
    device_service: DeviceServiceDependency,
    device_data: DeviceUpdate,  # device_id передается в теле
    current_user: User = Depends(get_current_user)
):
    return await device_service.update_device(device_data, current_user)


@router.post("/delete")  # Можно path("/delete/{device_id}")
async def delete_device(
    device_service: DeviceServiceDependency,
    device_data: DeviceDelete,  # device_id передается в теле
    current_user: User = Depends(get_current_user)
):
    return await device_service.delete_device(device_data, current_user)


@router.get("/select", response_model=List[Device])
async def select_all_devices(
    device_service: DeviceServiceDependency,
    current_user: User = Depends(get_current_user)
):
    return await device_service.select_all_devices(current_user)


@router.get("/select/{device_id}", response_model=Device)  # Новый роут для получения одного устройства
async def select_device_by_id(
    device_id: UUID,
    device_service: DeviceServiceDependency,
    current_user: User = Depends(get_current_user)
):
    return await device_service.get_device_by_id(device_id, current_user)


@router.get("/check_status/{device_id}")
async def check_device_status(  # Возвращает dict, можно сделать модель ответа
    device_id: UUID,
    device_service: DeviceServiceDependency,
    current_user: User = Depends(get_current_user)
):
    return await device_service.check_device_status(device_id, current_user)


# Новый эндпоинт WAKEUP
@router.post("/wakeup", response_model=DeviceWakeupResponse)
async def device_wakeup_event(
    device_service: DeviceServiceDependency,
    request: Request,
):
    client_ip = request.client.host if request.client else None
    client_port = request.client.port if request.client else None
    ip_config = {
        "ip": client_ip,
        "port": client_port,
    }
    return await device_service.handle_device_event_from_cv(ip_config)


@router.post("/wakeup/nginx", response_model=DeviceWakeupResponse)
async def device_wakeup_event_nginx(
    device_service: DeviceServiceDependency,
    request: Request,
    x_forwarded_for: str = Header(None),
    x_forwarded_port: str = Header(None),
    x_real_port: str = Header(None),
):
    client_ip = (
        x_forwarded_for.split(",")[0].strip()
        if x_forwarded_for
        else request.client.host
    )

    client_port = (
        x_forwarded_port or x_real_port or (request.client.port if request.client else None)
    )

    ip_config = {
        "ip": client_ip,
        "port": client_port,
    }
    return await device_service.handle_device_event_from_cv(ip_config)
