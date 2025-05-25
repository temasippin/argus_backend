from datetime import datetime
from enum import IntEnum
from typing import List, Union
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserResponse(BaseModel):
    user_id: UUID | str
    login: str
    full_name: str | None = None
    phone: str | None = None
    access_level: int
    employee_id: str | None = None
    department: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class AccessLevel(IntEnum):
    '''
    access_level = 0
    - Ничего не может

    access_level = 1
    - Может просматривать камеры

    access_level = 2
    - Все действия с камерами
    - Смотреть логи камер

    access_level = 3
    - Все действия с камерами
    - Смотреть логи камер
    - Смотреть глобальный конфиг
    - Может добавлять пользователей
    - Может изменять пользователей
    - Может удалять пользователей

    access_level = 4
    - Может всё
    '''
    GUEST = 0
    USER = 1
    MANAGER = 2
    ADMIN = 3
    ROOT = 4


class User(BaseModel):
    user_id: UUID
    login: str
    password: str
    full_name: str | None = None
    phone: str | None = None
    access_level: int
    employee_id: str | None = None
    department: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    login: str
    password: str
    full_name: str | None = None
    phone: str | None = None
    access_level: int = AccessLevel.GUEST
    employee_id: str | None = None
    department: str | None = None
    is_active: bool = True

    @field_validator('access_level')
    def validate_access_level(cls, v):
        if v > AccessLevel.ROOT:
            raise ValueError("Maximum allowed access level is ADMIN")
        return v


class UserUpdate(BaseModel):
    user_id: UUID
    login: str
    full_name: str | None = None
    phone: str | None = None
    password: str | None = None
    access_level: int | None = None
    employee_id: str | None = None
    department: str | None = None
    is_active: bool = True


class UserDelete(BaseModel):
    user_id: UUID


class UserLogin(BaseModel):
    login: str
    password: str
