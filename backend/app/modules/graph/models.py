"""SQLAlchemy-модели graph-модуля: интересы пользователей и тематические кластеры."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserInterestModel(Base):
    """Интерес пользователя, выведенный из его словаря и контекстов."""

    __tablename__ = "user_interests"
    __table_args__ = (UniqueConstraint("user_id", "interest_key", name="uq_user_interest_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    interest_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class TopicClusterModel(Base):
    """Тематический кластер — общий для всей системы, не привязан к пользователю."""

    __tablename__ = "topic_clusters"

    cluster_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
