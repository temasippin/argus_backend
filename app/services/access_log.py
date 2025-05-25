import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
import logging

from app.models.user import User, AccessLevel
from app.models.access_log import AccessLogResponse
from app.repositories.user import UserRepo
from app.repositories.access_log import AccessLogRepo
from app.repositories.device import DeviceRepo  # Для проверки, к какой зоне относится устройство
from app.services.permission import PermissionService  # Для проверки прав на просмотр логов
from app.repositories.audit_log import AuditLogRepo  # Добавлено

logger = logging.getLogger(__name__)


class AccessLogService:
    def __init__(
        self,
        user_repo: UserRepo,
        access_log_repo: AccessLogRepo,
        device_repo: DeviceRepo,
        permission_service: PermissionService,  # Добавлена зависимость
        audit_repo: "AuditLogRepo"
    ):
        self.user_repo = user_repo
        self.access_log_repo = access_log_repo
        self.device_repo = device_repo
        self.permission_service = permission_service  # Сохраняем
        self.audit_repo = audit_repo

    async def get_access_logs(
        self,
        current_user: User,
        device_id: Optional[uuid.UUID] = None,
        user_id_filter: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[AccessLogResponse]:
        # Права: Менеджер может смотреть логи по устройствам/зонам, на которые у него есть права.
        # Админ/Рут могут смотреть все логи.

        if current_user.access_level < AccessLevel.MANAGER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges to view access logs.")

        # Если запрашиваются логи для конкретного устройства
        if device_id:
            if current_user.access_level < AccessLevel.ADMIN:
                # Проверяем, есть ли у менеджера права на это устройство или его зону
                has_perm = await self.permission_service.check_user_permission_for_device(current_user, device_id)
                if not has_perm:
                    # Альтернативно, можно разрешить менеджеру видеть логи по всем его устройствам,
                    # но тогда фильтрация должна быть сложнее (получить все его устройства/зоны)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Manager does not have permission for device {device_id} or its zone to view logs."
                    )
        elif current_user.access_level < AccessLevel.ADMIN:
            # Менеджер без указания device_id не может смотреть все логи подряд.
            # Можно реализовать просмотр логов только по тем устройствам, к которым у него есть доступ,
            # но это потребует доп. логики (сначала получить все доступные device_id, потом фильтровать логи).
            # Пока упростим: менеджер должен указать device_id.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Managers must specify a device_id to view access logs. Admins can view all."
            )

        # Пользователь с правами MANAGER или выше может запрашивать логи
        # Фильтрация по user_id_filter также должна учитывать права current_user, если это не админ
        # (например, менеджер не должен видеть логи по пользователям выше себя, если это не логи по его устройству)
        # Пока оставим эту логику простой, т.к. основная проверка по device_id.

        return await self.access_log_repo.select_logs(
            device_id=device_id,
            user_id_param=user_id_filter,
            limit=limit,
            offset=offset,
            start_time=start_time,
            end_time=end_time
        )
