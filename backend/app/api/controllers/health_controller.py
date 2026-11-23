from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.health_repository import HealthRepository
from app.services.health_service import HealthService
from app.core.config import get_settings
from app.services.ai_providers import GeminiExtractionProvider

router = APIRouter(tags=["health"])


def get_health_service(session: Session = Depends(get_db)) -> HealthService:
    return HealthService(HealthRepository(session))


@router.get("/health", summary="Check API and database health")
def health_check(service: HealthService = Depends(get_health_service)) -> dict[str, str]:
    try:
        return service.get_status()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@router.get("/health/gemini", summary="Check Gemini extraction connectivity")
def gemini_health_check() -> dict:
    """Run one small extraction using the same provider/configuration as recordings."""
    settings = get_settings()
    started = perf_counter()
    try:
        result = GeminiExtractionProvider(settings).extract("દાન: એક હજાર રૂપિયા, માતુ શ્રી નિર્મળા બેન, ઘીનું દાન")
        return {
            "status": "ok",
            "model": settings.gemini_model,
            "duration_seconds": round(perf_counter() - started, 3),
            "result": result.model_dump(),
        }
    except Exception as exc:
        duration = round(perf_counter() - started, 3)
        # GeminiExtractionProvider intentionally gives its callers a generic error.
        # Its Python exception context still contains the original SDK exception.
        original = exc.__context__ or exc.__cause__ or exc
        response = getattr(original, "response", None)
        body = getattr(original, "body", None)
        if body is None and response is not None:
            try:
                body = response.text
            except Exception:
                body = None
        headers = getattr(response, "headers", None)
        diagnostic = {
            "status": "error",
            "model": settings.gemini_model,
            "duration_seconds": duration,
            "exception_type": type(original).__name__,
            "message": str(original),
            "http_status": getattr(original, "status_code", getattr(response, "status_code", None)),
            "error_body": body,
            "response_headers": dict(headers) if headers is not None else None,
        }
        raise HTTPException(status_code=503, detail=diagnostic) from exc
