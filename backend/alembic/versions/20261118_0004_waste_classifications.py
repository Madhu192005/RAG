"""Add private user-owned image classification history.

Revision ID: 20261118_0004
Revises: 20261117_0003
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20261118_0004"
down_revision: Union[str, Sequence[str], None] = "20261117_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "waste_classifications",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=False),
        sa.Column("predicted_class", sa.String(length=100), nullable=True),
        sa.Column("confirmed_class", sa.String(length=100), nullable=True),
        sa.Column("waste_category_id", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("confidence_label", sa.String(length=30), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["waste_category_id"], ["waste_categories.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_waste_classifications_user_id", "waste_classifications", ["user_id"])
    op.create_index("ix_waste_classifications_waste_category_id", "waste_classifications", ["waste_category_id"])

def downgrade() -> None:
    op.drop_index("ix_waste_classifications_waste_category_id", table_name="waste_classifications")
    op.drop_index("ix_waste_classifications_user_id", table_name="waste_classifications")
    op.drop_table("waste_classifications")
