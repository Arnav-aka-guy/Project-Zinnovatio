"""pilot v0.4 notifications outbox and push subscriptions

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31 03:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("audience", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("dedupe_key", sa.String(), nullable=False),
        sa.Column("farmer_id", sa.Integer(), nullable=True),
        sa.Column("machine_id", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("slot_id", sa.Integer(), nullable=True),
        sa.Column("lang", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("urgency", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("status_reason", sa.String(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("provider_ref", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["farmer_id"],
            ["farmer.id"],
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machine.id"],
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["request.id"],
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["slot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(op.f("ix_notification_audience"), "notification", ["audience"], unique=False)
    op.create_index(op.f("ix_notification_next_attempt_at"), "notification", ["next_attempt_at"], unique=False)
    op.create_index(op.f("ix_notification_request_id"), "notification", ["request_id"], unique=False)
    op.create_index(op.f("ix_notification_status"), "notification", ["status"], unique=False)
    op.create_table(
        "push_subscription",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(), nullable=False),
        sa.Column("auth", sa.String(), nullable=False),
        sa.Column("roles_json", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("machine_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machine.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )


def downgrade() -> None:
    op.drop_table("push_subscription")
    op.drop_index(op.f("ix_notification_status"), table_name="notification")
    op.drop_index(op.f("ix_notification_request_id"), table_name="notification")
    op.drop_index(op.f("ix_notification_next_attempt_at"), table_name="notification")
    op.drop_index(op.f("ix_notification_audience"), table_name="notification")
    op.drop_table("notification")
