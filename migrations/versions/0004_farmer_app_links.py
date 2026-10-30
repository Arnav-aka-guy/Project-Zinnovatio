"""farmer app links: notifications reach farmers through the Vaari app (no SMS/WhatsApp)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-31 05:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "farmer_link",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("farmer_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_opened_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["farmer_id"], ["farmer.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    with op.batch_alter_table("farmer_link", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_farmer_link_farmer_id"), ["farmer_id"], unique=False)

    with op.batch_alter_table("push_subscription", schema=None) as batch_op:
        batch_op.add_column(sa.Column("farmer_link_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_push_subscription_farmer_link_id"), ["farmer_link_id"], unique=False)
        batch_op.create_foreign_key("fk_push_subscription_farmer_link_id", "farmer_link", ["farmer_link_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("push_subscription", schema=None) as batch_op:
        batch_op.drop_constraint("fk_push_subscription_farmer_link_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_push_subscription_farmer_link_id"))
        batch_op.drop_column("farmer_link_id")
    with op.batch_alter_table("farmer_link", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_farmer_link_farmer_id"))
    op.drop_table("farmer_link")
