import uuid
from datetime import datetime, timedelta
from typing import List
import asyncpg
import pytz
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
# from httpx import AsyncClient, Timeout, _exceptions # Не используется здесь

from app.config import settings
from app.db_session import db  # Не используется здесь напрямую, все через репозиторий
from app.models.user import (AccessLevel, User, UserCreate, UserDelete,
                             UserLogin, UserUpdate, UserResponse)  # Добавлен UserResponse
from app.pkg.hasher import Hasher
from app.repositories.user import UserRepo
from app.repositories.audit_log import AuditLogRepo  # Добавлено
from app.services.audit_utils import AuditLogger  # Добавлено


class UserService:
    def __init__(self, user_repo: UserRepo, audit_repo: AuditLogRepo):  # Добавлен audit_repo
        self.user_repo = user_repo
        self.audit_repo = audit_repo  # Сохраняем

    async def create_user(self, user_data: UserCreate, current_user: User) -> UserResponse:
        await self.user_repo.min_admin_access_level(current_user)

        # Доп. проверка, что админ не создает юзера с правами выше или равными себе (если он не ROOT)
        if current_user.access_level != AccessLevel.ROOT and user_data.access_level >= current_user.access_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create users with an access level equal to or higher than your own."
            )

        user_id = await self.user_repo.create_user(user_data, current_user)
        created_user_full = await self.user_repo.select_user(user_id=user_id)  # Получаем полного юзера для аудита

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="create_user",
            entity_type="user", entity_id=user_id,
            details={"login": user_data.login, "access_level": user_data.access_level}
        )
        # Возвращаем UserResponse, а не User, т.к. пароль не должен утекать
        return UserResponse.model_validate(created_user_full)

    async def update_user(self, user_data: UserUpdate, current_user: User) -> UserResponse:
        await self.user_repo.min_admin_access_level(current_user)

        selected_user = await self.user_repo.select_user(user_id=user_data.user_id)
        if not selected_user:  # user_repo.select_user уже бросает 404, но для ясности
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to update not found.")

        # Доп. проверка прав: нельзя изменять пользователя с уровнем доступа выше или равным своему, если ты не ROOT
        if current_user.access_level != AccessLevel.ROOT and selected_user.access_level >= current_user.access_level:
            if selected_user.user_id != current_user.user_id:  # Себя рут может менять, других с таким же уровнем нет
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot update user with an access level equal to or higher than your own."
                )

        # Нельзя повышать уровень доступа пользователя выше своего собственного (если ты не ROOT)
        if user_data.access_level is not None and current_user.access_level != AccessLevel.ROOT and \
           user_data.access_level > current_user.access_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot set user access level higher than your own."
            )

        updated_user_internal = await self.user_repo.update_user(user_data, selected_user, current_user)

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="update_user",
            entity_type="user", entity_id=user_data.user_id,
            details={"changes": user_data.model_dump(exclude_unset=True, exclude={'password'})}  # Пароль не логируем
        )
        return UserResponse.model_validate(updated_user_internal)

    async def delete_user(self, user_data: UserDelete, current_user: User):
        await self.user_repo.min_admin_access_level(current_user)

        selected_user = await self.user_repo.select_user(user_id=user_data.user_id)
        if not selected_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to delete not found.")

        # user_repo.delete_user уже содержит проверки прав, но дублируем для ясности
        if current_user.access_level != AccessLevel.ROOT and selected_user.access_level >= current_user.access_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete user with an access level equal to or higher than your own."
            )
        if current_user.user_id == selected_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-deletion is not allowed via this endpoint."
            )

        deleted = await self.user_repo.delete_user(selected_user, current_user)
        if not deleted:  # На случай если delete_user вернет False без исключения
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User deletion failed.")

        await AuditLogger.log_action(
            self.audit_repo, current_user, action="delete_user",
            entity_type="user", entity_id=user_data.user_id,
            details={"deleted_user_login": selected_user.login}
        )
        return {"message": "User deleted successfully"}

    async def login(self, user_login: UserLogin):
        # Логин не логируем в аудит здесь, т.к. это действие пользователя, а не админа.
        # Можно логировать успешные/неуспешные попытки входа в отдельный security_log, если нужно.
        selected_user = await self.user_repo.select_user(login=user_login.login)  # может кинуть 404

        if not selected_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='User account is inactive.'
            )

        check_verify = Hasher.verify_password(user_login.password, selected_user.password)
        if check_verify:
            return selected_user.user_id
        else:
            # Неудачная попытка входа - это событие безопасности, не административное
            # Можно логировать в access_log с event_type="login_failed" или в отдельный лог
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,  # Изменено с 403 на 401 для логина
                detail='Incorrect login or password.'
            )

    async def select_all_users(self, current_user: User) -> List[UserResponse]:
        await self.user_repo.min_admin_access_level(current_user)
        users_internal = await self.user_repo.select_users()
        # Преобразуем User в UserResponse
        return [UserResponse.model_validate(user) for user in users_internal]

    async def root_create(self):
        # Этот метод вызывается при старте, current_user нет. Логировать можно, но user_id будет системным.
        try:
            root_user_exists = await self.user_repo.select_user(login=settings.root.login)
            # Если дошли сюда, рут уже есть. Ничего не делаем.
        except HTTPException as e:
            if e.status_code == status.HTTP_404_NOT_FOUND:  # Только если рута нет
                root_user_data = UserCreate(
                    login=settings.root.login,
                    password=settings.root.password,
                    access_level=AccessLevel.ROOT,
                    is_active=True
                )
                # Для create_user нужен current_user, но для рута он None. root=True это обрабатывает.
                user_id = await self.user_repo.create_user(root_user_data, current_user=None, root=True)

                # Логирование создания рута. Т.к. current_user нет, можно указать user_id самого рута
                # или специальный system_user_id
                if user_id and self.audit_repo:  # Проверяем, что audit_repo доступен
                    # Получаем созданного рута, чтобы использовать его user_id для лога
                    created_root_user = await self.user_repo.select_user(user_id=user_id)
                    await AuditLogger.log_action(
                        self.audit_repo, created_root_user, action="create_root_user",
                        entity_type="user", entity_id=user_id,
                        details={"login": root_user_data.login}
                    )
            else:
                raise  # Другая ошибка при проверке рута
