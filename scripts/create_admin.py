import os
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import ROLE_ADMIN, User
from app.schemas import UserCreate
from app.security import hash_password


def main() -> int:
    login = os.environ.get("ADMIN_LOGIN", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not login or not password:
        print("ADMIN_LOGIN/ADMIN_PASSWORD не заданы — учетная запись администратора не создается.")
        return 0

    try:
        data = UserCreate(login=login, password=password, role=ROLE_ADMIN)
    except ValueError as error:
        print(f"Некорректные ADMIN_LOGIN/ADMIN_PASSWORD:\n{error}", file=sys.stderr)
        return 1

    with Session(get_engine()) as session:
        if session.scalar(select(User).where(User.login == data.login)) is not None:
            print(f"Администратор «{data.login}» уже существует.")
            return 0
        session.add(
            User(login=data.login, password_hash=hash_password(data.password), role=ROLE_ADMIN)
        )
        session.commit()
    print(f"Создан администратор «{data.login}».")
    return 0


if __name__ == "__main__":
    sys.exit(main())
