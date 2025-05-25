import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import asyncpg

from app.db_session import db
from app.models.openvpn import VpnConfigDB


class OpenVPNRepo:
    async def get_configuration(self) -> Optional[VpnConfigDB]:
        async with db.pool.acquire() as conn:
            query = "SELECT * FROM public.openvpn LIMIT 1;"
            row = await conn.fetchrow(query)
            if row:
                return VpnConfigDB.model_validate(dict(row))
            return None

    async def upsert_configuration(
        self,
        vpn_enabled: Optional[bool] = None,
        vpn_config_content: Optional[str] = None
    ) -> VpnConfigDB:
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                existing_config = await conn.fetchrow("SELECT openvpn_id FROM public.openvpn LIMIT 1;")

                current_time = datetime.now()
                fields_to_update = {}
                if vpn_enabled is not None:
                    fields_to_update['vpn_enabled'] = vpn_enabled
                if vpn_config_content is not None:
                    # Сохраняем как JSON объект в JSONB поле
                    fields_to_update['vpn_config'] = json.dumps({"ovpn_content": vpn_config_content})

                if existing_config:
                    openvpn_id = existing_config['openvpn_id']
                    if not fields_to_update:  # Если нет данных для обновления, просто получаем текущую
                        row = await conn.fetchrow("SELECT * FROM public.openvpn WHERE openvpn_id = $1;", openvpn_id)
                        return VpnConfigDB.model_validate(dict(row))

                    set_clauses = []
                    params = []
                    param_idx = 1
                    for key, value in fields_to_update.items():
                        set_clauses.append(f"{key} = ${param_idx}")
                        params.append(value)
                        param_idx += 1

                    set_clauses.append(f"updated_at = ${param_idx}")
                    params.append(current_time)
                    param_idx += 1

                    params.append(openvpn_id)

                    query = f"""
                        UPDATE public.openvpn
                        SET {', '.join(set_clauses)}
                        WHERE openvpn_id = ${param_idx}
                        RETURNING *;
                    """
                    updated_row = await conn.fetchrow(query, *params)
                    return VpnConfigDB.model_validate(dict(updated_row))
                else:
                    # Создаем новую запись, если не существует
                    new_openvpn_id = uuid.uuid4()
                    vpn_enabled_val = vpn_enabled if vpn_enabled is not None else False
                    vpn_config_val = json.dumps({"ovpn_content": vpn_config_content}) if vpn_config_content else None

                    query = """
                        INSERT INTO public.openvpn (openvpn_id, vpn_enabled, vpn_config, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $4)
                        RETURNING *;
                    """
                    new_row = await conn.fetchrow(query, new_openvpn_id, vpn_enabled_val, vpn_config_val, current_time)
                    if not new_row:
                        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create configuration")
                    return VpnConfigDB.model_validate(dict(new_row))
