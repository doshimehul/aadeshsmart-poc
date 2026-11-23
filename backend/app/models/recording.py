from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RecordingStatus(StrEnum):
    UPLOADED = "uploaded"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    MATCHING = "matching"
    MATCHED = "matched"


class BackgroundJobStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    SUCCESS = "success"


class Recording(Base):
    __tablename__ = "recordings"
    __table_args__ = (
        CheckConstraint("size >= 0", name="ck_recordings_size_nonnegative"),
        CheckConstraint(
            "progress_status IN ('uploaded', 'transcribing', 'transcribed', 'extracting', 'extracted', 'matching', 'matched')",
            name="ck_recordings_progress_status",
        ),
        CheckConstraint(
            "background_job_status IN ('not_started', 'in_progress', 'failed', 'success')",
            name="ck_recordings_background_job_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    recording_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), default=uuid4, nullable=False, unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    operator_identifier: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ledger_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ledgers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # This is a generated storage key, not the original client-supplied filename.
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    transcript: Mapped[str | None] = mapped_column()
    progress_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=RecordingStatus.UPLOADED.value, index=True
    )
    extracted_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    matching_candidates: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    background_job_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=BackgroundJobStatus.NOT_STARTED.value, index=True
    )
    last_error: Mapped[str | None] = mapped_column(String(1000))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    modified: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
