import uuid
from datetime import datetime
from typing import List

import asyncpg
from fastapi import HTTPException, status

from app.db_session import db
from app.models.device import Device, DeviceCreate, DeviceUpdate
from app.models.user import AccessLevel, User


class DeviceRepo:
    @staticmethod
    async def create_device(device_data: DeviceCreate) -> uuid.UUID:
        async with db.pool.acquire() as conn:
            query = """
                INSERT INTO public.device (
                    name, ip, port, zone_id,
                    location_description, is_online
                ) VALUES (
                    $1, $2, $3, $4, $5, FALSE
                )
                RETURNING device_id;
            """
            try:
                device_id = await conn.fetchval(
                    query,
                    device_data.name,
                    device_data.ip,
                    device_data.port,
                    device_data.zone_id,
                    device_data.location_description
                )
                return device_id
            except asyncpg.ForeignKeyViolationError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid zone_id"
                )
            except asyncpg.PostgresError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {e}"
                )

    @staticmethod
    async def select_device(device_id: uuid.UUID) -> Device:
        async with db.pool.acquire() as conn:
            query = """
                SELECT * FROM public.device
                WHERE device_id = $1;
            """
            device = await conn.fetchrow(query, device_id)
            if not device:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Device not found"
                )
            return Device(
                device_id=device['device_id'],
                name=device['name'],
                ip=device['ip'],
                port=device['port'],
                zone_id=device['zone_id'],
                location_description=device['location_description'],
                is_online=device['is_online'],
                last_heartbeat=device['last_heartbeat'],
                created_at=device['created_at'],
                updated_at=device['updated_at']
            )

    @staticmethod
    async def select_device_by_ip_port(ip_config: dict) -> Device:
        async with db.pool.acquire() as conn:
            query = """
                SELECT * FROM public.device
                WHERE ip = $1 AND port = $2;
            """
            device = await conn.fetchrow(query, ip_config['ip'], ip_config['port'])
            if not device:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Device not found"
                )
            return Device(
                device_id=device['device_id'],
                name=device['name'],
                ip=device['ip'],
                port=device['port'],
                zone_id=device['zone_id'],
                location_description=device['location_description'],
                is_online=device['is_online'],
                last_heartbeat=device['last_heartbeat'],
                created_at=device['created_at'],
                updated_at=device['updated_at']
            )

    @staticmethod
    async def select_devices() -> List[Device]:
        async with db.pool.acquire() as conn:
            query = """
                SELECT d.*, z.name as zone_name
                FROM public.device d
                LEFT JOIN public.zone z ON d.zone_id = z.zone_id;
            """
            devices = await conn.fetch(query)
            return [
                Device(
                    device_id=device['device_id'],
                    name=device['name'],
                    ip=device['ip'],
                    port=device['port'],
                    zone_id=device['zone_id'],
                    location_description=device['location_description'],
                    is_online=device['is_online'],
                    last_heartbeat=device['last_heartbeat'],
                    created_at=device['created_at'],
                    updated_at=device['updated_at']
                ) for device in devices
            ]

    @staticmethod
    async def update_device(device_data: DeviceUpdate) -> Device:
        async with db.pool.acquire() as conn:
            updates = []
            params = []

            fields_to_update = {
                'name': device_data.name,
                'ip': device_data.ip,
                'port': device_data.port,
                'zone_id': device_data.zone_id,
                'location_description': device_data.location_description,
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
                UPDATE public.device
                SET {', '.join(updates)}
                WHERE device_id = $1
                RETURNING *;
            """

            try:
                updated_device = await conn.fetchrow(query, device_data.device_id, *params)
                return Device(
                    device_id=updated_device['device_id'],
                    name=updated_device['name'],
                    ip=updated_device['ip'],
                    port=updated_device['port'],
                    zone_id=updated_device['zone_id'],
                    location_description=updated_device['location_description'],
                    is_online=updated_device['is_online'],
                    last_heartbeat=updated_device['last_heartbeat'],
                    created_at=updated_device['created_at'],
                    updated_at=updated_device['updated_at']
                )
            except asyncpg.ForeignKeyViolationError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid zone_id"
                )
            except asyncpg.PostgresError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {e}"
                )

    @staticmethod
    async def update_device_status(device_id: uuid.UUID, is_online: bool) -> None:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.device
                SET
                    is_online = $1,
                    last_heartbeat = CASE WHEN $1 THEN NOW() ELSE last_heartbeat END
                WHERE device_id = $2;
                """,
                is_online,
                device_id
            )

    @staticmethod
    async def delete_device(device_id: uuid.UUID) -> bool:
        async with db.pool.acquire() as conn:
            try:
                result = await conn.execute(
                    "DELETE FROM public.device WHERE device_id = $1 RETURNING 1;",
                    device_id
                )
                return bool(result)
            except asyncpg.PostgresError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not delete device"
                )
