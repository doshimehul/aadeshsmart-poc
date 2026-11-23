from sqlalchemy import text
from sqlalchemy.orm import Session


class LedgerRepository:
    """Read-only access to donor contacts in the project ledger."""

    def __init__(self, session: Session):
        self._session = session

    def search_donors(self, donor_name: str, limit: int = 10) -> list[dict]:
        """Rank likely donors in PostgreSQL using pg_trgm similarity."""
        statement = text(
            """
            WITH input AS (
                SELECT lower(trim(:donor_name)) AS raw_name,
                       trim(regexp_replace(
                           regexp_replace(lower(:donor_name), '[[:punct:]_]+', ' ', 'g'),
                           '(^| )(શ્રીમતી|શ્રી)( |$)', ' ', 'g'
                       )) AS normalized_name
            ), candidates AS (
                SELECT l.id AS ledger_id, l.ledger_name, l.contact_person, l.mobile,
                       i.raw_name, i.normalized_name,
                       trim(regexp_replace(
                           regexp_replace(lower(l.ledger_name), '[[:punct:]_]+', ' ', 'g'),
                           '(^| )(શ્રીમતી|શ્રી)( |$)', ' ', 'g'
                       )) AS normalized_candidate
                FROM ledgers AS l CROSS JOIN input AS i
                WHERE lower(l.ledger_name) % i.raw_name
                   OR trim(regexp_replace(
                       regexp_replace(lower(l.ledger_name), '[[:punct:]_]+', ' ', 'g'),
                       '(^| )(શ્રીમતી|શ્રી)( |$)', ' ', 'g'
                   )) = i.normalized_name
            ), ranked AS (
                SELECT ledger_id, ledger_name, contact_person, mobile,
                       CASE
                           WHEN raw_name = lower(trim(ledger_name)) THEN 1.0
                           WHEN normalized_name = normalized_candidate THEN 1.0
                           ELSE similarity(normalized_name, normalized_candidate)
                       END AS score,
                       CASE
                           WHEN raw_name = lower(trim(ledger_name)) THEN 'exact'
                           WHEN normalized_name = normalized_candidate THEN 'normalized_exact'
                           ELSE 'fuzzy_name'
                       END AS method
                FROM candidates
            )
            SELECT ledger_id, ledger_name, contact_person, mobile,
                   round(score::numeric, 4)::float AS score, method
            FROM ranked
            WHERE score >= 0.45
            ORDER BY score DESC, ledger_id ASC
            LIMIT :limit
            """
        )
        rows = self._session.execute(
            statement, {"donor_name": donor_name, "limit": limit}
        ).mappings()
        return [dict(row) for row in rows]
