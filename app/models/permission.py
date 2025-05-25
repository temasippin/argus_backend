from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PermissionBase(BaseModel):
    user_id: UUID = Field(..., description="ID пользователя, которому выдается право")
    target_type: Literal['DEVICE', 'ZONE'] = Field(..., description="Тип объекта (DEVICE или ZONE)")
    target_id: UUID = Field(..., description="ID объекта (device_id или zone_id)")
    valid_from: Optional[datetime] = Field(default_factory=datetime.now, description="Время начала действия права")
    valid_to: Optional[datetime] = Field(None, description="Время окончания действия права (None - бессрочно)")
    # schedule: Optional[dict] = Field(None, description="Расписание доступа (JSONB)") # Можно добавить позже


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    # Позволяем обновлять только сроки действия. Тип и объект права не меняются.
    # Для изменения типа/объекта - удалить старое право и создать новое.
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    # schedule: Optional[dict] = None


class Permission(PermissionBase):  # Модель для представления данных из БД
    permission_id: UUID = Field(..., description="ID права доступа")
    assigned_by: UUID = Field(..., description="ID пользователя, выдавшего право")
    created_at: datetime = Field(..., description="Время создания записи о праве")
    updated_at: Optional[datetime] = Field(None, description="Время последнего обновления права")

    class Config:
        from_attributes = True


class PermissionResponse(Permission):  # Модель для ответа API
    pass


class PermissionDelete(BaseModel):
    permission_id: UUID = Field(..., description="ID права для удаления")
