from datetime import datetime
from typing import List, Union
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class Zone(BaseModel):
    zone_id: UUID
    name: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: Union[datetime, None] = None


class ZoneCreate(BaseModel):
    name: str
    description: str | None = None


class ZoneUpdate(BaseModel):
    zone_id: UUID
    name: str | None = None
    description: str | None = None


class ZoneDelete(BaseModel):
    zone_id: UUID
