from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AccessLogBase(BaseModel):
    user_id: Optional[UUID] = Field(None, description="ID пользователя (если идентифицирован)")
    device_id: UUID = Field(..., description="ID устройства, сгенерировавшего событие")
    biometry_id: Optional[UUID] = Field(None, description="ID биометрической записи (если использовалась)")
    event_type: str = Field(..., max_length=32, description="Тип события (например, 'access_granted', 'cv_timeout')")
    confidence: Optional[float] = Field(None, description="Уверенность распознавания (если применимо)")
    path_to_photo: Optional[str] = Field(None, max_length=128, description="Путь к фото события")
    access_granted: Optional[bool] = Field(False, description="Был ли предоставлен доступ по итогу проверки прав")


class AccessLogCreate(AccessLogBase):
    pass


class AccessLog(AccessLogBase):  # Модель для представления данных из БД
    access_log_id: UUID = Field(..., description="ID записи в журнале доступа")
    created_at: datetime = Field(..., description="Время события")

    class Config:
        from_attributes = True


class AccessLogResponse(AccessLog):  # Модель для ответа API
    pass
