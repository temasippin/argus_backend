from datetime import datetime, timedelta

import jwt
import pytz
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Hasher:
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(password):
        return pwd_context.hash(password)

    def create_access_token(data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(pytz.timezone('Europe/Moscow')) + timedelta(minutes=expires_delta)
        else:
            expire = datetime.now(pytz.timezone('Europe/Moscow')) + timedelta(minutes=settings.hasher.access_token_expire)
        to_encode.update({"expire": expire.isoformat()})
        encoded_jwt = jwt.encode(to_encode, settings.hasher.hash_key, algorithm=settings.hasher.algorithm)
        return encoded_jwt

    def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(pytz.timezone('Europe/Moscow')) + timedelta(minutes=expires_delta)
        else:
            expire = datetime.now(pytz.timezone('Europe/Moscow')) + timedelta(minutes=settings.hasher.refresh_token_expire)
        to_encode.update({"expire": expire.isoformat()})
        encoded_jwt = jwt.encode(to_encode, settings.hasher.hash_key, algorithm=settings.hasher.algorithm)
        return encoded_jwt
