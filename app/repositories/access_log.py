import uuid
from datetime import datetime
from typing import List, Optional
import logging

import asyncpg
from fastapi import HTTPException, status

from app.db_session import db
from app.models.access_log import AccessLog, AccessLogCreate

logger = logging.getLogger(__name__)


class AccessLogRepo:
    @staticmethod
    async def create(log_data: AccessLogCreate) -> AccessLog:
        q = """
            INSERT INTO public.access_log (
                user_id, device_id, biometry_id, event_type, confidence, path_to_photo, access_granted, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            RETURNING access_log_id, user_id, device_id, biometry_id, event_type, confidence, path_to_photo, access_granted, created_at;
        """
        try:
            row = await db.pool.fetchrow(
                q, log_data.user_id, log_data.device_id, log_data.biometry_id,
                log_data.event_type, log_data.confidence, log_data.path_to_photo, log_data.access_granted
            )
            if not row:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create access log entry")
            return AccessLog.model_validate(row)
        except asyncpg.ForeignKeyViolationError as e:
            logger.error(f"AccessLog creation FK violation: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid foreign key in access log data: {str(e).splitlines()[-1]}")
        except Exception as e:
            logger.exception("Error creating access log in DB")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(e)}")

    @staticmethod
    async def select_logs(
        device_id: Optional[uuid.UUID] = None,
        user_id_param: Optional[uuid.UUID] = None,  # Изменено имя параметра
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AccessLog]:
        conditions = []
        params = []

        current_param_idx = 1
        if device_id:
            conditions.append(f"device_id = ${current_param_idx}")
            params.append(device_id)
            current_param_idx += 1
        if user_id_param:
            conditions.append(f"user_id = ${current_param_idx}")
            params.append(user_id_param)
            current_param_idx += 1
        if start_time:
            conditions.append(f"created_at >= ${current_param_idx}")
            params.append(start_time)
            current_param_idx += 1
        if end_time:
            conditions.append(f"created_at <= ${current_param_idx}")
            params.append(end_time)
            current_param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        q = f"""
            SELECT * FROM public.access_log
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${current_param_idx} OFFSET ${current_param_idx + 1};
        """
        params.extend([limit, offset])

        rows = await db.pool.fetch(q, *params)
        return [AccessLog.model_validate(row) for row in rows]
