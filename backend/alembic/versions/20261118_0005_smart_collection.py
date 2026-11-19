"""Extend centers, explicit accepted materials, and collection lifecycle.

Revision ID: 20261118_0005
Revises: 20261118_0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261118_0005"
down_revision: Union[str, Sequence[str], None] = "20261118_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recycling_centers", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("recycling_centers", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("recycling_centers", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("recycling_centers", sa.Column("center_type", sa.String(100), nullable=True))
    op.add_column("recycling_centers", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("recycling_centers", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE recycling_centers SET updated_at = created_at WHERE updated_at IS NULL")
    with op.batch_alter_table("recycling_centers") as batch:
        batch.alter_column("updated_at", existing_type=sa.DateTime(), nullable=False)
    op.create_index("ix_recycling_centers_center_type", "recycling_centers", ["center_type"])
    op.create_index("ix_recycling_centers_is_active", "recycling_centers", ["is_active"])

    op.add_column("accepted_waste_types", sa.Column("accepted_waste_label", sa.String(100), nullable=True))
    with op.batch_alter_table("accepted_waste_types") as batch:
        batch.drop_constraint("uq_center_category", type_="unique")
        batch.create_unique_constraint(
            "uq_center_category_material", ["center_id", "category_id", "accepted_waste_label"]
        )
    op.create_index(
        "ix_accepted_waste_types_accepted_waste_label", "accepted_waste_types", ["accepted_waste_label"]
    )

    with op.batch_alter_table("collection_requests") as batch:
        batch.add_column(sa.Column("waste_classification_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("recycling_center_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("quantity", sa.Numeric(12, 2), nullable=True))
        batch.add_column(sa.Column("quantity_unit", sa.String(20), nullable=False, server_default="kg"))
        batch.add_column(sa.Column("pickup_latitude", sa.Float(), nullable=True))
        batch.add_column(sa.Column("pickup_longitude", sa.Float(), nullable=True))
        batch.add_column(sa.Column("assigned_staff_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("internal_notes", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_collection_request_classification", "waste_classifications",
            ["waste_classification_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_collection_request_center", "recycling_centers",
            ["recycling_center_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_collection_request_assigned_staff", "users",
            ["assigned_staff_id"], ["id"], ondelete="SET NULL",
        )
        batch.alter_column("status", existing_type=sa.String(50), server_default="pending")
    for column in ("waste_classification_id", "recycling_center_id", "assigned_staff_id"):
        op.create_index(f"ix_collection_requests_{column}", "collection_requests", [column])


def downgrade() -> None:
    for column in ("assigned_staff_id", "recycling_center_id", "waste_classification_id"):
        op.drop_index(f"ix_collection_requests_{column}", table_name="collection_requests")
    with op.batch_alter_table("collection_requests") as batch:
        batch.drop_constraint("fk_collection_request_assigned_staff", type_="foreignkey")
        batch.drop_constraint("fk_collection_request_center", type_="foreignkey")
        batch.drop_constraint("fk_collection_request_classification", type_="foreignkey")
        batch.drop_column("internal_notes")
        batch.drop_column("assigned_staff_id")
        batch.drop_column("pickup_longitude")
        batch.drop_column("pickup_latitude")
        batch.drop_column("quantity_unit")
        batch.drop_column("quantity")
        batch.drop_column("recycling_center_id")
        batch.drop_column("waste_classification_id")
        # The previous migration had no server default for status.
        batch.alter_column("status", existing_type=sa.String(50), server_default=None)

    op.drop_index("ix_accepted_waste_types_accepted_waste_label", table_name="accepted_waste_types")
    # The legacy schema cannot represent class-specific acceptance. Remove those
    # rows on downgrade instead of silently turning them into broad stream acceptance.
    op.execute("DELETE FROM accepted_waste_types WHERE accepted_waste_label IS NOT NULL")
    with op.batch_alter_table("accepted_waste_types") as batch:
        batch.drop_constraint("uq_center_category_material", type_="unique")
        batch.create_unique_constraint("uq_center_category", ["center_id", "category_id"])
        batch.drop_column("accepted_waste_label")

    op.drop_index("ix_recycling_centers_is_active", table_name="recycling_centers")
    op.drop_index("ix_recycling_centers_center_type", table_name="recycling_centers")
    with op.batch_alter_table("recycling_centers") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("is_active")
        batch.drop_column("center_type")
        batch.drop_column("email")
        batch.drop_column("country")
        batch.drop_column("description")
