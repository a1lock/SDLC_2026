import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import validators
from app.common import PaginationParams, paginate
from app.deps import AdminUser, DbSession
from app.models import ROLE_ADMIN, User
from app.schemas import Page, UserCreate, UserOut, UserUpdate
from app.security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Безопасность"])

UserId = Annotated[int, Path(ge=1, le=validators.MAX_INT, description="Идентификатор пользователя")]


@router.get("", response_model=Page[UserOut], summary="Список учетных записей")
def list_users(session: DbSession, _admin: AdminUser, pagination: PaginationParams):
    rows, total = paginate(session, select(User), [User.id], pagination)
    return Page[UserOut](
        items=[UserOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("", response_model=UserOut, status_code=201, summary="Создать учетную запись")
def create_user(payload: UserCreate, session: DbSession, admin: AdminUser) -> User:
    user = User(
        login=payload.login,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Пользователь с таким логином уже существует") from None
    logger.info(
        "Создана учетная запись %s (роль %s) пользователем %s", user.login, user.role, admin.login
    )
    return user


@router.patch("/{user_id}", response_model=UserOut, summary="Изменить роль, статус или пароль")
def update_user(user_id: UserId, payload: UserUpdate, session: DbSession, admin: AdminUser) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Пользователь не найден")
    if user.id == admin.id and (
        payload.is_active is False or (payload.role is not None and payload.role != ROLE_ADMIN)
    ):
        raise HTTPException(409, "Нельзя отключить учетную запись или снять роль у самого себя")

    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    session.commit()
    logger.info("Изменена учетная запись %s пользователем %s", user.login, admin.login)
    return user
