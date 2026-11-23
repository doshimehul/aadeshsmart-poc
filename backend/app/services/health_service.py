from app.repositories.health_repository import HealthRepository


class HealthService:
    def __init__(self, repository: HealthRepository):
        self._repository = repository

    def get_status(self) -> dict[str, str]:
        self._repository.database_is_available()
        return {"status": "ok", "database": "ok"}
