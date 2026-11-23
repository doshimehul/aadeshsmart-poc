import logging
from uuid import UUID

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.recording_processing_service import RecordingProcessingService

logger = logging.getLogger(__name__)


def process_recording_background(recording_id: UUID, *, already_claimed: bool = False) -> None:
    """FastAPI BackgroundTasks entry point; processing logic lives in the service."""
    session = SessionLocal()
    try:
        RecordingProcessingService(session, get_settings()).process(
            recording_id, already_claimed=already_claimed
        )
    except Exception:
        session.rollback()
        logger.exception("recording_id=%s stage=background_task outcome=failed", recording_id)
    finally:
        session.close()
