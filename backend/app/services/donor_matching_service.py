from app.repositories.ledger_repository import LedgerRepository


class DonorMatchingService:
    def __init__(self, repository: LedgerRepository):
        self._repository = repository

    def match(self, donor_name: str) -> list[dict]:
        return self._repository.search_donors(donor_name, limit=10)
