from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File

from app.models.user import User, AccessLevel
from app.models.openvpn import VpnConfigUpload, VpnStatusUpdateRequest, VpnStatusResponse
from app.depends import OpenVPNServiceDependency
from app.pkg.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/openvpn",
    tags=["VPN Configuration"]
)


@router.post("/upload", response_model=VpnStatusResponse, status_code=status.HTTP_201_CREATED)
async def upload_vpn_configuration(
    vpn_service: OpenVPNServiceDependency,
    file: UploadFile = File(...),  # Принимаем файл
    current_user: User = Depends(get_current_user)
):
    if current_user.access_level < AccessLevel.ROOT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    try:
        contents = await file.read()
        ovpn_content = contents.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not read .ovpn file: {e}")
    finally:
        await file.close()

    if not ovpn_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OVPN file content is empty")

    config_data = VpnConfigUpload(ovpn_content=ovpn_content)
    return await vpn_service.update_vpn_config(config_data, current_user)


@router.post("/status", response_model=VpnStatusResponse)
async def set_vpn_status(
    status_update: VpnStatusUpdateRequest,
    vpn_service: OpenVPNServiceDependency,
    current_user: User = Depends(get_current_user)
):
    return await vpn_service.update_vpn_status(status_update, current_user)


@router.get("/status", response_model=VpnStatusResponse)
async def get_vpn_status_route(  # Переименовано, чтобы избежать конфликта с POST
    vpn_service: OpenVPNServiceDependency,
    current_user: User = Depends(get_current_user)
):
    # Проверка прав доступа уже внутри сервисного метода get_vpn_status
    return await vpn_service.get_vpn_status(current_user)
