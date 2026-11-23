from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.models.recording import Recording
from app.repositories.recording_repository import RecordingRepository
from app.services.file_storage import LocalRecordingStorage

MAX_AUDIO_SIZE = 25 * 1024 * 1024
SUPPORTED_AUDIO = {
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".wav": {"audio/wav", "audio/x-wav", "audio/vnd.wave"},
    ".m4a": {"audio/mp4", "audio/x-m4a"},
    ".aac": {"audio/aac", "audio/aacp"},
    ".ogg": {"audio/ogg", "application/ogg"},
    ".webm": {"audio/webm"},
    ".flac": {"audio/flac", "audio/x-flac"},
}


class RecordingError(ValueError):
    pass


class RecordingService:
    def __init__(self, repository: RecordingRepository, storage: LocalRecordingStorage):
        self._repository = repository
        self._storage = storage

    async def create(self, event_id: str, operator_identifier: str, upload: UploadFile) -> Recording:
        original_name = Path(upload.filename or "").name
        suffix = Path(original_name).suffix.lower()
        # MediaRecorder adds codec parameters such as `;codecs=opus`. Validate the
        # container media type while preserving that parameter in no persisted field.
        mime_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if suffix not in SUPPORTED_AUDIO or mime_type not in SUPPORTED_AUDIO[suffix]:
            raise RecordingError("Unsupported audio format")
        content = await upload.read(MAX_AUDIO_SIZE + 1)
        if not content:
            raise RecordingError("Audio file is empty")
        if len(content) > MAX_AUDIO_SIZE:
            raise RecordingError("Audio file exceeds the 25 MiB limit")
        recording_id = uuid4()
        storage_name = self._storage.save(recording_id, suffix, content)
        recording = Recording(
            recording_id=recording_id,
            event_id=event_id,
            operator_identifier=operator_identifier,
            file_name=storage_name,
            original_filename=original_name[:255],
            size=len(content),
            mime_type=mime_type,
        )
        try:
            return self._repository.add(recording)
        except Exception:
            self._storage.delete(storage_name)
            raise

    def get(self, recording_id):
        return self._repository.get(recording_id)

    def list(self, limit: int, offset: int):
        return self._repository.list(limit, offset)

    def claim_retry(self, recording_id):
        return self._repository.claim(recording_id, retry=True)
