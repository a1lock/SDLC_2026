from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import StorageUnit, Supplier, User
from scripts import seed

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "suppliers",
    "materials",
    "units",
    "material_units",
    "documents",
    "storage_units",
    "users",
}


def test_migration_creates_all_tables_and_can_be_rolled_back():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        inspector = inspect(connection)
        assert EXPECTED_TABLES <= set(inspector.get_table_names())
        index_names = {i["name"] for i in inspector.get_indexes("storage_units")}
        assert "ix_storage_units_material_supplier" in index_names
        assert "ix_suppliers_bank_address" in {
            i["name"] for i in inspector.get_indexes("suppliers")
        }

        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}


def test_control_example_seed_is_idempotent(engine):
    with Session(engine) as session:
        seed.seed_control_example(session)
        seed.seed_control_example(session)
        session.commit()
        assert session.scalar(select(func.count()).select_from(StorageUnit)) == 4
        assert session.scalar(select(func.count()).select_from(Supplier)) == 3


def test_seed_users_and_bulk(engine):
    with Session(engine) as session:
        seed.seed_control_example(session)
        seed.seed_users(session, "Demo-password-1")
        seed.seed_users(session, "Demo-password-1")
        assert seed.seed_bulk(session, 25, batch_size=10) is True
        assert seed.seed_bulk(session, 25) is False
        session.commit()
        assert session.scalar(select(func.count()).select_from(User)) == 2
        assert session.scalar(select(func.count()).select_from(StorageUnit)) == 4 + 25
        assert session.scalar(select(func.count()).select_from(Supplier)) == 3 + 2000
