from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogBase(BaseModel):
    user_id: UUID = Field(..., description="ID пользователя, совершившего действие")
    action: str = Field(..., max_length=32, description="Описание действия (например, 'create_user')")
    entity_type: Optional[str] = Field(None, max_length=32, description="Тип сущности")
    entity_id: Optional[UUID] = Field(None, description="ID сущности")
    action_data: Optional[Dict[str, Any]] = Field(None, description="Дополнительные данные о действии (JSONB)")


class AuditLogCreate(AuditLogBase):
    pass


class AuditLog(AuditLogBase):  # Модель для представления данных из БД
    audit_log_id: UUID = Field(..., description="ID записи в журнале аудита")
    created_at: datetime = Field(..., description="Время действия")

    class Config:
        from_attributes = True


class AuditLogResponse(AuditLog):  # Модель для ответа API
    pass
