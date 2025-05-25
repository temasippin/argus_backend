import asyncio
from datetime import datetime
from typing import Optional, List  # Добавлен List
import uuid  # Добавлено
import logging

import httpx
from fastapi import HTTPException, status

# from app.db_session import db # Не используется
from app.models.device import (Device, DeviceCreate, DeviceDelete, DeviceUpdate,
                               DeviceWakeupPayloadFromCV, DeviceWakeupResponse)  # Добавлены новые модели
from app.models.user import AccessLevel, User
from app.models.access_log import AccessLogCreate  # Добавлено
from app.repositories.device import DeviceRepo
from app.repositories.user import UserRepo
from app.repositories.zone import ZoneRepo
from app.repositories.audit_log import AuditLogRepo  # Добавлено
from app.repositories.access_log import AccessLogRepo  # Добавлено
from app.services.audit_utils import AuditLogger  # Добавлено
from app.services.permission import PermissionService  # Добавлено
from app.config import settings  # Для URL CV-модели

logger = logging.getLogger(__name__)


class DeviceService:
    def __init__(
        self,
        user_repo: UserRepo,
        zone_repo: ZoneRepo,
        device_repo: DeviceRepo,
        audit_repo: AuditLogRepo,  # Добавлено
        access_log_repo: AccessLogRepo,  # Добавлено
        permission_service: PermissionService  # Добавлено
    ):
        self.user_repo = user_repo
        self.zone_repo = zone_repo
        self.device_repo = device_repo
        self.audit_repo = audit_repo
        self.access_log_repo = access_log_repo
        self.permission_service = permission_service

    async def create_device(self, device_data: DeviceCreate, current_user: User) -> Device:
        await self.user_repo.min_manager_access_level(current_user)

        # Проверяем, существует ли зона
        zone = await self.zone_repo.select_zone(zone_id=device_data.zone_id)
        if not zone:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Zone with id {device_data.zone_id} not found.")

        device_id = await self.device_repo.create_device(device_data)
        created_device = await self.device_repo.select_device(device_id=device_id)

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="create_device",
            entity_type="device", entity_id=device_id,
            details={"name": device_data.name, "ip": str(device_data.ip), "zone_id": str(device_data.zone_id)}
        )
        return created_device

    async def update_device(self, device_data: DeviceUpdate, current_user: User) -> Device:
        await self.user_repo.min_manager_access_level(current_user)

        existing_device = await self.device_repo.select_device(device_id=device_data.device_id)  # Проверка существования
        if not existing_device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

        if device_data.zone_id:  # Если зона меняется, проверяем ее существование
            zone = await self.zone_repo.select_zone(zone_id=device_data.zone_id)
            if not zone:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"New zone with id {device_data.zone_id} not found.")

        updated_device = await self.device_repo.update_device(device_data)

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="update_device",
            entity_type="device", entity_id=device_data.device_id,
            details={"changes": device_data.model_dump(exclude_unset=True, exclude={'device_id'})}
        )
        return updated_device

    async def delete_device(self, device_data: DeviceDelete, current_user: User):
        await self.user_repo.min_manager_access_level(current_user)

        existing_device = await self.device_repo.select_device(device_id=device_data.device_id)  # Проверка существования
        if not existing_device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

        deleted = await self.device_repo.delete_device(device_data.device_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Device deletion failed.")

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="delete_device",
            entity_type="device", entity_id=device_data.device_id,
            details={"deleted_device_name": existing_device.name}
        )
        return {"message": "Device deleted successfully"}

    async def select_all_devices(self, current_user: User) -> List[Device]:
        await self.user_repo.min_user_access_level(current_user)  # GUEST и выше могут смотреть устройства
        devices = await self.device_repo.select_devices()
        # await asyncio.gather(*[self._update_device_status_in_db(device) for device in devices]) # Обновление статуса в фоне
        # Для роута select можно не обновлять статус каждого, чтобы не замедлять.
        # Статус будет обновляться через check_device_status или wakeup.
        return devices

    async def get_device_by_id(self, device_id: uuid.UUID, current_user: User) -> Device:  # Новый метод
        await self.user_repo.min_user_access_level(current_user)
        device = await self.device_repo.select_device(device_id=device_id)
        # Можно добавить обновление статуса здесь, если нужно
        # await self._update_device_status_in_db(device)
        return device

    async def check_device_status(self, device_id: uuid.UUID, current_user: User):
        await self.user_repo.min_user_access_level(current_user)
        device = await self.device_repo.select_device(device_id=device_id)
        is_online = await self._check_and_update_device_online_status(device)
        return {"device_id": device.device_id, "name": device.name, "is_online": is_online}

    async def _check_and_update_device_online_status(self, device: Device) -> bool:
        """Проверяет статус устройства (ping) и обновляет его в БД, если он изменился."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Пример проверки: простой GET-запрос. Может быть ICMP ping или специфичный health-check эндпоинт
                response = await client.get(f"http://{device.ip}:{device.port}/health")  # /health или /status
                is_online_now = response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException):
            is_online_now = False

        if device.is_online != is_online_now:
            await self.device_repo.update_device_status(device.device_id, is_online_now)
            # Не обновляем device.is_online здесь, т.к. select_device вернет актуальное значение из БД
        return is_online_now

    async def handle_device_event_from_cv(self, ip_config: dict) -> DeviceWakeupResponse:
        """
        Обрабатывает "wakeup" событие от камеры.
        Камера (или ее шлюз) вызывает этот эндпоинт.
        Этот эндпоинт делает запрос к CV-модели.
        """
        # 1. Получаем информацию об устройстве, которое вызвало wakeup
        device_info = await self.device_repo.select_device_by_ip_port(ip_config=ip_config)
        if not device_info:
            # Этого не должно произойти, если device_id валидный
            logger.error(f"Wakeup event for non-existent device_id: {ip_config}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device initiating wakeup not found.")

        # 2. Отправляем запрос CV-модели, передавая device_id камеры.
        # CV-модель должна обработать событие с этой камеры и вернуть результат.
        # URL CV-модели может быть другим для этого типа запроса.
        cv_payload_for_request = {"device_id": str(device_info['device_id'])}
        cv_event_data: Optional[DeviceWakeupPayloadFromCV] = None
        cv_request_error_str = None

        try:
            async with httpx.AsyncClient() as client:
                # Пример: CV-модель имеет специальный эндпоинт для событий с камер
                # URL может быть f"{settings.cv.url}/camera_event" или аналогичный
                cv_target_url = f"{settings.cv.url}/process_event"  # Уточните этот URL
                response = await client.post(
                    cv_target_url,
                    json=cv_payload_for_request,
                    timeout=float(settings.cv.timeout)
                )
                response.raise_for_status()
                cv_event_data_raw = response.json()
                cv_event_data = DeviceWakeupPayloadFromCV.model_validate(cv_event_data_raw)
        except httpx.HTTPStatusError as e:
            cv_request_error_str = f"CV model error {e.response.status_code}: {e.response.text[:200]}"
            logger.warning(f"CV request failed for device {device_info['device_id']}: {cv_request_error_str}")
        except (httpx.RequestError, httpx.TimeoutException) as e:
            cv_request_error_str = f"CV model request failed: {str(e)}"
            logger.warning(f"CV request error for device {device_info['device_id']}: {cv_request_error_str}")
        except Exception as e:  # Pydantic ValidationError и др.
            cv_request_error_str = f"Error processing CV model response: {str(e)}"
            logger.error(f"Error with CV response for device {device_info['device_id']}: {cv_request_error_str}")

        # 3. Обработка ответа от CV-модели и логирование в AccessLog
        user_id_from_cv = cv_event_data.user_id if cv_event_data else None
        biometry_id_from_cv = cv_event_data.biometry_id if cv_event_data else None
        event_type_from_cv = cv_event_data.event_type if cv_event_data else "cv_communication_error"
        confidence_from_cv = cv_event_data.confidence if cv_event_data else None
        photo_path_from_cv = cv_event_data.path_to_photo if cv_event_data else None

        access_granted = False
        final_event_type = event_type_from_cv

        # 4. Проверка прав, если пользователь идентифицирован
        if user_id_from_cv:
            user = await self.user_repo.select_user(user_id=user_id_from_cv)  # может кинуть 404
            if user:
                if user.access_level == AccessLevel.ADMIN or user.access_level == AccessLevel.ROOT:
                    access_granted = True  # Админы/Руты имеют доступ везде
                else:
                    # Проверяем права менеджера/пользователя
                    has_permission = await self.permission_service.check_user_permission_for_device(user, device_info['device_id'])
                    if has_permission:
                        access_granted = True
                    else:
                        final_event_type = "access_denied_no_permission"
                        logger.info(f"Access denied for user {user_id_from_cv} to device {device_info['device_id']}: No permission.")
            else:  # Пользователь из CV не найден в нашей БД
                final_event_type = "access_denied_unknown_user"
                logger.warning(f"User {user_id_from_cv} from CV model not found in local DB for device {device_info['device_id']}.")
        else:  # Пользователь не идентифицирован CV-моделью
            if cv_request_error_str:  # Если была ошибка связи с CV
                final_event_type = "cv_error"
            elif event_type_from_cv == "face_not_recognized" or not cv_event_data:
                final_event_type = "access_denied_not_recognized"
            # другие event_type от CV, не связанные с распознаванием, могут не требовать user_id

        # 5. Запись в AccessLog
        log_entry = AccessLogCreate(
            user_id=user_id_from_cv,
            device_id=device_info['device_id'],
            biometry_id=biometry_id_from_cv,
            event_type=final_event_type,
            confidence=confidence_from_cv,
            path_to_photo=photo_path_from_cv,
            access_granted=access_granted
        )
        await self.access_log_repo.create(log_entry)

        # 6. Если доступ предоставлен, отправить команду на открытие двери (GET запрос)
        if access_granted:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    # Пример команды: GET /open. URL и метод могут отличаться.
                    # IP и порт берем из device_info
                    open_url = f"http://{device_info.ip}:{device_info.port}/open_door"  # Уточните этот URL
                    open_response = await client.get(open_url)
                    open_response.raise_for_status()  # Проверка на ошибки от устройства
                    logger.info(f"Door open command sent to device {device_info['device_id']} for user {user_id_from_cv}. Status: {open_response.status_code}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to send open command to device {device_info['device_id']}. Device error {e.response.status_code}: {e.response.text[:100]}")
                # Можно добавить запись в access_log о неудачной команде открытия, если нужно
            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.error(f"Failed to send open command to device {device_info['device_id']}. Network error: {str(e)}")

        return DeviceWakeupResponse(
            message=f"Event '{final_event_type}' processed for device {device_info['device_id']}.",
            access_granted=access_granted,
            final_event_type=final_event_type,
            processed_device_id=device_info['device_id'],
            identified_user_id=user_id_from_cv
        )
