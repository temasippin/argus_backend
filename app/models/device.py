from datetime import datetime
from typing import List, Union, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field
from pydantic.networks import IPvAnyAddress


class Device(BaseModel):
    device_id: UUID
    name: str | None = None
    ip: IPvAnyAddress
    port: int | None = None
    zone_id: UUID | None = None
    location_description: str | None = None
    is_online: bool
    last_heartbeat: datetime | None
    created_at: datetime
    updated_at: datetime | None


class DeviceCreate(BaseModel):
    name: str
    ip: IPvAnyAddress
    port: int
    zone_id: UUID
    location_description: str | None = None


class DeviceUpdate(BaseModel):
    device_id: UUID
    name: str | None = None
    ip: IPvAnyAddress | None = None
    port: int | None = None
    zone_id: UUID | None = None
    location_description: str | None = None


class DeviceDelete(BaseModel):
    device_id: UUID


class DeviceWakeupPayloadFromCV(BaseModel):  # Данные, которые CV-модель возвращает
    user_id: Optional[UUID] = None
    # device_id: UUID # CV-модель не обязательно должна возвращать device_id, т.к. мы его уже знаем
    biometry_id: Optional[UUID] = None
    event_type: str  # Например, "face_recognized", "face_not_recognized", "tampering_detected"
    confidence: Optional[float] = None
    path_to_photo: Optional[str] = None


class DeviceWakeupResponse(BaseModel):  # Ответ нашего API на /wakeup
    message: str
    access_granted: bool
    final_event_type: str
    processed_device_id: UUID
    identified_user_id: Optional[UUID] = None
