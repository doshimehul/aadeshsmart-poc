"""Load ledger names from a CSV file into the application database.

Run from the repository root with:
    python backend/scripts/seed_ledger.py
"""

import argparse
import csv
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.models.ledger import Ledger  # noqa: E402


def read_ledger_rows(csv_path: Path) -> list[dict[str, str | None]]:
    """Read ledger names and optional contact details from the CSV."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file)
        header = None
        for row in reader:
            if "serial_number" in row and "name" in row:
                header = row
                break
        if header is None:
            raise ValueError("CSV must include serial_number and name columns")

        rows: list[dict[str, str | None]] = []
        serial_index = header.index("serial_number")
        name_index = header.index("name")
        contact_index = header.index("contact_name") if "contact_name" in header else None
        mobile_index = header.index("mobile") if "mobile" in header else None
        for row in reader:
            if len(row) <= max(serial_index, name_index) or not row[serial_index].strip():
                continue
            name = row[name_index].strip()
            if name:
                contact = (
                    row[contact_index].strip()
                    if contact_index is not None and len(row) > contact_index
                    else ""
                )
                mobile = (
                    row[mobile_index].strip()
                    if mobile_index is not None and len(row) > mobile_index
                    else ""
                )
                rows.append(
                    {
                        "ledger_name": name,
                        "contact_person": contact or None,
                        "mobile": mobile or None,
                    }
                )
        return rows


def seed_ledgers(csv_path: Path) -> tuple[int, int]:
    rows = read_ledger_rows(csv_path)
    if not rows:
        return 0, 0

    with SessionLocal() as session:
        names = [row["ledger_name"] for row in rows]
        existing_ledgers = session.scalars(
            select(Ledger).where(Ledger.ledger_name.in_(names))
        ).all()
        ledgers_by_name = {ledger.ledger_name: ledger for ledger in existing_ledgers}
        inserted = 0
        for row in rows:
            ledger = ledgers_by_name.get(row["ledger_name"])
            if ledger is None:
                ledger = Ledger(ledger_name=row["ledger_name"])
                session.add(ledger)
                ledgers_by_name[row["ledger_name"]] = ledger
                inserted += 1
            ledger.contact_person = row["contact_person"]
            ledger.mobile = row["mobile"]
        session.commit()
        return inserted, len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ledger names from a CSV file")
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=BACKEND_DIR / "ledger_seed.csv",
        help="CSV file to load (default: backend/ledger_seed.csv)",
    )
    args = parser.parse_args()

    inserted, loaded = seed_ledgers(args.csv_path)
    print(f"Loaded {loaded} ledger names; inserted {inserted} new rows.")


if __name__ == "__main__":
    main()
