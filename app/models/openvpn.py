from pydantic import BaseModel, Json
from typing import Optional, Dict, Any
import uuid
from datetime import datetime


class VpnConfigUpload(BaseModel):
    ovpn_content: str  # Содержимое .ovpn файла


class VpnConfigDB(BaseModel):
    openvpn_id: uuid.UUID
    vpn_enabled: bool = False
    vpn_config: Optional[Dict[str, Any]] = None  # {"ovpn_content": "..."}
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VpnStatusUpdateRequest(BaseModel):
    enabled: bool


class VpnStatusResponse(BaseModel):
    openvpn_id: Optional[uuid.UUID] = None
    vpn_enabled: bool
    vpn_config_present: bool  # Указывает, загружен ли конфиг
    vpn_container_status: Optional[str] = None  # Статус контейнера openvpn_client
    updated_at: Optional[datetime] = None
