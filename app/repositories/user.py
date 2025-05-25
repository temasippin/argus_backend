import uuid
from datetime import datetime, timedelta
from typing import List

import asyncpg
import pytz
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from httpx import AsyncClient, Timeout, _exceptions

from app.config import settings
from app.db_session import db
from app.models.user import (AccessLevel, User, UserCreate, UserDelete,
                             UserLogin, UserUpdate)
from app.pkg.hasher import Hasher


class UserRepo:
    @staticmethod
    async def create_user(user_data: UserCreate, current_user: User | None, root: bool = False):
        if not root:
            if user_data.access_level >= current_user.access_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot create users with same access level or higher"
                )
        async with db.pool.acquire() as conn:
            query = """
                INSERT INTO public.user (
                    login,
                    password,
                    full_name,
                    phone,
                    access_level,
                    employee_id,
                    department,
                    is_active,
                    created_at,
                    updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8,
                    COALESCE($9, NOW()),
                    NULL
                )
                ON CONFLICT (login)
                DO NOTHING
                RETURNING user_id;
            """
            params = (
                user_data.login,
                Hasher.get_password_hash(user_data.password),
                user_data.full_name,
                user_data.phone,
                user_data.access_level,
                user_data.employee_id,
                user_data.department,
                user_data.is_active,
                datetime.now()
            )
            try:
                user_id = await conn.fetchval(query, *params)
                if not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f'User {user_data.login} already exists'
                    )
                return user_id
            except asyncpg.PostgresError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {e}"
                )

    @staticmethod
    async def select_user(login: str | None = None, user_id: uuid.UUID | str | None = None) -> User:
        if not any([login, user_id]):
            raise ValueError("Either login or user_id must be provided")

        async with db.pool.acquire() as conn:
            query = """
                SELECT
                    *
                FROM public.user
                WHERE
                    ($1::uuid IS NOT NULL AND user_id = $1) OR
                    ($2::text IS NOT NULL AND login = $2)
                LIMIT 1;
            """

            params = (user_id, login)

            try:
                user = await conn.fetchrow(query, *params)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found"
                    )

                return User(
                    user_id=str(user['user_id']),
                    login=user['login'],
                    password=user['password'],
                    full_name=user['full_name'],
                    phone=user['phone'],
                    access_level=user['access_level'],
                    employee_id=user['employee_id'],
                    department=user['department'],
                    is_active=user['is_active'],
                    created_at=user['created_at'],
                    updated_at=user['updated_at']
                )

            except asyncpg.PostgresError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {e}"
                )

    @staticmethod
    async def select_users() -> List[User]:
        async with db.pool.acquire() as conn:
            query = '''
                SELECT
                    *
                FROM public.user;
            '''
            users = await conn.fetch(query)
            return [
                User(
                    user_id=str(user['user_id']),
                    login=user['login'],
                    password=user['password'],
                    full_name=user['full_name'],
                    phone=user['phone'],
                    access_level=user['access_level'],
                    employee_id=user['employee_id'],
                    department=user['department'],
                    is_active=user['is_active'],
                    created_at=user['created_at'],
                    updated_at=user['updated_at']
                ) for user in users
            ]

    @staticmethod
    async def update_user(user_data: UserUpdate, selected_user: User, current_user: User) -> User:
        if selected_user.access_level >= current_user.access_level and current_user.access_level != AccessLevel.ROOT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update user with same access level or higher"
            )
        async with db.pool.acquire() as conn:
            updates = []
            params = []

            fields_to_update = {
                'login': user_data.login,
                'password': Hasher.get_password_hash(user_data.password) if user_data.password else None,
                'full_name': user_data.full_name,
                'phone': user_data.phone,
                'access_level': user_data.access_level,
                'employee_id': user_data.employee_id,
                'department': user_data.department,
                'is_active': user_data.is_active,
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
                UPDATE public.user
                SET {', '.join(updates)}
                WHERE user_id = $1
                RETURNING
                    user_id, login, password, full_name, phone,
                    access_level, employee_id, department,
                    is_active, created_at, updated_at;
            """

            try:
                updated_user = await conn.fetchrow(query, user_data.user_id, *params)
                if not updated_user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"User with id {user_data.user_id} not found"
                    )

                return User(
                    user_id=updated_user['user_id'],
                    login=updated_user['login'],
                    password=updated_user['password'],
                    full_name=updated_user['full_name'],
                    phone=updated_user['phone'],
                    access_level=updated_user['access_level'],
                    employee_id=updated_user['employee_id'],
                    department=updated_user['department'],
                    is_active=updated_user['is_active'],
                    created_at=updated_user['created_at'],
                    updated_at=updated_user['updated_at']
                )

            except asyncpg.UniqueViolationError:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Login {user_data.login} already exists"
                )
            except asyncpg.PostgresError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {e}"
                )

    @staticmethod
    async def delete_user(selected_user: User, current_user: User) -> bool:
        if selected_user.access_level >= current_user.access_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete user with same access level or higher"
            )
        if current_user.user_id == selected_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-deletion is not allowed"
            )
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute(
                        "DELETE FROM public.biometry WHERE user_id = $1",
                        selected_user.user_id
                    )

                    result = await conn.execute(
                        """
                        DELETE FROM public.user
                        WHERE user_id = $1
                        RETURNING 1;
                        """,
                        selected_user.user_id
                    )

                    if not result:
                        return False

                    return True

                except asyncpg.PostgresError as e:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Could not delete user"
                    )

    @staticmethod
    async def rights_exception():
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail='You receive an error, stating that you have insufficient user rights')

    @staticmethod
    async def min_user_access_level(user: User):
        if user.access_level < AccessLevel.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges"
            )

    @staticmethod
    async def min_manager_access_level(user: User):
        if user.access_level < AccessLevel.MANAGER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges"
            )

    @staticmethod
    async def min_admin_access_level(user: User):
        if user.access_level < AccessLevel.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges"
            )

    @staticmethod
    async def min_root_access_level(user: User):
        if user.access_level < AccessLevel.ROOT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges"
            )
