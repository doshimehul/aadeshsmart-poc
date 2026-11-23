import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/aadeshsmart")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.controllers.health_controller import get_health_service


class HealthyRepository:
    def database_is_available(self) -> bool:
        return True


class HealthyService:
    def get_status(self) -> dict[str, str]:
        HealthyRepository().database_is_available()
        return {"status": "ok", "database": "ok"}


@pytest.fixture
def client():
    app.dependency_overrides[get_health_service] = lambda: HealthyService()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
