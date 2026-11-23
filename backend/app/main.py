from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.controllers.health_controller import router as health_router
from app.api.controllers.recording_controller import router as recording_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix="/api")
app.include_router(recording_router, prefix="/api")
