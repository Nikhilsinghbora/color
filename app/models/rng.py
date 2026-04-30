"""RNG audit log model."""

from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RNGAuditLog(Base):
    __tablename__ = "rng_audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    round_id: Mapped[UUID] = mapped_column(ForeignKey("game_rounds.id"), unique=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False, default="secrets.randbelow")
    raw_value: Mapped[int] = mapped_column(nullable=False)
    num_options: Mapped[int] = mapped_column(nullable=False)
    selected_color: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
