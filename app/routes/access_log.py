from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.depends import AccessLogServiceDependency
from app.models.user import User
from app.models.access_log import AccessLogResponse
from app.pkg.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/access-log",
    tags=["access-log"],
    dependencies=[Depends(get_current_user)]
)


@router.get("/select", response_model=List[AccessLogResponse])
async def select_access_logs(
    service: AccessLogServiceDependency,
    current_user: User = Depends(get_current_user),
    device_id: Optional[UUID] = Query(None, description="Фильтр по ID устройства"),
    user_id_filter: Optional[UUID] = Query(None, alias="userId", description="Фильтр по ID пользователя"),
    start_time: Optional[datetime] = Query(None, description="Начало периода (ISO формат)"),
    end_time: Optional[datetime] = Query(None, description="Конец периода (ISO формат)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Получить записи из журнала доступа.
    Менеджеры должны указать device_id или получат ошибку (если не реализована логика просмотра по всем их устройствам).
    Админы могут смотреть все логи или фильтровать по device_id / user_id.
    """
    return await service.get_access_logs(
        current_user=current_user,
        device_id=device_id,
        user_id_filter=user_id_filter,
        limit=limit,
        offset=offset,
        start_time=start_time,
        end_time=end_time
    )
