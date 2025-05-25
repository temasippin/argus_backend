import uuid
from datetime import datetime
from typing import List

import asyncpg
from fastapi import HTTPException, status

from app.db_session import db
from app.models.user import AccessLevel, User
from app.models.zone import Zone, ZoneCreate, ZoneUpdate


class ZoneRepo:
    @staticmethod
    async def create_zone(zone_data: ZoneCreate) -> uuid.UUID:
        async with db.pool.acquire() as conn:
            query = """
                INSERT INTO public.zone (
                    name,
                    description
                ) VALUES (
                    $1, $2
                )
                RETURNING zone_id;
            """
            try:
                zone_id = await conn.fetchval(query, zone_data.name, zone_data.description)
                return zone_id
            except asyncpg.UniqueViolationError:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Zone with name '{zone_data.name}' already exists"
                )
            except asyncpg.PostgresError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {e}"
                )

    @staticmethod
    async def select_zone(zone_id: uuid.UUID) -> Zone:
        async with db.pool.acquire() as conn:
            query = """
                SELECT * FROM public.zone
                WHERE zone_id = $1;
            """
            zone = await conn.fetchrow(query, zone_id)
            if not zone:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Zone not found"
                )
            return Zone(
                zone_id=zone['zone_id'],
                name=zone['name'],
                description=zone['description'],
                created_at=zone['created_at'],
                updated_at=zone['updated_at']
            )

    @staticmethod
    async def select_zones() -> List[Zone]:
        async with db.pool.acquire() as conn:
            query = "SELECT * FROM public.zone;"
            zones = await conn.fetch(query)
            return [
                Zone(
                    zone_id=zone['zone_id'],
                    name=zone['name'],
                    description=zone['description'],
                    created_at=zone['created_at'],
                    updated_at=zone['updated_at']
                ) for zone in zones
            ]

    @staticmethod
    async def update_zone(zone_data: ZoneUpdate) -> Zone:
        async with db.pool.acquire() as conn:
            updates = []
            params = []

            fields_to_update = {
                'name': zone_data.name,
                'description': zone_data.description,
                'updated_at': datetime.now()
            }

            for field, value in fields_to_update.items():
                if value is not None:
                    updates.append(f"{field} = ${len(params) + 2}")
                    params.append(value)

            if not updates:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update"
                )

            query = f"""
                UPDATE public.zone
                SET {', '.join(updates)}
                WHERE zone_id = $1
                RETURNING *;
            """

            try:
                updated_zone = await conn.fetchrow(query, zone_data.zone_id, *params)
                return Zone(
                    zone_id=updated_zone['zone_id'],
                    name=updated_zone['name'],
                    description=updated_zone['description'],
                    created_at=updated_zone['created_at'],
                    updated_at=updated_zone['updated_at']
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Zone name '{zone_data.name}' already exists"
                )
            except asyncpg.PostgresError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {e}"
                )

    @staticmethod
    async def delete_zone(zone_id: uuid.UUID) -> bool:
        async with db.pool.acquire() as conn:
            try:
                result = await conn.execute(
                    "DELETE FROM public.zone WHERE zone_id = $1 RETURNING 1;",
                    zone_id
                )
                return bool(result)
            except asyncpg.ForeignKeyViolationError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete zone - it has associated devices"
                )
