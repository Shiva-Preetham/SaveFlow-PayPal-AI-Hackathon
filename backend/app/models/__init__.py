"""SQLAlchemy models. Policies and cancel attempts are added with the policy engine."""
import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SubscriptionState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSE_SCHEDULED = "PAUSE_SCHEDULED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    name: Mapped[str] = mapped_column(String(120))
    paypal_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    paypal_plan_id: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[SubscriptionState] = mapped_column(Enum(SubscriptionState), default=SubscriptionState.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WebhookEvent(Base):
    """Stored by PayPal event id so duplicate deliveries are ignored."""
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # PayPal event id
    event_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Every decision and PayPal call, so the dashboard can show its work."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_id: Mapped[int | None] = mapped_column(ForeignKey("subscribers.id"))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
