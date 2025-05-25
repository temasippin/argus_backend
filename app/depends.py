from typing import Annotated

from fastapi import Depends

# Репозитории
from app.repositories.user import UserRepo
from app.repositories.zone import ZoneRepo
from app.repositories.device import DeviceRepo
from app.repositories.biometry import BiometryRepo
from app.repositories.permission import PermissionRepo  # Новый
from app.repositories.access_log import AccessLogRepo  # Новый
from app.repositories.audit_log import AuditLogRepo   # Новый
from app.repositories.openvpn import OpenVPNRepo   # Новый

# Сервисы
from app.services.user import UserService
from app.services.zone import ZoneService
from app.services.device import DeviceService
from app.services.biometry import BiometryService
from app.services.permission import PermissionService  # Новый
from app.services.access_log import AccessLogService  # Новый
from app.services.audit_log import AuditLogService   # Новый
from app.services.openvpn import OpenVPNService   # Новый

from app.pkg.docker_manager import DockerManager

# --- Репозитории ---
UserRepoDependency = Annotated[UserRepo, Depends(UserRepo)]
ZoneRepoDependency = Annotated[ZoneRepo, Depends(ZoneRepo)]
DeviceRepoDependency = Annotated[DeviceRepo, Depends(DeviceRepo)]
BiometryRepoDependency = Annotated[BiometryRepo, Depends(BiometryRepo)]
PermissionRepoDependency = Annotated[PermissionRepo, Depends(PermissionRepo)]
AccessLogRepoDependency = Annotated[AccessLogRepo, Depends(AccessLogRepo)]
AuditLogRepoDependency = Annotated[AuditLogRepo, Depends(AuditLogRepo)]
OpenVPNRepoDependency = Annotated[OpenVPNRepo, Depends(OpenVPNRepo)]

DockerManagerDependency = Annotated[DockerManager, Depends(DockerManager)]


# --- Сервисы ---


# UserService
async def get_user_service(
    user_repo: UserRepoDependency,
    audit_repo: AuditLogRepoDependency  # Добавлено
):
    return UserService(user_repo, audit_repo)

UserServiceDependency = Annotated[UserService, Depends(get_user_service)]


# ZoneService
async def get_zone_service(
    user_repo: UserRepoDependency,
    zone_repo: ZoneRepoDependency,
    audit_repo: AuditLogRepoDependency  # Добавлено
):
    return ZoneService(user_repo, zone_repo, audit_repo)

ZoneServiceDependency = Annotated[ZoneService, Depends(get_zone_service)]


# PermissionService (новый)
async def get_permission_service(
    user_repo: UserRepoDependency,
    permission_repo: PermissionRepoDependency,
    device_repo: DeviceRepoDependency,
    zone_repo: ZoneRepoDependency,
    audit_repo: AuditLogRepoDependency
):
    return PermissionService(user_repo, permission_repo, device_repo, zone_repo, audit_repo)

PermissionServiceDependency = Annotated[PermissionService, Depends(get_permission_service)]


# DeviceService
async def get_device_service(
    user_repo: UserRepoDependency,
    zone_repo: ZoneRepoDependency,
    device_repo: DeviceRepoDependency,
    audit_repo: AuditLogRepoDependency,    # Добавлено
    access_log_repo: AccessLogRepoDependency,  # Добавлено
    permission_service: PermissionServiceDependency  # Добавлено (для проверки прав в wakeup)
):
    return DeviceService(user_repo, zone_repo, device_repo, audit_repo, access_log_repo, permission_service)

DeviceServiceDependency = Annotated[DeviceService, Depends(get_device_service)]


# BiometryService
async def get_biometry_service(
    user_repo: UserRepoDependency,
    biometry_repo: BiometryRepoDependency,
    audit_repo: AuditLogRepoDependency  # Добавлено
):
    return BiometryService(user_repo, biometry_repo, audit_repo)

BiometryServiceDependency = Annotated[BiometryService, Depends(get_biometry_service)]


# AccessLogService (новый)
async def get_access_log_service(
    user_repo: UserRepoDependency,
    access_log_repo: AccessLogRepoDependency,
    device_repo: DeviceRepoDependency,  # Для AccessLogService
    permission_service: PermissionServiceDependency,  # Для AccessLogService
    audit_repo: AuditLogRepoDependency  # AuditLogService тоже может что-то логировать
):
    return AccessLogService(user_repo, access_log_repo, device_repo, permission_service, audit_repo)

AccessLogServiceDependency = Annotated[AccessLogService, Depends(get_access_log_service)]


# AuditLogService (новый)
async def get_audit_log_service(
    user_repo: UserRepoDependency,
    audit_log_repo: AuditLogRepoDependency
):
    return AuditLogService(user_repo, audit_log_repo)

AuditLogServiceDependency = Annotated[AuditLogService, Depends(get_audit_log_service)]


def get_openvpn_service(
    user_repo: UserRepoDependency,
    openvpn_repo: OpenVPNRepoDependency,
    manager: DockerManagerDependency,
):
    return OpenVPNService(user_repo, openvpn_repo, manager)


OpenVPNServiceDependency = Annotated[OpenVPNService, Depends(get_openvpn_service)]
