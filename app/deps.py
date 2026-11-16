from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ROLE_ADMIN, User
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False, description="Токен из POST /auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(status_code=401, detail=message, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: DbSession,
) -> User:
    if credentials is None:
        raise _unauthorized("Требуется аутентификация")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _unauthorized("Недействительный или просроченный токен") from None
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Учетная запись не найдена или отключена")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Недостаточно прав для выполнения операции")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
