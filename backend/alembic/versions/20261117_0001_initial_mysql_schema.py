"""Initial MySQL schema for WasteWise AI.

Revision ID: 20261117_0001
Revises:
Create Date: 2026-11-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261117_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("role_name", name="uq_roles_role_name"),
    )
    op.create_index("ix_roles_id", "roles", ["id"])
    op.create_index("ix_roles_role_name", "roles", ["role_name"])

    op.create_table(
        "waste_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("category_name", name="uq_waste_categories_category_name"),
    )
    op.create_index("ix_waste_categories_id", "waste_categories", ["id"])
    op.create_index("ix_waste_categories_category_name", "waste_categories", ["category_name"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role_id", "users", ["role_id"])

    op.create_table(
        "recycling_centers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("center_name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("operating_hours", sa.String(length=100), nullable=True),
        sa.Column("verification_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_recycling_centers_id", "recycling_centers", ["id"])
    op.create_index("ix_recycling_centers_city", "recycling_centers", ["city"])
    op.create_index("ix_recycling_centers_verification_status", "recycling_centers", ["verification_status"])

    op.create_table(
        "accepted_waste_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["center_id"], ["recycling_centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["waste_categories.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("center_id", "category_id", name="uq_center_category"),
    )
    op.create_index("ix_accepted_waste_types_id", "accepted_waste_types", ["id"])
    op.create_index("ix_accepted_waste_types_center_id", "accepted_waste_types", ["center_id"])
    op.create_index("ix_accepted_waste_types_category_id", "accepted_waste_types", ["category_id"])

    op.create_table(
        "waste_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("waste_description", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("estimated_weight_kg", sa.String(length=50), nullable=True),
        sa.Column("report_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["waste_categories.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_waste_reports_id", "waste_reports", ["id"])
    op.create_index("ix_waste_reports_user_id", "waste_reports", ["user_id"])
    op.create_index("ix_waste_reports_category_id", "waste_reports", ["category_id"])
    op.create_index("ix_waste_reports_report_status", "waste_reports", ["report_status"])

    op.create_table(
        "collection_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("category_label", sa.String(length=100), nullable=False),
        sa.Column("weight_tier", sa.String(length=100), nullable=True),
        sa.Column("pickup_address", sa.Text(), nullable=False),
        sa.Column("preferred_pickup_date", sa.String(length=100), nullable=False),
        sa.Column("time_slot", sa.String(length=100), nullable=True),
        sa.Column("additional_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["waste_categories.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_collection_requests_id", "collection_requests", ["id"])
    op.create_index("ix_collection_requests_user_id", "collection_requests", ["user_id"])
    op.create_index("ix_collection_requests_category_id", "collection_requests", ["category_id"])
    op.create_index("ix_collection_requests_status", "collection_requests", ["status"])

    op.create_table(
        "collection_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("collector_id", sa.Integer(), nullable=True),
        sa.Column("collected_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity_unit", sa.String(length=20), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["collection_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["collector_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_collection_records_id", "collection_records", ["id"])
    op.create_index("ix_collection_records_request_id", "collection_records", ["request_id"])
    op.create_index("ix_collection_records_collector_id", "collection_records", ["collector_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("collection_records")
    op.drop_table("collection_requests")
    op.drop_table("waste_reports")
    op.drop_table("accepted_waste_types")
    op.drop_table("recycling_centers")
    op.drop_table("users")
    op.drop_table("waste_categories")
    op.drop_table("roles")
