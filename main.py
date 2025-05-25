import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer

from app.config import settings
from app.db_session import db
from app.pkg.logging.logger import LOGGING
from app.pkg.logging.middlewares.logging import LoggingMiddleware
from app.routes import (
    auth as auth_router,
    openvpn as openvpn_roter,
    user as user_router,
    zone as zone_router,
    device as device_router,
    biometry as biometry_router,
    permission as permission_router,  # Новый
    access_log as access_log_router,  # Новый
    audit_log as audit_log_router    # Новый
)
from app.services.user import UserService  # Для root_create
from app.repositories.user import UserRepo  # Для root_create
from app.repositories.audit_log import AuditLogRepo  # Для root_create


def create_lifespan(user_service: UserService):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Подключение к БД
        await db.connect(settings.db.db_dsn)

        # Создание root-пользователя
        await user_service.root_create()

        yield

        # Отключение от БД
        await db.disconnect()

    return lifespan


user_service = UserService(UserRepo(), AuditLogRepo())
app = FastAPI(lifespan=create_lifespan(user_service))

uvicorn_access = logging.getLogger("uvicorn.access")
uvicorn_access.disabled = True

uvicorn.config.LOGGING_CONFIG = LOGGING


origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    LoggingMiddleware
)

app.include_router(auth_router.router)
app.include_router(user_router.router)
app.include_router(zone_router.router)
app.include_router(device_router.router)
app.include_router(biometry_router.router)
app.include_router(permission_router.router)   # Новый
app.include_router(access_log_router.router)  # Новый
app.include_router(audit_log_router.router)
app.include_router(openvpn_roter.router)


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host=settings.run.host,
        port=settings.run.port,
        reload=True
    )
