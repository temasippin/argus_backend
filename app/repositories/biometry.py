import uuid
from datetime import datetime
from typing import Optional

import asyncpg
from fastapi import HTTPException, status

from app.db_session import db
from app.models.biometry import BiometryDB
from app.models.user import AccessLevel, User


class BiometryRepo:
    @staticmethod
    async def create_biometry(
        user_id: uuid.UUID,
        encrypted_embedding: bytes,
        iv: bytes,
        secure_hash: bytes
    ) -> BiometryDB:
        async with db.pool.acquire() as conn:
            query = """
                INSERT INTO public.biometry (
                    user_id, encrypted_embedding, iv, secure_hash
                ) VALUES (
                    $1, $2, $3, $4
                )
                RETURNING *;
            """
            try:
                biometry = await conn.fetchrow(
                    query,
                    user_id,
                    encrypted_embedding,
                    iv,
                    secure_hash
                )
                return BiometryDB(
                    biometry_id=biometry['biometry_id'],
                    user_id=biometry['user_id'],
                    encrypted_embedding=biometry['encrypted_embedding'],
                    iv=biometry['iv'],
                    secure_hash=biometry['secure_hash'],
                    created_at=biometry['created_at']
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already has biometry data"
                )
            except asyncpg.ForeignKeyViolationError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User not found"
                )
            except asyncpg.PostgresError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {e}"
                )

    @staticmethod
    async def get_biometry(biometry_id: uuid.UUID) -> BiometryDB:
        async with db.pool.acquire() as conn:
            query = """
                SELECT * FROM public.biometry
                WHERE biometry_id = $1;
            """
            biometry = await conn.fetchrow(query, biometry_id)
            if not biometry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Biometry not found"
                )
            return BiometryDB(
                biometry_id=biometry['biometry_id'],
                user_id=biometry['user_id'],
                encrypted_embedding=biometry['encrypted_embedding'],
                iv=biometry['iv'],
                secure_hash=biometry['secure_hash'],
                created_at=biometry['created_at']
            )

    @staticmethod
    async def get_biometry_by_user(user_id: uuid.UUID) -> Optional[BiometryDB]:
        async with db.pool.acquire() as conn:
            query = """
                SELECT * FROM public.biometry
                WHERE user_id = $1;
            """
            biometry = await conn.fetchrow(query, user_id)
            if not biometry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Biometry not found for this user"
                )
            return BiometryDB(
                biometry_id=biometry['biometry_id'],
                user_id=biometry['user_id'],
                encrypted_embedding=biometry['encrypted_embedding'],
                iv=biometry['iv'],
                secure_hash=biometry['secure_hash'],
                created_at=biometry['created_at']
            )

    @staticmethod
    async def update_biometry(
        biometry_id: uuid.UUID,
        encrypted_embedding: bytes,
        iv: bytes,
        secure_hash: bytes
    ) -> BiometryDB:
        async with db.pool.acquire() as conn:
            query = """
                UPDATE public.biometry
                SET
                    encrypted_embedding = $1,
                    iv = $2,
                    secure_hash = $3
                WHERE biometry_id = $4
                RETURNING *;
            """
            try:
                biometry = await conn.fetchrow(
                    query,
                    encrypted_embedding,
                    iv,
                    secure_hash,
                    biometry_id
                )
                return BiometryDB(
                    biometry_id=biometry['biometry_id'],
                    user_id=biometry['user_id'],
                    encrypted_embedding=biometry['encrypted_embedding'],
                    iv=biometry['iv'],
                    secure_hash=biometry['secure_hash'],
                    created_at=biometry['created_at']
                )
            except asyncpg.PostgresError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {e}"
                )

    @staticmethod
    async def delete_biometry(biometry_id: uuid.UUID) -> bool:
        async with db.pool.acquire() as conn:
            try:
                result = await conn.execute(
                    "DELETE FROM public.biometry WHERE biometry_id = $1 RETURNING 1;",
                    biometry_id
                )
                return bool(result)
            except asyncpg.PostgresError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not delete biometry"
                )

    @staticmethod
    async def get_user(user_id: uuid.UUID) -> User:
        async with db.pool.acquire() as conn:
            query = """
                SELECT * FROM public.user
                WHERE user_id = $1;
            """
            user = await conn.fetchrow(query, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return User(
                user_id=user['user_id'],
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

    @staticmethod
    async def min_user_access_level(user: User):
        if user.access_level < AccessLevel.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges"
            )
