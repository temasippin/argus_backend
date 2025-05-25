import os
import json
from fastapi import HTTPException, status, Depends

from app.models.openvpn import VpnConfigUpload, VpnStatusUpdateRequest, VpnStatusResponse, VpnConfigDB
from app.models.user import User, AccessLevel
from app.repositories.openvpn import OpenVPNRepo
from app.repositories.user import UserRepo
from app.pkg.docker_manager import DockerManager
from app.config import settings


class OpenVPNService:
    def __init__(self, user_repo: UserRepo, openvpn_repo: OpenVPNRepo, manager: DockerManager):
        self.user_repo = user_repo
        self.openvpn_repo = openvpn_repo
        self.manager = manager

    async def _ensure_config_dir_exists(self):
        openvpn_dir = os.path.dirname(settings.openvpn.path_host)
        if not os.path.exists(openvpn_dir):
            try:
                os.makedirs(openvpn_dir, exist_ok=True)
            except OSError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Could not create directory for VPN config: {e}"
                )

    async def update_vpn_config(self, config_data: VpnConfigUpload, current_user: User) -> VpnStatusResponse:
        if current_user.access_level < AccessLevel.ROOT:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

        # Сохраняем в БД
        db_openvpn = await self.openvpn_repo.upsert_configuration(vpn_config_content=config_data.ovpn_content)

        # Записываем конфиг в файл, если VPN включен или для будущего включения
        # (openvpn_client может автоматически подхватить изменения, если он так настроен,
        # но dperson/openvpn-client обычно требует перезапуска или HUP сигнала)
        await self._ensure_config_dir_exists()
        try:
            with open(settings.openvpn.path_host, "w") as f:
                f.write(config_data.ovpn_content)
        except IOError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to write VPN config file: {e}"
            )

        # Если VPN был активен, его нужно перезапустить с новым конфигом
        if db_openvpn.vpn_enabled:
            await self.manager.stop_vpn_container()  # Останавливаем
            await self.manager.start_vpn_container()  # Запускаем (он подхватит новый client.ovpn)

        return await self.get_vpn_status(current_user)

    async def update_vpn_status(self, status_data: VpnStatusUpdateRequest, current_user: User) -> VpnStatusResponse:
        if current_user.access_level < AccessLevel.ROOT:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

        config = await self.openvpn_repo.get_configuration()
        if not config or not config.vpn_config:
            if status_data.enabled:  # Пытаемся включить VPN без конфига
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot enable VPN without a configuration. Please upload a .ovpn file first."
                )
            # Если выключаем VPN или конфига нет, то просто обновляем статус в БД
            await self.openvpn_repo.upsert_configuration(vpn_enabled=False)

        if status_data.enabled:
            # Проверяем, что конфиг файл существует перед запуском
            if not os.path.exists(settings.openvpn.path_host):
                if config and config.vpn_config and "ovpn_content" in config.vpn_config:
                    await self._ensure_config_dir_exists()
                    try:
                        with open(settings.openvpn.path_host, "w") as f:
                            f.write(config.vpn_config["ovpn_content"])
                    except IOError as e:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to write VPN config file before starting: {e}"
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="VPN config file not found and no config in DB. Upload config first."
                    )

            await self.manager.start_vpn_container()
            await self.openvpn_repo.upsert_configuration(vpn_enabled=True)
        else:
            await self.manager.stop_vpn_container()
            await self.openvpn_repo.upsert_configuration(vpn_enabled=False)

        return await self.get_vpn_status(current_user)

    async def get_vpn_status(self, current_user: User) -> VpnStatusResponse:
        if current_user.access_level < AccessLevel.ADMIN:  # Читать статус могут и админы
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

        config = await self.openvpn_repo.get_configuration()
        container_status = await self.manager.get_vpn_container_status()

        if not config:
            # Если конфига в БД нет вообще, создаем запись по умолчанию (VPN выключен)
            default_config = await self.openvpn_repo.upsert_configuration(vpn_enabled=False, vpn_config_content=None)
            return VpnStatusResponse(
                openvpn_id=default_config.openvpn_id,
                vpn_enabled=False,
                vpn_config_present=False,
                vpn_container_status=container_status,
                updated_at=default_config.updated_at
            )

        return VpnStatusResponse(
            openvpn_id=config.openvpn_id,
            vpn_enabled=config.vpn_enabled,
            vpn_config_present=bool(config.vpn_config and config.vpn_config.get("ovpn_content")),
            vpn_container_status=container_status,
            updated_at=config.updated_at
        )
