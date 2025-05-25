from uuid import UUID

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'Bearer'


class TokenData(BaseModel):
    uuid: UUID | None = None


class AuthForm(BaseModel):
    email: str
    password: str
