import random
import string

from dotenv import load_dotenv
from pydantic import BaseModel, Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class RunConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class OpenVPN(BaseModel):
    container_name: str = "openvpn_client"
    path_host: str = "./openvpn_conf_active/client.ovpn"


class DatabaseConfig(BaseModel):
    username: str
    password: str
    host: str
    port: str  # Может быть int, но DSN ожидает строку
    db: str

    @property
    def db_dsn(self) -> str:  # Явно указываем тип возврата
        # Ensure port is string for DSN
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.db}?sslmode=disable"

    # Эти поля больше относятся к HasherConfig или общим настройкам JWT, а не к БД
    # hash_key: str = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(64))
    # algorithm: str = "HS256"
    # access_token_expire: int = 30
    echo: bool = False
    echo_pool: bool = False
    pool_size: int = 50
    max_overflow: int = 10


class HasherConfig(BaseModel):
    hash_key: str = Field(default_factory=lambda: ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(64)))
    algorithm: str = "HS256"
    access_token_expire: int = 30  # минуты
    refresh_token_expire: int = 60 * 24 * 30  # минуты (30 дней)


class RootConfig(BaseModel):
    login: str = "root"  # Можно задать дефолтные значения
    password: str = "rootpassword"  # Замените на безопасный способ установки или генерации


class CVConfig(BaseModel):
    url: str
    timeout: float = 10.0  # Изменено на float, значение по умолчанию


class BiometrySettings(BaseModel):  # Изменено на BaseModel для лучшей практики
    min_embedding_size: int = 128


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=('.env', '.env.local'),  # Добавлен .env.local для переопределения
        case_sensitive=False,
        env_nested_delimiter='__',
        env_prefix='BACKEND_CONFIG__',  # Единый префикс
        env_file_encoding='utf-8',
        extra='ignore'  # Игнорировать лишние переменные окружения
    )
    run: RunConfig = Field(default_factory=RunConfig)  # Используем Field с default_factory
    openvpn: OpenVPN
    biometry: BiometrySettings = Field(default_factory=BiometrySettings)
    db: DatabaseConfig
    hasher: HasherConfig = Field(default_factory=HasherConfig)  # default_factory для генерации hash_key
    root: RootConfig
    cv: CVConfig


settings = Settings()

# Для отладки можно вывести настройки при старте, если это не продакшен
# import json
# print("Loaded settings:", json.dumps(settings.model_dump(), indent=2))
