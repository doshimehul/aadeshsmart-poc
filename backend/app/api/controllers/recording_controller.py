from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.recording import Recording
from app.repositories.recording_repository import RecordingRepository
from app.services.file_storage import LocalRecordingStorage
from app.services.recording_service import RecordingError, RecordingService
from app.services.recording_background_task import process_recording_background

router = APIRouter(prefix="/v1/recordings", tags=["recordings"])


class RecordingResponse(BaseModel):
    recording_id: UUID
    event_id: str
    operator_identifier: str
    original_filename: str
    size: int
    mime_type: str
    progress_status: str
    background_job_status: str
    transcript: str | None = None
    extracted_json: dict | None = None
    matching_candidates: list[dict] | None = None
    last_error: str | None = None
    failed_at: datetime | None = None
    processing_completed_at: datetime | None = None
    uploaded_at: datetime

    @classmethod
    def from_model(cls, recording: Recording):
        return cls(
            recording_id=recording.recording_id,
            event_id=recording.event_id,
            operator_identifier=recording.operator_identifier,
            original_filename=recording.original_filename,
            size=recording.size,
            mime_type=recording.mime_type,
            progress_status=recording.progress_status,
            background_job_status=recording.background_job_status,
            transcript=recording.transcript,
            extracted_json=recording.extracted_json,
            matching_candidates=recording.matching_candidates,
            last_error=recording.last_error,
            failed_at=recording.failed_at,
            processing_completed_at=recording.processing_completed_at,
            uploaded_at=recording.uploaded_at,
        )


def get_recording_service(session: Session = Depends(get_db)) -> RecordingService:
    return RecordingService(RecordingRepository(session), LocalRecordingStorage())


@router.post("", response_model=RecordingResponse, status_code=201)
async def create_recording(
    background_tasks: BackgroundTasks,
    event_id: str = Form(min_length=1, max_length=128),
    operator_identifier: str = Form(min_length=1, max_length=128),
    file: UploadFile = File(...),
    service: RecordingService = Depends(get_recording_service),
):
    try:
        recording = await service.create(event_id, operator_identifier, file)
        background_tasks.add_task(process_recording_background, recording.recording_id)
        return RecordingResponse.from_model(recording)
    except RecordingError as exc:
        raise HTTPException(status_code=415 if "format" in str(exc) else 400, detail=str(exc)) from exc


@router.get("", response_model=list[RecordingResponse])
def list_recordings(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: RecordingService = Depends(get_recording_service),
):
    return [RecordingResponse.from_model(r) for r in service.list(limit, offset)]


@router.get("/{recording_id}", response_model=RecordingResponse)
def get_recording(recording_id: UUID, service: RecordingService = Depends(get_recording_service)):
    recording = service.get(recording_id)
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    return RecordingResponse.from_model(recording)


@router.post("/{recording_id}/retry", response_model=RecordingResponse, status_code=202)
def retry_recording(
    recording_id: UUID,
    background_tasks: BackgroundTasks,
    service: RecordingService = Depends(get_recording_service),
):
    recording = service.get(recording_id)
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.progress_status == "matched" or recording.background_job_status == "success":
        raise HTTPException(status_code=409, detail="Recording processing has already completed")
    if recording.background_job_status == "in_progress":
        raise HTTPException(status_code=409, detail="Recording is already being processed")
    if recording.background_job_status != "failed":
        raise HTTPException(status_code=409, detail="Recording is not eligible for retry")
    if not service.claim_retry(recording_id):
        raise HTTPException(status_code=409, detail="Recording is already being processed")
    background_tasks.add_task(process_recording_background, recording_id, already_claimed=True)
    recording = service.get(recording_id)
    return RecordingResponse.from_model(recording)
