from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers

from app.models.base import Base
from app.models.recording import Recording
from app.repositories.recording_repository import RecordingRepository
from app.services.file_storage import LocalRecordingStorage
from app.services.recording_service import RecordingError, RecordingService


def make_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # JSONB is PostgreSQL-specific; the test only needs the recording table metadata.
    Recording.__table__.c.extracted_json.type = __import__("sqlalchemy").JSON()
    Base.metadata.create_all(engine)
    return Session(engine)


def make_upload(filename="call.wav", content_type="audio/wav", payload=b"RIFF audio"):
    return UploadFile(filename=filename, file=__import__("io").BytesIO(payload), headers=Headers({"content-type": content_type}))


def test_successful_upload_persists_metadata_and_audio(tmp_path):
    session = make_db()
    storage = LocalRecordingStorage(tmp_path / "storage" / "recordings")
    service = RecordingService(RecordingRepository(session), storage)

    recording = __import__("asyncio").run(service.create("event-42", "operator-7", make_upload()))

    assert isinstance(recording.recording_id, UUID)
    assert recording.event_id == "event-42"
    assert recording.operator_identifier == "operator-7"
    assert recording.original_filename == "call.wav"
    assert recording.size == len(b"RIFF audio")
    assert recording.mime_type == "audio/wav"
    assert recording.uploaded_at is not None
    assert (tmp_path / "storage" / "recordings" / recording.file_name).read_bytes() == b"RIFF audio"
    fetched = RecordingRepository(session).get(recording.recording_id)
    assert fetched is not None and fetched.recording_id == recording.recording_id


def test_rejects_unsupported_file_without_persisting(tmp_path):
    session = make_db()
    storage = LocalRecordingStorage(tmp_path / "recordings")
    service = RecordingService(RecordingRepository(session), storage)

    try:
        __import__("asyncio").run(service.create("event", "operator", make_upload("notes.txt", "text/plain")))
        assert False, "expected unsupported audio rejection"
    except RecordingError as exc:
        assert "Unsupported" in str(exc)
    assert RecordingRepository(session).list(10, 0) == []
    assert list(Path(tmp_path / "recordings").glob("*")) == [] if (tmp_path / "recordings").exists() else True


def test_rejects_audio_over_size_limit(tmp_path):
    session = make_db()
    service = RecordingService(RecordingRepository(session), LocalRecordingStorage(tmp_path / "recordings"))

    try:
        __import__("asyncio").run(service.create("event", "operator", make_upload(payload=b"x" * (25 * 1024 * 1024 + 1))))
        assert False, "expected file size rejection"
    except RecordingError as exc:
        assert "25 MiB" in str(exc)
    assert RecordingRepository(session).list(10, 0) == []
