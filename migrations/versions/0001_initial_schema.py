from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("supplier_code", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("inn", sa.String(12), nullable=False),
        sa.Column("legal_zip", sa.String(10), nullable=False),
        sa.Column("legal_city", sa.String(100), nullable=False),
        sa.Column("legal_street", sa.String(150), nullable=False),
        sa.Column("legal_house", sa.String(20), nullable=False),
        sa.Column("bank_zip", sa.String(10), nullable=False),
        sa.Column("bank_city", sa.String(100), nullable=False),
        sa.Column("bank_street", sa.String(150), nullable=False),
        sa.Column("bank_house", sa.String(20), nullable=False),
        sa.Column("bank_account", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("supplier_code", name="pk_suppliers"),
        sa.UniqueConstraint("inn", name="uq_suppliers_inn"),
    )
    op.create_index(
        "ix_suppliers_bank_address",
        "suppliers",
        ["bank_zip", "bank_city", "bank_street", "bank_house"],
    )
    op.create_index(
        "ix_suppliers_bank_address_lower",
        "suppliers",
        [
            sa.text("lower(bank_zip)"),
            sa.text("lower(bank_city)"),
            sa.text("lower(bank_street)"),
            sa.text("lower(bank_house)"),
        ],
    )

    op.create_table(
        "materials",
        sa.Column("material_code", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("class_code", sa.String(10), nullable=False),
        sa.Column("group_code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("material_code", name="pk_materials"),
    )

    op.create_table(
        "units",
        sa.Column("unit_code", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("short_name", sa.String(10), nullable=False),
        sa.PrimaryKeyConstraint("unit_code", name="pk_units"),
        sa.UniqueConstraint("name", name="uq_units_name"),
    )

    op.create_table(
        "material_units",
        sa.Column("material_code", sa.Integer(), nullable=False),
        sa.Column("unit_code", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["material_code"], ["materials.material_code"], name="fk_material_units_material"
        ),
        sa.ForeignKeyConstraint(["unit_code"], ["units.unit_code"], name="fk_material_units_unit"),
        sa.PrimaryKeyConstraint("material_code", "unit_code", name="pk_material_units"),
    )

    op.create_table(
        "documents",
        sa.Column("doc_code", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("doc_code", name="pk_documents"),
        sa.UniqueConstraint("name", name="uq_documents_name"),
    )

    op.create_table(
        "storage_units",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("order_number", sa.String(20), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("supplier_code", sa.Integer(), nullable=False),
        sa.Column("balance_account", sa.String(20), nullable=False),
        sa.Column("doc_code", sa.Integer(), nullable=False),
        sa.Column("doc_number", sa.String(30), nullable=False),
        sa.Column("material_code", sa.Integer(), nullable=False),
        sa.Column("unit_code", sa.Integer(), nullable=False),
        sa.Column("material_account", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_storage_units"),
        sa.UniqueConstraint("order_number", "order_date", name="uq_storage_units_order"),
        sa.ForeignKeyConstraint(
            ["supplier_code"], ["suppliers.supplier_code"], name="fk_storage_units_supplier"
        ),
        sa.ForeignKeyConstraint(
            ["doc_code"], ["documents.doc_code"], name="fk_storage_units_document"
        ),
        sa.ForeignKeyConstraint(
            ["material_code", "unit_code"],
            ["material_units.material_code", "material_units.unit_code"],
            name="fk_storage_units_material_unit",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_storage_units_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_storage_units_unit_price"),
    )
    op.create_index(
        "ix_storage_units_material_supplier", "storage_units", ["material_code", "supplier_code"]
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("login", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("login", name="uq_users_login"),
        sa.CheckConstraint("role IN ('storekeeper', 'admin')", name="ck_users_role"),
    )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_index("ix_storage_units_material_supplier", table_name="storage_units")
    op.drop_table("storage_units")
    op.drop_table("documents")
    op.drop_table("material_units")
    op.drop_table("units")
    op.drop_table("materials")
    op.drop_index("ix_suppliers_bank_address_lower", table_name="suppliers")
    op.drop_index("ix_suppliers_bank_address", table_name="suppliers")
    op.drop_table("suppliers")
