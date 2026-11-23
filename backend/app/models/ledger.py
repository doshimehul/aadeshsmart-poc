from datetime import datetime

from sqlalchemy import DateTime, Identity, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Ledger(Base):
    __tablename__ = "ledgers"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    ledger_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_person: Mapped[str | None] = mapped_column(String(255))
    mobile: Mapped[str | None] = mapped_column(String(32))
    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    modified: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
