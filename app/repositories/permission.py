import uuid
from datetime import datetime
from typing import List, Optional

import asyncpg
from fastapi import HTTPException, status
import logging  # Для логирования ошибок

from app.db_session import db
from app.models.permission import Permission, PermissionCreate, PermissionUpdate

logger = logging.getLogger(__name__)


class PermissionRepo:
    @staticmethod
    async def create(data: PermissionCreate, assigned_by_user_id: uuid.UUID) -> Permission:
        q = """
            INSERT INTO public.permission (user_id, target_type, target_id, assigned_by, valid_from, valid_to, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            RETURNING permission_id, user_id, target_type, target_id, assigned_by, valid_from, valid_to, created_at, updated_at;
        """
        try:
            row = await db.pool.fetchrow(
                q, data.user_id, data.target_type, data.target_id,
                assigned_by_user_id, data.valid_from, data.valid_to
            )
            if not row:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create permission")
            return Permission.model_validate(row)
        except asyncpg.ForeignKeyViolationError as e:
            logger.error(f"Permission creation FK violation: {e}")
            if "fk_user" in str(e).lower() and "user_id" in str(e).lower():  # Проверяем user_id
                detail = f"User with id {data.user_id} not found."
            elif "fk_assigner" in str(e).lower():
                detail = f"Assigner user with id {assigned_by_user_id} not found."
            else:  # Ошибка с target_id (fk на device или zone неявно) или другой FK
                detail = "Invalid user_id, target_id (device/zone), or assigner_id."
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
        except asyncpg.UniqueViolationError as e:
            logger.warning(f"Permission creation unique violation: {e}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This permission (user-target combination) may already exist.")
        except Exception as e:
            logger.exception("Error creating permission in DB")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(e)}")

    @staticmethod
    async def get_by_id(permission_id: uuid.UUID) -> Optional[Permission]:
        q = "SELECT * FROM public.permission WHERE permission_id = $1;"
        row = await db.pool.fetchrow(q, permission_id)
        return Permission.model_validate(row) if row else None

    @staticmethod
    async def get_for_user(user_id: uuid.UUID) -> List[Permission]:
        q = "SELECT * FROM public.permission WHERE user_id = $1 ORDER BY created_at DESC;"
        rows = await db.pool.fetch(q, user_id)
        return [Permission.model_validate(row) for row in rows]

    @staticmethod
    async def get_all(limit: int = 100, offset: int = 0) -> List[Permission]:
        q = "SELECT * FROM public.permission ORDER BY created_at DESC LIMIT $1 OFFSET $2;"
        rows = await db.pool.fetch(q, limit, offset)
        return [Permission.model_validate(row) for row in rows]

    @staticmethod
    async def check_active_permission(user_id: uuid.UUID, target_type: str, target_id: uuid.UUID) -> bool:
        q = """
            SELECT EXISTS (
                SELECT 1
                FROM public.permission
                WHERE user_id = $1
                  AND target_type = $2
                  AND target_id = $3
                  AND (valid_from IS NULL OR valid_from <= NOW() AT TIME ZONE 'utc')
                  AND (valid_to IS NULL OR valid_to >= NOW() AT TIME ZONE 'utc')
                -- AND (schedule IS NULL OR check_schedule(schedule)) -- Если будет логика расписаний
            );
        """
        has_permission = await db.pool.fetchval(q, user_id, target_type, target_id)
        return bool(has_permission)

    @staticmethod
    async def update(permission_id: uuid.UUID, data: PermissionUpdate, assigned_by_user_id: uuid.UUID) -> Optional[Permission]:
        # Обновляем только valid_from, valid_to и assigned_by (кто последний менял)
        q = """
            UPDATE public.permission
            SET valid_from = COALESCE($1, valid_from),
                valid_to = $2, -- null можно передавать для сброса
                assigned_by = $3,
                updated_at = NOW()
            WHERE permission_id = $4
            RETURNING *;
        """
        try:
            row = await db.pool.fetchrow(q, data.valid_from, data.valid_to, assigned_by_user_id, permission_id)
            return Permission.model_validate(row) if row else None
        except Exception as e:
            logger.exception(f"Error updating permission {permission_id}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error during permission update: {str(e)}")

    @staticmethod
    async def delete(permission_id: uuid.UUID) -> bool:
        q = "DELETE FROM public.permission WHERE permission_id = $1 RETURNING permission_id;"
        result = await db.pool.fetchval(q, permission_id)
        return result is not None
