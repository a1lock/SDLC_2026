import argparse
import random
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import (
    ROLE_ADMIN,
    ROLE_STOREKEEPER,
    Document,
    Material,
    MaterialUnit,
    StorageUnit,
    Supplier,
    Unit,
    User,
)
from app.security import hash_password
from app.validators import make_inn10

KILOGRAM, METER, LITER = 166, 6, 112  # коды ОКЕИ
DOC_INVOICE, DOC_UPD = 1, 2

UNITS = [
    (KILOGRAM, "килограмм", "кг"),
    (METER, "метр", "м"),
    (LITER, "литр", "л"),
    (168, "тонна", "т"),
    (796, "штука", "шт"),
    (55, "квадратный метр", "м2"),
    (113, "кубический метр", "м3"),
]
DOCUMENTS = [(DOC_INVOICE, "Накладная"), (DOC_UPD, "Универсальный передаточный документ")]

_BANK_MOSCOW = ("101000", "Москва", "ул. Банковская", "5")
_BANK_SPB = ("190000", "Санкт-Петербург", "ул. Финансовая", "12")

# Таблица 19 ТЗ: поставщики.
SUPPLIERS = [
    (
        101,
        "ООО «Металлоторг»",
        "7707123458",
        ("125009", "Москва", "ул. Тверская", "10"),
        _BANK_MOSCOW,
    ),
    (102, "АО «СтальСнаб»", "5047112238", ("141400", "Химки", "ул. Заводская", "3"), _BANK_MOSCOW),
    (
        103,
        "ООО «Прокат-Сервис»",
        "7728345613",
        ("196084", "Санкт-Петербург", "пр. Прокатный", "7"),
        _BANK_SPB,
    ),
]

# Таблица 20 ТЗ: материалы и допустимые единицы.
MATERIALS = [
    (1001, "10", "01", "Лист стальной 3 мм", KILOGRAM),
    (1002, "10", "05", "Кабель медный", METER),
    (1003, "10", "03", "Масло трансформаторное", LITER),
]

# Таблица 20 ТЗ: поступления (номер ордера, дата, поставщик, материал, ед., кол-во, цена).
RECEIPTS = [
    ("1", date(2026, 12, 1), 101, 1001, KILOGRAM, Decimal("500.000"), Decimal("85.50")),
    ("2", date(2026, 12, 3), 101, 1001, KILOGRAM, Decimal("300.000"), Decimal("86.00")),
    ("3", date(2026, 12, 5), 102, 1001, KILOGRAM, Decimal("1000.000"), Decimal("84.00")),
    ("4", date(2026, 12, 6), 103, 1002, METER, Decimal("500.000"), Decimal("245.00")),
]


def seed_control_example(session: Session) -> None:
    for code, name, short_name in UNITS:
        session.merge(Unit(unit_code=code, name=name, short_name=short_name))
    for code, name in DOCUMENTS:
        session.merge(Document(doc_code=code, name=name))

    for code, name, inn, legal, bank in SUPPLIERS:
        session.merge(
            Supplier(
                supplier_code=code,
                name=name,
                inn=inn,
                legal_zip=legal[0],
                legal_city=legal[1],
                legal_street=legal[2],
                legal_house=legal[3],
                bank_zip=bank[0],
                bank_city=bank[1],
                bank_street=bank[2],
                bank_house=bank[3],
                bank_account=f"40702810100000000{code}",
            )
        )

    for code, class_code, group_code, name, unit_code in MATERIALS:
        session.merge(
            Material(material_code=code, class_code=class_code, group_code=group_code, name=name)
        )
        session.flush()
        session.merge(MaterialUnit(material_code=code, unit_code=unit_code))
    session.flush()

    for number, order_date, supplier, material, unit, quantity, price in RECEIPTS:
        exists = session.scalar(
            select(StorageUnit.id).where(
                StorageUnit.order_number == number, StorageUnit.order_date == order_date
            )
        )
        if exists is None:
            session.add(
                StorageUnit(
                    order_number=number,
                    order_date=order_date,
                    supplier_code=supplier,
                    balance_account="60.01",
                    doc_code=DOC_INVOICE,
                    doc_number=f"Н-{number}",
                    material_code=material,
                    unit_code=unit,
                    material_account="10.01",
                    quantity=quantity,
                    unit_price=price,
                )
            )
    session.flush()


def seed_users(session: Session, password: str) -> None:
    for login, role in (("admin", ROLE_ADMIN), ("storekeeper", ROLE_STOREKEEPER)):
        if session.scalar(select(User).where(User.login == login)) is None:
            session.add(User(login=login, password_hash=hash_password(password), role=role))
    session.flush()


def seed_bulk(session: Session, count: int, seed: int = 42, batch_size: int = 5000) -> bool:
    first_supplier, supplier_total = 10_000, 2_000
    first_material, material_total = 20_000, 1_000
    if session.get(Supplier, first_supplier) is not None:
        return False

    rng = random.Random(seed)
    session.execute(
        insert(Supplier),
        [
            {
                "supplier_code": first_supplier + i,
                "name": f"Поставщик {i + 1}",
                "inn": make_inn10(str(770_000_000 + i)),
                "legal_zip": "125009",
                "legal_city": "Москва",
                "legal_street": f"ул. Тестовая {i % 50 + 1}",
                "legal_house": str(i % 200 + 1),
                "bank_zip": "101000",
                "bank_city": "Москва",
                "bank_street": f"ул. Банковская {i % 20 + 1}",
                "bank_house": str(i % 30 + 1),
                "bank_account": f"407028101{i:011d}",
            }
            for i in range(supplier_total)
        ],
    )
    session.execute(
        insert(Material),
        [
            {
                "material_code": first_material + i,
                "class_code": "10",
                "group_code": f"{i % 50:02d}",
                "name": f"Материал {i + 1}",
            }
            for i in range(material_total)
        ],
    )
    session.execute(
        insert(MaterialUnit),
        [
            {"material_code": first_material + i, "unit_code": KILOGRAM}
            for i in range(material_total)
        ],
    )

    start = date(2023, 1, 1)
    for offset in range(0, count, batch_size):
        rows = [
            {
                "order_number": f"B{n + 1}",
                "order_date": start + timedelta(days=rng.randrange(1400)),
                "supplier_code": first_supplier + rng.randrange(supplier_total),
                "balance_account": "60.01",
                "doc_code": DOC_INVOICE,
                "doc_number": f"Н-{n + 1}",
                "material_code": first_material + rng.randrange(material_total),
                "unit_code": KILOGRAM,
                "material_account": "10.01",
                "quantity": Decimal(rng.randrange(1, 500_000)) / 1000,
                "unit_price": Decimal(rng.randrange(100, 100_000)) / 100,
            }
            for n in range(offset, min(offset + batch_size, count))
        ]
        session.execute(insert(StorageUnit), rows)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Заполнение БД тестовыми данными")
    parser.add_argument("--users-password", help="создать admin и storekeeper с этим паролем")
    parser.add_argument("--bulk", type=int, default=0, help="число ЕХ нагрузочного набора")
    args = parser.parse_args(argv)

    with Session(get_engine()) as session:
        seed_control_example(session)
        print("Контрольный пример (п. 6.6) загружен.")
        if args.users_password:
            seed_users(session, args.users_password)
            print("Учетные записи admin и storekeeper созданы (если их не было).")
        if args.bulk > 0:
            loaded = seed_bulk(session, args.bulk)
            print(
                f"Нагрузочный набор: {args.bulk} ЕХ загружено."
                if loaded
                else "Нагрузочный набор уже загружен."
            )
        session.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
