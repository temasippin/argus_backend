from fastapi import HTTPException, status
import uuid  # Добавлено
from typing import List
# from app.db_session import db # Не используется
from app.models.user import AccessLevel, User
from app.models.zone import Zone, ZoneCreate, ZoneDelete, ZoneUpdate
from app.repositories.user import UserRepo
from app.repositories.zone import ZoneRepo
from app.repositories.audit_log import AuditLogRepo  # Добавлено
from app.services.audit_utils import AuditLogger  # Добавлено


class ZoneService:
    def __init__(self, user_repo: UserRepo, zone_repo: ZoneRepo, audit_repo: AuditLogRepo):  # Добавлен audit_repo
        self.user_repo = user_repo
        self.zone_repo = zone_repo
        self.audit_repo = audit_repo  # Сохраняем

    async def create_zone(self, zone_data: ZoneCreate, current_user: User) -> Zone:
        await self.user_repo.min_manager_access_level(current_user)
        zone_id = await self.zone_repo.create_zone(zone_data)
        created_zone = await self.zone_repo.select_zone(zone_id=zone_id)

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="create_zone",
            entity_type="zone", entity_id=zone_id,
            details={"name": zone_data.name, "description": zone_data.description}
        )
        return created_zone

    async def update_zone(self, zone_data: ZoneUpdate, current_user: User) -> Zone:
        await self.user_repo.min_manager_access_level(current_user)
        # Проверяем, что зона существует перед обновлением
        existing_zone = await self.zone_repo.select_zone(zone_id=zone_data.zone_id)
        if not existing_zone:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")

        updated_zone = await self.zone_repo.update_zone(zone_data)

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="update_zone",
            entity_type="zone", entity_id=zone_data.zone_id,
            details={"changes": zone_data.model_dump(exclude_unset=True, exclude={'zone_id'})}
        )
        return updated_zone

    async def delete_zone(self, zone_data: ZoneDelete, current_user: User):
        await self.user_repo.min_manager_access_level(current_user)
        # Проверяем, что зона существует перед удалением
        existing_zone = await self.zone_repo.select_zone(zone_id=zone_data.zone_id)
        if not existing_zone:  # select_zone уже кидает 404, но для явности
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")

        deleted = await self.zone_repo.delete_zone(zone_data.zone_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Zone deletion failed.")

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="delete_zone",
            entity_type="zone", entity_id=zone_data.zone_id,
            details={"deleted_zone_name": existing_zone.name}
        )
        return {"message": "Zone deleted successfully"}

    async def select_all_zones(self, current_user: User) -> List[Zone]:
        await self.user_repo.min_user_access_level(current_user)  # GUEST и выше могут смотреть зоны
        return await self.zone_repo.select_zones()

    async def get_zone_by_id(self, zone_id: uuid.UUID, current_user: User) -> Zone:  # Новый метод
        await self.user_repo.min_user_access_level(current_user)
        return await self.zone_repo.select_zone(zone_id=zone_id)
