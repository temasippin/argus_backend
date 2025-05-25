from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.depends import AuditLogServiceDependency
from app.models.user import User
from app.models.audit_log import AuditLogResponse
from app.pkg.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/audit-log",
    tags=["audit-log"],
    dependencies=[Depends(get_current_user)]
)


@router.get("/select", response_model=List[AuditLogResponse])
async def select_audit_logs(
    service: AuditLogServiceDependency,
    current_user: User = Depends(get_current_user),
    user_id_filter: Optional[UUID] = Query(None, alias="userId", description="Фильтр по ID пользователя, совершившего действие"),
    entity_type_filter: Optional[str] = Query(None, alias="entityType", description="Фильтр по типу сущности"),
    entity_id_filter: Optional[UUID] = Query(None, alias="entityId", description="Фильтр по ID сущности"),
    action_filter: Optional[str] = Query(None, alias="action", description="Фильтр по действию (частичное совпадение)"),
    start_time: Optional[datetime] = Query(None, description="Начало периода (ISO формат)"),
    end_time: Optional[datetime] = Query(None, description="Конец периода (ISO формат)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Получить записи из журнала аудита (только для Admin/Root).
    """
    return await service.get_audit_logs(
        current_user=current_user,
        user_id_filter=user_id_filter,
        entity_type_filter=entity_type_filter,
        entity_id_filter=entity_id_filter,
        action_filter=action_filter,
        limit=limit,
        offset=offset,
        start_time=start_time,
        end_time=end_time
    )
