"""Create the initial application schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ledgers",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("ledger_name", sa.String(length=255), nullable=False),
        sa.Column("contact_person", sa.String(length=255), nullable=True),
        sa.Column("mobile", sa.String(length=32), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modified", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ledgers_ledger_name", "ledgers", ["ledger_name"])

    op.create_table(
        "recordings",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("recording_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("operator_identifier", sa.String(length=128), nullable=False),
        sa.Column(
            "ledger_id",
            sa.Integer(),
            sa.ForeignKey("ledgers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("file_name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("progress_status", sa.String(length=32), server_default="uploaded", nullable=False),
        sa.Column("extracted_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("matching_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("background_job_status", sa.String(length=32), server_default="not_started", nullable=False),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modified", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("size >= 0", name="ck_recordings_size_nonnegative"),
        sa.CheckConstraint(
            "progress_status IN ('uploaded', 'transcribing', 'transcribed', 'extracting', 'extracted', 'matching', 'matched')",
            name="ck_recordings_progress_status",
        ),
        sa.CheckConstraint(
            "background_job_status IN ('not_started', 'in_progress', 'failed', 'success')",
            name="ck_recordings_background_job_status",
        ),
    )
    op.create_index("ix_recordings_recording_id", "recordings", ["recording_id"], unique=True)
    op.create_index("ix_recordings_event_id", "recordings", ["event_id"])
    op.create_index("ix_recordings_operator_identifier", "recordings", ["operator_identifier"])
    op.create_index("ix_recordings_ledger_id", "recordings", ["ledger_id"])
    op.create_index("ix_recordings_progress_status", "recordings", ["progress_status"])
    op.create_index("ix_recordings_background_job_status", "recordings", ["background_job_status"])

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_ledgers_ledger_name_trgm "
        "ON ledgers USING gin (lower(ledger_name) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_ledgers_ledger_name_trgm", table_name="ledgers")
    op.drop_index("ix_recordings_background_job_status", table_name="recordings")
    op.drop_index("ix_recordings_progress_status", table_name="recordings")
    op.drop_index("ix_recordings_ledger_id", table_name="recordings")
    op.drop_index("ix_recordings_operator_identifier", table_name="recordings")
    op.drop_index("ix_recordings_event_id", table_name="recordings")
    op.drop_index("ix_recordings_recording_id", table_name="recordings")
    op.drop_table("recordings")
    op.drop_index("ix_ledgers_ledger_name", table_name="ledgers")
    op.drop_table("ledgers")
