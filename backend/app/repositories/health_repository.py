from sqlalchemy import text
from sqlalchemy.orm import Session


class HealthRepository:
    def __init__(self, session: Session):
        self._session = session

    def database_is_available(self) -> bool:
        self._session.execute(text("SELECT 1"))
        return True
