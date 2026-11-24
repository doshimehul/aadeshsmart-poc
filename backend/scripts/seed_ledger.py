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
REPOSITORY_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.models.ledger import Ledger  # noqa: E402


def read_ledger_names(csv_path: Path) -> list[str]:
    """Read non-empty names from the serial_number/name CSV section."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file)
        header = None
        for row in reader:
            if "serial_number" in row and "name" in row:
                header = row
                break
        if header is None:
            raise ValueError("CSV must include serial_number and name columns")

        names: list[str] = []
        serial_index = header.index("serial_number")
        name_index = header.index("name")
        for row in reader:
            if len(row) <= max(serial_index, name_index) or not row[serial_index].strip():
                continue
            name = row[name_index].strip()
            if name:
                names.append(name)
        return names


def seed_ledgers(csv_path: Path) -> tuple[int, int]:
    names = read_ledger_names(csv_path)
    if not names:
        return 0, 0

    with SessionLocal() as session:
        existing_names = set(
            session.scalars(select(Ledger.ledger_name).where(Ledger.ledger_name.in_(names)))
        )
        new_names = [name for name in names if name not in existing_names]
        session.add_all(Ledger(ledger_name=name) for name in new_names)
        session.commit()
        return len(new_names), len(names)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ledger names from a CSV file")
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=REPOSITORY_ROOT / "ledger_seed.csv",
        help="CSV file to load (default: ledger_seed.csv in the repository root)",
    )
    args = parser.parse_args()

    inserted, loaded = seed_ledgers(args.csv_path)
    print(f"Loaded {loaded} ledger names; inserted {inserted} new rows.")


if __name__ == "__main__":
    main()
