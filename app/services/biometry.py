import uuid
from datetime import datetime
from typing import Optional

import httpx
from fastapi import HTTPException, UploadFile, status

from app.config import settings
# from app.db_session import db # Не используется
from app.models.biometry import (BiometryDB, BiometryCreate, BiometryDelete,  # Изменено Biometry на BiometryDB
                                 BiometryUpdate, BiometryResponse)  # Добавлен BiometryResponse
from app.models.user import AccessLevel, User
from app.repositories.biometry import BiometryRepo
from app.repositories.user import UserRepo
from app.repositories.audit_log import AuditLogRepo  # Добавлено
from app.services.audit_utils import AuditLogger  # Добавлено


class BiometryService:
    def __init__(self, user_repo: UserRepo, biometry_repo: BiometryRepo, audit_repo: AuditLogRepo):  # Добавлен audit_repo
        self.user_repo = user_repo
        self.biometry_repo = biometry_repo
        self.audit_repo = audit_repo  # Сохраняем

    async def create_biometry(self, biometry_data: BiometryCreate, face_photo: UploadFile, current_user: User) -> BiometryResponse:
        # Проверяем права на создание биометрии для biometry_data.user_id
        biometry_user = await self.user_repo.select_user(user_id=biometry_data.user_id)
        if not biometry_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {biometry_data.user_id} for biometry not found.")

        # Логика проверки прав на создание/изменение биометрии другого пользователя
        # Пользователь может создавать биометрию для себя
        # Админ/Рут могут создавать для других, если уровень целевого пользователя ниже
        if current_user.user_id != biometry_data.user_id:
            if current_user.access_level < AccessLevel.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient privileges to create biometry for another user."
                )
            if current_user.access_level != AccessLevel.ROOT and biometry_user.access_level >= current_user.access_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot create biometry for a user with an equal or higher access level."
                )

        # Убрал existing = await self.biometry_repo.get_biometry_by_user(biometry_data.user_id)
        # т.к. create_biometry в репозитории уже содержит UNIQUE constraint
        # Но если нужно специфическое сообщение, то можно оставить, но репозиторий кинет свою ошибку.

        cv_response = await self._get_cv_model_embedding(face_photo)
        if not cv_response or not all(k in cv_response for k in ['encrypted_embedding', 'iv', 'secure_hash']):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="CV model did not return expected data.")

        created_biometry_db = await self.biometry_repo.create_biometry(
            user_id=biometry_data.user_id,
            # Данные из CV модели, Убедитесь, что CV модель возвращает байты или строки, которые можно преобразовать в байты
            encrypted_embedding=bytes.fromhex(cv_response['encrypted_embedding']) if isinstance(cv_response['encrypted_embedding'], str) else cv_response['encrypted_embedding'],
            iv=bytes.fromhex(cv_response['iv']) if isinstance(cv_response['iv'], str) else cv_response['iv'],
            secure_hash=bytes.fromhex(cv_response['secure_hash']) if isinstance(cv_response['secure_hash'], str) else cv_response['secure_hash']
        )

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="create_biometry",
            entity_type="biometry", entity_id=created_biometry_db.biometry_id,
            details={"user_id": str(biometry_data.user_id)}
        )

        return BiometryResponse(
            biometry_id=created_biometry_db.biometry_id,
            user_id=created_biometry_db.user_id,
            created_at=created_biometry_db.created_at
            # algorithm_version - можно брать из конфига или CV-модели
        )

    async def update_biometry(self, biometry_data: BiometryUpdate, face_photo: UploadFile, current_user: User) -> BiometryResponse:
        target_biometry_db = await self.biometry_repo.get_biometry(biometry_data.biometry_id)  # Это BiometryDB
        if not target_biometry_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Biometry record not found.")

        target_user = await self.user_repo.select_user(user_id=target_biometry_db.user_id)
        if not target_user:  # Маловероятно, если есть биометрия, но все же
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User for biometry {target_biometry_db.user_id} not found.")

        self._check_biometry_permissions(current_user, target_user)

        cv_response = await self._get_cv_model_embedding(face_photo)
        if not cv_response or not all(k in cv_response for k in ['encrypted_embedding', 'iv', 'secure_hash']):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="CV model did not return expected data for update.")

        updated_biometry_db = await self.biometry_repo.update_biometry(
            biometry_id=biometry_data.biometry_id,
            encrypted_embedding=bytes.fromhex(cv_response['encrypted_embedding']) if isinstance(cv_response['encrypted_embedding'], str) else cv_response['encrypted_embedding'],
            iv=bytes.fromhex(cv_response['iv']) if isinstance(cv_response['iv'], str) else cv_response['iv'],
            secure_hash=bytes.fromhex(cv_response['secure_hash']) if isinstance(cv_response['secure_hash'], str) else cv_response['secure_hash']
        )

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="update_biometry",
            entity_type="biometry", entity_id=biometry_data.biometry_id,
            details={"user_id": str(target_user.user_id)}
        )
        return BiometryResponse(
            biometry_id=updated_biometry_db.biometry_id,
            user_id=updated_biometry_db.user_id,
            created_at=updated_biometry_db.created_at
        )

    async def delete_biometry(self, biometry_data: BiometryDelete, current_user: User):
        target_biometry_db = await self.biometry_repo.get_biometry(biometry_data.biometry_id)
        if not target_biometry_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Biometry record not found.")

        target_user = await self.user_repo.select_user(user_id=target_biometry_db.user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User for biometry {target_biometry_db.user_id} not found.")

        self._check_biometry_permissions(current_user, target_user)

        deleted = await self.biometry_repo.delete_biometry(biometry_data.biometry_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete biometry.")

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="delete_biometry",
            entity_type="biometry", entity_id=biometry_data.biometry_id,
            details={"user_id": str(target_user.user_id)}
        )
        return {"message": "Biometry deleted successfully"}

    async def get_biometry(self, user_id_str: str, current_user: User) -> BiometryResponse:  # user_id это UUID
        try:
            user_id_uuid = uuid.UUID(user_id_str)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user_id format.")

        target_user = await self.user_repo.select_user(user_id=user_id_uuid)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id_uuid} not found.")

        # Для просмотра биометрии (даже просто факта ее наличия) нужны права
        self._check_biometry_permissions(current_user, target_user, for_view=True)

        biometry_db_record = await self.biometry_repo.get_biometry_by_user(user_id_uuid)
        if not biometry_db_record:  # get_biometry_by_user уже кидает 404, но для унификации
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Biometry not found for this user.")

        return BiometryResponse(
            biometry_id=biometry_db_record.biometry_id,
            user_id=biometry_db_record.user_id,
            created_at=biometry_db_record.created_at
        )

    def _check_biometry_permissions(self, current_user: User, target_user: User, for_view: bool = False):
        if current_user.access_level == AccessLevel.ROOT:
            return

        # Пользователь может управлять/смотреть свою биометрию
        if current_user.user_id == target_user.user_id:
            return

        # Админ может управлять/смотреть биометрию пользователей с уровнем доступа ниже своего
        if current_user.access_level >= AccessLevel.ADMIN:
            if target_user.access_level < current_user.access_level:
                return
            else:  # Попытка админа на пользователя с равным или большим уровнем
                action = "view" if for_view else "modify"
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot {action} biometry of user with same or higher access level."
                )

        # Если не свой, не рут и не админ с достаточными правами
        action = "view" if for_view else "modify"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient privileges for biometry {action}."
        )

    async def _get_cv_model_embedding(self, face_photo: UploadFile) -> dict:
        # Эта функция остается без изменений, как вы ее предоставили.
        # Только убедитесь, что CV-модель возвращает 'encrypted_embedding', 'iv', 'secure_hash'
        # в виде hex-строк или байт. Если hex, то нужна конвертация bytes.fromhex().
        try:
            await face_photo.seek(0)
            files_payload = {
                'file': (
                    face_photo.filename,
                    face_photo.file,
                    face_photo.content_type
                )
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.cv.url}/process",
                    files=files_payload,
                    timeout=float(settings.cv.timeout)  # Убедимся что timeout это float
                )
                response.raise_for_status()
                cv_data = response.json()
                # Валидация ответа CV модели
                if not isinstance(cv_data, dict) or \
                   not all(key in cv_data for key in ['encrypted_embedding', 'iv', 'secure_hash']):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="CV model returned an invalid response format. Missing required keys."
                    )
                return cv_data
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="CV model service request timed out."
            )
        except httpx.HTTPStatusError as e:
            error_detail = f"CV model service returned an error: {e.response.status_code}."
            try:
                cv_error = e.response.json()
                if isinstance(cv_error, dict) and "detail" in cv_error: error_detail += f" Detail: {cv_error['detail']}"
                elif isinstance(cv_error, str): error_detail += f" Detail: {cv_error}"
                else: error_detail += f" Response: {e.response.text[:200]}"
            except Exception: error_detail += f" Response: {e.response.text[:200]}"
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=error_detail)
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"CV model service unavailable or network issue: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred while processing the image with CV model: {str(e)}"
            )
        finally:
            if face_photo and hasattr(face_photo, 'close') and callable(face_photo.close):
                await face_photo.close()
