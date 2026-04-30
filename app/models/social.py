"""Social models: FriendLink."""

from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FriendLink(Base):
    __tablename__ = "friend_links"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    friend_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "friend_id", name="uq_friend_link"),
    )
