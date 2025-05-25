import uuid
from datetime import datetime
from typing import List, Optional, Any, Dict
import json
import logging

import asyncpg
from fastapi import HTTPException, status

from app.db_session import db
from app.models.audit_log import AuditLog, AuditLogCreate

logger = logging.getLogger(__name__)


class AuditLogRepo:
    @staticmethod
    async def create(log_data: AuditLogCreate) -> AuditLog:
        q = """
            INSERT INTO public.audit_log (user_id, action, entity_type, entity_id, action_data, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING audit_log_id, user_id, action, entity_type, entity_id, action_data, created_at;
        """
        action_data_json = json.dumps(log_data.action_data) if log_data.action_data is not None else None
        try:
            row = await db.pool.fetchrow(
                q, log_data.user_id, log_data.action, log_data.entity_type,
                log_data.entity_id, action_data_json
            )
            if not row:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create audit log entry")

            # asyncpg должен десериализовать JSONB в dict
            validated_row = dict(row)
            if isinstance(validated_row.get('action_data'), str):  # На всякий случай
                validated_row['action_data'] = json.loads(validated_row['action_data'])
            return AuditLog.model_validate(validated_row)
        except asyncpg.ForeignKeyViolationError as e:
            logger.error(f"AuditLog creation FK violation for user_id {log_data.user_id}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid user_id in audit log data: {str(e).splitlines()[-1]}")
        except Exception as e:
            logger.exception(f"Error creating audit log for user {log_data.user_id}, action {log_data.action}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(e)}")

    @staticmethod
    async def select_logs(
        user_id_filter: Optional[uuid.UUID] = None,
        entity_type_filter: Optional[str] = None,
        entity_id_filter: Optional[uuid.UUID] = None,
        action_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AuditLog]:
        conditions = []
        params = []
        idx = 1

        if user_id_filter:
            conditions.append(f"user_id = ${idx}")
            params.append(user_id_filter)
            idx += 1
        if entity_type_filter:
            conditions.append(f"entity_type = ${idx}")
            params.append(entity_type_filter)
            idx += 1
        if entity_id_filter:
            conditions.append(f"entity_id = ${idx}")
            params.append(entity_id_filter)
            idx += 1
        if action_filter:
            conditions.append(f"action ILIKE ${idx}")
            params.append(f"%{action_filter}%")  # Для ILIKE '%value%'
            idx += 1
        if start_time:
            conditions.append(f"created_at >= ${idx}")
            params.append(start_time)
            idx += 1
        if end_time:
            conditions.append(f"created_at <= ${idx}")
            params.append(end_time)
            idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        q = f"""
            SELECT * FROM public.audit_log
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1};
        """
        params.extend([limit, offset])

        rows = await db.pool.fetch(q, *params)
        logs = []
        for row_data in rows:
            validated_row = dict(row_data)
            if isinstance(validated_row.get('action_data'), str):
                validated_row['action_data'] = json.loads(validated_row['action_data'])
            logs.append(AuditLog.model_validate(validated_row))
        return logs
