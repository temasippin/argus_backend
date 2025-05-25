from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

# from app.config import settings # Не используется


class BiometryDB(BaseModel):  # Модель для представления данных из БД
    biometry_id: UUID
    user_id: UUID
    encrypted_embedding: bytes  # Это поле есть в таблице и используется в репозитории
    iv: bytes                # Это поле есть в таблице и используется в репозитории
    secure_hash: bytes       # Это поле есть в таблице и используется в репозитории
    created_at: datetime

    class Config:
        from_attributes = True


class BiometryCreate(BaseModel):  # Данные для создания биометрии
    user_id: UUID = Field(..., description="ID пользователя, для которого создается биометрия")


class BiometryUpdate(BaseModel):  # Данные для обновления биометрии (по сути, замена фото)
    biometry_id: UUID = Field(..., description="ID биометрической записи для обновления")
    # user_id не меняется, фото привязано к user_id через biometry_id


class BiometryDelete(BaseModel):
    biometry_id: UUID = Field(..., description="ID биометрической записи для удаления")


class BiometryResponse(BaseModel):  # Ответ API
    biometry_id: UUID
    user_id: UUID
    created_at: datetime
    algorithm_version: str = Field("1.0", description="Версия алгоритма обработки")
