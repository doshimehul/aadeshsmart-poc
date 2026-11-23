import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.recording import Recording, RecordingStatus
from app.repositories.ledger_repository import LedgerRepository
from app.repositories.recording_repository import RecordingRepository
from app.services.ai_providers import (
    DonationExtraction,
    GeminiExtractionProvider,
    MockExtractionProvider,
    MockTranscriptionProvider,
    SarvamTranscriptionProvider,
)
from app.services.donor_matching_service import DonorMatchingService

logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(self, settings: Settings):
        self._provider = MockTranscriptionProvider() if settings.sarvam_mode.lower() == "mock" else SarvamTranscriptionProvider(settings)

    def transcribe(self, audio_path: str) -> str:
        return self._provider.transcribe(audio_path)


class ExtractionService:
    def __init__(self, settings: Settings):
        self._provider = MockExtractionProvider() if settings.gemini_mode.lower() == "mock" else GeminiExtractionProvider(settings)

    def extract(self, transcript: str) -> DonationExtraction:
        return self._provider.extract(transcript)


class RecordingProcessingService:
    def __init__(self, session: Session, settings: Settings, storage_root: str | Path = "storage/recordings"):
        self._session = session
        self._repository = RecordingRepository(session)
        self._transcription = TranscriptionService(settings)
        self._extraction = ExtractionService(settings)
        self._matching = DonorMatchingService(LedgerRepository(session))
        self._storage_root = Path(storage_root)

    def process(self, recording_id: UUID, *, already_claimed: bool = False) -> None:
        if not already_claimed and not self._repository.claim(recording_id):
            logger.info("recording_id=%s stage=claim outcome=skipped", recording_id)
            return
        try:
            recording = self._repository.get(recording_id)
            if recording is None:
                raise ValueError("Recording no longer exists")
            if recording.progress_status == RecordingStatus.MATCHED:
                self._repository.mark_success(recording_id)
                return

            if recording.progress_status in (RecordingStatus.UPLOADED, RecordingStatus.TRANSCRIBING):
                self._run_transcription(recording)
                recording = self._repository.get(recording_id)
            if recording and recording.progress_status in (RecordingStatus.TRANSCRIBED, RecordingStatus.EXTRACTING):
                self._run_extraction(recording)
                recording = self._repository.get(recording_id)
            if recording and recording.progress_status in (RecordingStatus.EXTRACTED, RecordingStatus.MATCHING):
                self._run_matching(recording)
            self._repository.mark_success(recording_id)
            logger.info("recording_id=%s stage=processing outcome=success", recording_id)
        except Exception as exc:
            self._session.rollback()
            message = str(exc).strip() or type(exc).__name__
            self._repository.mark_failed(recording_id, message[:1000])
            logger.exception("recording_id=%s stage=%s outcome=failed", recording_id, self._current_stage(recording_id))

    def _current_stage(self, recording_id: UUID) -> str:
        recording = self._repository.get(recording_id)
        return recording.progress_status if recording else "unknown"

    def _set_stage(self, recording_id: UUID, stage: RecordingStatus) -> None:
        if not self._repository.update_stage(recording_id, stage.value):
            raise RuntimeError("Recording processing ownership was lost")
        logger.info("recording_id=%s stage=%s outcome=started", recording_id, stage.value)

    def _run_transcription(self, recording: Recording) -> None:
        self._set_stage(recording.recording_id, RecordingStatus.TRANSCRIBING)
        audio_path = self._storage_root / recording.file_name
        transcript = self._transcription.transcribe(str(audio_path))
        if not transcript.strip():
            raise ValueError("Transcription provider returned empty text")
        self._repository.persist_transcript(recording.recording_id, transcript)
        if not self._repository.update_stage(recording.recording_id, RecordingStatus.TRANSCRIBED.value):
            raise RuntimeError("Could not persist transcription checkpoint")
        logger.info("recording_id=%s stage=transcribed outcome=persisted", recording.recording_id)

    def _run_extraction(self, recording: Recording) -> None:
        if not recording.transcript:
            raise ValueError("Cannot extract donation details without a transcript")
        self._set_stage(recording.recording_id, RecordingStatus.EXTRACTING)
        extraction = self._extraction.extract(recording.transcript)
        validated = DonationExtraction.model_validate(extraction)
        self._repository.persist_extraction(recording.recording_id, validated.model_dump())
        if not self._repository.update_stage(recording.recording_id, RecordingStatus.EXTRACTED.value):
            raise RuntimeError("Could not persist extraction checkpoint")
        logger.info("recording_id=%s stage=extracted outcome=persisted", recording.recording_id)

    def _run_matching(self, recording: Recording) -> None:
        if not recording.extracted_json:
            raise ValueError("Cannot match donors without extracted donation details")
        self._set_stage(recording.recording_id, RecordingStatus.MATCHING)
        candidates = self._matching.match(str(recording.extracted_json["name"]))
        self._repository.persist_candidates(recording.recording_id, candidates)
        if not self._repository.update_stage(recording.recording_id, RecordingStatus.MATCHED.value):
            raise RuntimeError("Could not persist donor matching checkpoint")
        logger.info("recording_id=%s stage=matched candidates=%s outcome=persisted", recording.recording_id, len(candidates))
