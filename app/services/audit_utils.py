from uuid import UUID
from typing import Optional, Any, Dict
import logging

from app.models.user import User
from app.models.audit_log import AuditLogCreate
from app.repositories.audit_log import AuditLogRepo  # Предполагаем, что AuditLogRepo будет импортирован в __init__.py репозиториев или через depends

logger = logging.getLogger(__name__)

# Инициализация AuditLogRepo будет происходить через DI в реальном приложении.
# Для простоты здесь можно передавать инстанс или использовать глобальный.
# Однако, лучше всего, чтобы эта функция вызывалась из сервиса,
# у которого уже есть AuditLogRepo.
# Для примера сделаем ее статической и ожидаем, что AuditLogRepo будет доступен.


class AuditLogger:
    # Эту зависимость нужно будет инжектировать или сделать репозиторий доступным
    # Например, через app_context или передавая в каждый сервисный метод, где нужен аудит
    # Для простоты демонстрации, предположим, что сервисы будут иметь доступ к audit_repo.
    # Этот файл больше как набор вспомогательных функций/декораторов.

    @staticmethod
    async def log_action(
        audit_repo: AuditLogRepo,  # AuditLogRepo должен быть инжектирован
        user: User,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,  # Для логирования попыток и их результата
        error_message: Optional[str] = None
    ):
        """
        Универсальная функция для логирования действий в аудит.
        """
        action_data = details if details is not None else {}

        if not success and error_message:
            action_data["error"] = error_message
            action_status_prefix = "failed_"  # Например, "failed_create_user"
        else:
            action_status_prefix = ""

        log_entry = AuditLogCreate(
            user_id=user.user_id,
            action=f"{action_status_prefix}{action}",
            entity_type=entity_type,
            entity_id=entity_id,
            action_data=action_data
        )
        try:
            await audit_repo.create(log_entry)
        except Exception as e:
            # Критично! Логирование аудита не должно прерывать основную операцию.
            # Но нужно залогировать саму ошибку логирования.
            logger.error(f"Failed to write audit log for user {user.user_id}, action {action}: {e}")


# Пример использования как декоратора (более продвинутый вариант)
# def audit_log_decorator(action: str, entity_type: Optional[str] = None):
#     def decorator(func):
#         @wraps(func)
#         async def wrapper(self, *args, **kwargs):
#             # 'self' здесь - это инстанс сервиса
#             # Необходимо извлечь current_user и audit_repo из self или args/kwargs
#             # current_user = ...
#             # audit_repo = self.audit_repo
#             # entity_id_val = ... (из args или kwargs)
#             # details_val = ... (из args или kwargs)
#             try:
#                 result = await func(self, *args, **kwargs)
#                 await AuditLogger.log_action(
#                     audit_repo, current_user, action, entity_type, entity_id_val, details_val, success=True
#                 )
#                 return result
#             except HTTPException as http_exc:
#                 await AuditLogger.log_action(
#                     audit_repo, current_user, action, entity_type, entity_id_val, details_val,
#                     success=False, error_message=f"{http_exc.status_code}: {http_exc.detail}"
#                 )
#                 raise
#             except Exception as e:
#                 await AuditLogger.log_action(
#                     audit_repo, current_user, action, entity_type, entity_id_val, details_val,
#                     success=False, error_message=str(e)
#                 )
#                 raise
#         return wrapper
#     return decorator
