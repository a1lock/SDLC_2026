import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import User
from app.schemas import LoginIn, TokenOut, UserOut
from app.security import create_access_token, dummy_hash, get_throttle, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Безопасность"])

INVALID_CREDENTIALS = "Неверный логин или пароль"


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Ф6. Вход, получение токена",
    responses={
        401: {"description": INVALID_CREDENTIALS},
        429: {"description": "Вход заблокирован"},
    },
)
def login(payload: LoginIn, session: DbSession) -> TokenOut:
    throttle = get_throttle()
    wait = throttle.seconds_locked(payload.login)
    if wait > 0:
        logger.warning("Вход заблокирован: логин=%s, осталось %s с", payload.login, wait)
        raise HTTPException(
            status_code=429,
            detail="Слишком много неудачных попыток входа. Повторите позже.",
            headers={"Retry-After": str(wait)},
        )

    user = session.scalar(select(User).where(User.login == payload.login))
    password_ok = verify_password(payload.password, user.password_hash if user else dummy_hash())
    if user is None or not password_ok or not user.is_active:
        throttle.register_failure(payload.login)
        logger.warning("Неудачная попытка входа: логин=%s", payload.login)
        raise HTTPException(
            status_code=401,
            detail=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    throttle.reset(payload.login)
    token, expires_in = create_access_token(user)
    logger.info("Вход выполнен: пользователь=%s, роль=%s", user.login, user.role)
    return TokenOut(access_token=token, expires_in=expires_in, role=user.role)


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
def me(user: CurrentUser) -> User:
    return user
