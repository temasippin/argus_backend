import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
import logging

from app.models.user import User, AccessLevel
from app.models.audit_log import AuditLogResponse
from app.repositories.user import UserRepo
from app.repositories.audit_log import AuditLogRepo

logger = logging.getLogger(__name__)


class AuditLogService:
    def __init__(self, user_repo: UserRepo, audit_log_repo: AuditLogRepo):
        self.user_repo = user_repo
        self.audit_log_repo = audit_log_repo

    async def get_audit_logs(
        self,
        current_user: User,
        user_id_filter: Optional[uuid.UUID] = None,
        entity_type_filter: Optional[str] = None,
        entity_id_filter: Optional[uuid.UUID] = None,
        action_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AuditLogResponse]:
        # Только админ и выше могут смотреть аудит лог
        await self.user_repo.min_admin_access_level(current_user)

        return await self.audit_log_repo.select_logs(
            user_id_filter=user_id_filter,
            entity_type_filter=entity_type_filter,
            entity_id_filter=entity_id_filter,
            action_filter=action_filter,
            limit=limit,
            offset=offset,
            start_time=start_time,
            end_time=end_time
        )
