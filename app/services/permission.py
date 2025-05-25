import uuid
from typing import List
from fastapi import HTTPException, status
import logging

from app.models.user import User, AccessLevel
from app.models.permission import Permission, PermissionCreate, PermissionUpdate, PermissionDelete
from app.repositories.user import UserRepo
from app.repositories.permission import PermissionRepo
from app.repositories.device import DeviceRepo
from app.repositories.zone import ZoneRepo
from app.services.audit_utils import AuditLogger  # Добавлено
from app.repositories.audit_log import AuditLogRepo  # Добавлено

logger = logging.getLogger(__name__)


class PermissionService:
    def __init__(
        self,
        user_repo: UserRepo,
        permission_repo: PermissionRepo,
        device_repo: DeviceRepo,
        zone_repo: ZoneRepo,
        audit_repo: "AuditLogRepo"  # Типизируем строкой для избежания циклического импорта
    ):
        self.user_repo = user_repo
        self.permission_repo = permission_repo
        self.device_repo = device_repo
        self.zone_repo = zone_repo
        self.audit_repo = audit_repo  # Добавлено

    async def create_permission(self, data: PermissionCreate, current_user: User) -> Permission:
        await self.user_repo.min_manager_access_level(current_user)  # Менеджер и выше

        # Проверяем, существует ли пользователь, которому выдаются права
        target_user = await self.user_repo.select_user(user_id=data.user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {data.user_id} not found.")

        # Проверяем, что менеджер не выдает права пользователю с уровнем выше или равным своему (кроме ROOT)
        if current_user.access_level != AccessLevel.ROOT and target_user.access_level >= current_user.access_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot grant permissions to a user with an equal or higher access level."
            )

        # Проверяем, существует ли целевой объект (устройство или зона)
        if data.target_type == 'DEVICE':
            target_object = await self.device_repo.select_device(device_id=data.target_id)
            if not target_object:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device with id {data.target_id} not found.")
        elif data.target_type == 'ZONE':
            target_object = await self.zone_repo.select_zone(zone_id=data.target_id)
            if not target_object:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Zone with id {data.target_id} not found.")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target_type.")

        permission = await self.permission_repo.create(data, current_user.user_id)

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="create_permission",
            entity_type="permission", entity_id=permission.permission_id,
            details={
                "granted_to_user_id": str(data.user_id),
                "target_type": data.target_type,
                "target_id": str(data.target_id)
            }
        )
        return permission

    async def get_permission(self, permission_id: uuid.UUID, current_user: User) -> Permission:
        await self.user_repo.min_manager_access_level(current_user)
        permission = await self.permission_repo.get_by_id(permission_id)
        if not permission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

        # Менеджер может видеть только те права, которые он выдал или права пользователей ниже уровнем
        # Админ/Рут видят все
        if current_user.access_level < AccessLevel.ADMIN:
            target_user = await self.user_repo.select_user(user_id=permission.user_id)
            if permission.assigned_by != current_user.user_id and target_user.access_level >= current_user.access_level:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges to view this permission.")
        return permission

    async def get_permissions_for_user(self, user_id_to_view: uuid.UUID, current_user: User) -> List[Permission]:
        await self.user_repo.min_manager_access_level(current_user)

        user_to_view = await self.user_repo.select_user(user_id=user_id_to_view)
        if not user_to_view:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {user_id_to_view} not found.")

        if current_user.access_level < AccessLevel.ADMIN and user_to_view.access_level >= current_user.access_level and current_user.user_id != user_id_to_view:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges to view permissions of this user.")

        return await self.permission_repo.get_for_user(user_id_to_view)

    async def get_all_permissions(self, current_user: User, limit: int = 100, offset: int = 0) -> List[Permission]:
        await self.user_repo.min_admin_access_level(current_user)  # Только админ/рут видят все права
        return await self.permission_repo.get_all(limit, offset)

    async def update_permission(self, permission_id: uuid.UUID, data: PermissionUpdate, current_user: User) -> Permission:
        await self.user_repo.min_manager_access_level(current_user)

        existing_permission = await self.permission_repo.get_by_id(permission_id)
        if not existing_permission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

        target_user = await self.user_repo.select_user(user_id=existing_permission.user_id)
        if current_user.access_level < AccessLevel.ADMIN and \
           (existing_permission.assigned_by != current_user.user_id and target_user.access_level >= current_user.access_level):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges to update this permission.")

        updated_permission = await self.permission_repo.update(permission_id, data, current_user.user_id)
        if not updated_permission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found or could not be updated")

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="update_permission",
            entity_type="permission", entity_id=permission_id,
            details={"changes": data.model_dump(exclude_unset=True)}
        )
        return updated_permission

    async def delete_permission(self, permission_id: uuid.UUID, current_user: User):
        await self.user_repo.min_manager_access_level(current_user)

        existing_permission = await self.permission_repo.get_by_id(permission_id)
        if not existing_permission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

        target_user = await self.user_repo.select_user(user_id=existing_permission.user_id)
        if current_user.access_level < AccessLevel.ADMIN and \
           (existing_permission.assigned_by != current_user.user_id and target_user.access_level >= current_user.access_level):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges to delete this permission.")

        deleted = await self.permission_repo.delete(permission_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete permission")

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="delete_permission",
            entity_type="permission", entity_id=permission_id
        )
        return {"message": "Permission deleted successfully"}

    async def check_user_permission_for_device(self, user: User, device_id: uuid.UUID) -> bool:
        """Проверяет, есть ли у пользователя прямое разрешение на устройство или разрешение на зону, к которой принадлежит устройство."""
        # 1. Проверка прямого разрешения на устройство
        has_direct_permission = await self.permission_repo.check_active_permission(user.user_id, 'DEVICE', device_id)
        if has_direct_permission:
            return True

        # 2. Проверка разрешения на зону устройства
        device = await self.device_repo.select_device(device_id=device_id)  # может бросить 404, если устройства нет
        if device and device.zone_id:
            has_zone_permission = await self.permission_repo.check_active_permission(user.user_id, 'ZONE', device.zone_id)
            if has_zone_permission:
                return True
        return False
