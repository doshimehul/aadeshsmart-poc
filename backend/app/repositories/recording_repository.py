from __future__ import annotations

from uuid import UUID

from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.recording import Recording


class RecordingRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, recording: Recording) -> Recording:
        self._session.add(recording)
        self._session.commit()
        self._session.refresh(recording)
        return recording

    def get(self, recording_id: UUID) -> Recording | None:
        return self._session.scalar(select(Recording).where(Recording.recording_id == recording_id))

    def list(self, limit: int = 50, offset: int = 0) -> list[Recording]:
        stmt = select(Recording).order_by(Recording.uploaded_at.desc()).limit(limit).offset(offset)
        return list(self._session.scalars(stmt))

    def claim(self, recording_id: UUID, *, retry: bool = False) -> bool:
        eligible = (
            (Recording.background_job_status == "failed") & (Recording.progress_status != "matched")
            if retry
            else (Recording.background_job_status == "not_started") & (Recording.progress_status != "matched")
        )
        result = self._session.execute(
            update(Recording)
            .where(Recording.recording_id == recording_id, eligible)
            .values(background_job_status="in_progress", last_error=None, failed_at=None)
        )
        self._session.commit()
        self._session.expire_all()
        return result.rowcount == 1

    def update_stage(self, recording_id: UUID, stage: str) -> bool:
        allowed_from = {
            "transcribing": ("uploaded", "transcribing"),
            "transcribed": ("transcribing",),
            "extracting": ("transcribed", "extracting"),
            "extracted": ("extracting",),
            "matching": ("extracted", "matching"),
            "matched": ("matching",),
        }
        previous = allowed_from.get(stage)
        if previous is None:
            return False
        result = self._session.execute(
            update(Recording).where(
                Recording.recording_id == recording_id,
                Recording.background_job_status == "in_progress",
                Recording.progress_status.in_(previous),
            ).values(progress_status=stage)
        )
        self._session.commit()
        return result.rowcount == 1

    def persist_transcript(self, recording_id: UUID, transcript: str) -> None:
        result = self._session.execute(
            update(Recording).where(
                Recording.recording_id == recording_id,
                Recording.background_job_status == "in_progress",
                Recording.progress_status == "transcribing",
            ).values(transcript=transcript)
        )
        self._session.commit()
        if result.rowcount != 1:
            raise RuntimeError("Could not persist transcription")

    def persist_extraction(self, recording_id: UUID, extraction: dict) -> None:
        result = self._session.execute(
            update(Recording).where(
                Recording.recording_id == recording_id,
                Recording.background_job_status == "in_progress",
                Recording.progress_status == "extracting",
            ).values(extracted_json=extraction)
        )
        self._session.commit()
        if result.rowcount != 1:
            raise RuntimeError("Could not persist structured extraction")

    def persist_candidates(self, recording_id: UUID, candidates: list[dict]) -> None:
        result = self._session.execute(
            update(Recording).where(
                Recording.recording_id == recording_id,
                Recording.background_job_status == "in_progress",
                Recording.progress_status == "matching",
            ).values(matching_candidates=candidates)
        )
        self._session.commit()
        if result.rowcount != 1:
            raise RuntimeError("Could not persist donor candidates")

    def mark_success(self, recording_id: UUID) -> None:
        result = self._session.execute(
            update(Recording).where(
                Recording.recording_id == recording_id,
                Recording.progress_status == "matched",
                Recording.background_job_status == "in_progress",
            ).values(
                background_job_status="success",
                processing_completed_at=datetime.now(timezone.utc), last_error=None,
            )
        )
        self._session.commit()
        if result.rowcount != 1:
            raise RuntimeError("Could not finalize recording processing")

    def mark_failed(self, recording_id: UUID, message: str) -> None:
        result = self._session.execute(
            update(Recording).where(
                Recording.recording_id == recording_id,
                Recording.background_job_status == "in_progress",
            ).values(
                background_job_status="failed", last_error=message[:1000], failed_at=datetime.now(timezone.utc)
            )
        )
        self._session.commit()
        if result.rowcount != 1:
            raise RuntimeError("Could not release recording processing ownership")

    def list_stale_in_progress(self, older_than: datetime) -> list[Recording]:
        return list(self._session.scalars(
            select(Recording).where(
                Recording.background_job_status == "in_progress", Recording.modified < older_than
            ).order_by(Recording.modified.asc())
        ))
