"""SQLAlchemy models."""
import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class Plan(Base):
    """A PayPal billing plan the merchant offers. Discounts are separate plans, because PayPal
    rejects a price override on the subscriber's current plan (Day 1: OVERRIDES_ON_SAME_PLAN_NOT_ALLOWED)."""
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    key: Mapped[str] = mapped_column(String(40), unique=True)  # "pro", "pro_off30", "lite"
    name: Mapped[str] = mapped_column(String(120))
    price: Mapped[float] = mapped_column(Float)  # what the subscriber pays now (the discounted price for discounts)
    regular_price: Mapped[float] = mapped_column(Float)  # price after any discount months
    base_key: Mapped[str] = mapped_column(String(40))  # the plan a discount is taken from
    discount_pct: Mapped[int] = mapped_column(Integer, default=0)
    discount_months: Mapped[int] = mapped_column(Integer, default=0)  # trial cycles at the discounted price
    paypal_plan_id: Mapped[str | None] = mapped_column(String(64))


class Policy(Base):
    """A versioned merchant retention policy. Only one is ACTIVE; drafts wait for merchant approval."""
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | active | superseded
    rules: Mapped[dict] = mapped_column(JSON)
    source_text: Mapped[str | None] = mapped_column(Text)  # the merchant's plain-English rules
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    name: Mapped[str] = mapped_column(String(120))
    plan_key: Mapped[str] = mapped_column(String(40), default="pro")
    paypal_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)  # backed by a real sandbox subscription
    state: Mapped[SubscriptionState] = mapped_column(Enum(SubscriptionState), default=SubscriptionState.ACTIVE)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    months_paid: Mapped[int] = mapped_column(Integer, default=0)
    failed_payments: Mapped[int] = mapped_column(Integer, default=0)
    offers_received: Mapped[int] = mapped_column(Integer, default=0)
    resume_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    persona: Mapped[str | None] = mapped_column(Text)  # demo-only note shown in the cancel flow picker
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CancelAttempt(Base):
    """One save attempt: the reason, what the AI proposed, what the guardrail allowed, and the outcome."""
    __tablename__ = "cancel_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscribers.id"))
    channel: Mapped[str] = mapped_column(String(16), default="save_page")  # save_page | win_back
    reason_text: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(32))
    reason_summary: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)  # subscriber facts the agent saw
    allowed_actions: Mapped[list] = mapped_column(JSON, default=list)
    proposed_action_id: Mapped[str | None] = mapped_column(String(40))  # what the LLM picked
    action: Mapped[dict | None] = mapped_column(JSON)  # what was actually offered
    guardrail: Mapped[str] = mapped_column(String(16), default="passed")  # passed | blocked | fallback
    guardrail_note: Mapped[str | None] = mapped_column(Text)
    injection_suspected: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    ai_source: Mapped[str] = mapped_column(String(16), default="gemini")  # gemini | cache | fallback
    counter_used: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[str] = mapped_column(String(24), default="offered")
    # offered | saved | awaiting_approval | cancelled | declined
    revenue_kept_12m: Mapped[float] = mapped_column(Float, default=0.0)
    approve_url: Mapped[str | None] = mapped_column(Text)
    paypal_calls: Mapped[list] = mapped_column(JSON, default=list)
    policy_version: Mapped[int | None] = mapped_column(Integer)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    subscriber: Mapped[Subscriber] = relationship()


class WebhookEvent(Base):
    """Stored by PayPal event id so duplicate deliveries are ignored."""
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # PayPal event id
    event_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    verification: Mapped[str] = mapped_column(String(24))  # SUCCESS | SIMULATED
    result: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Every decision and PayPal call, so the dashboard can show its work."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_id: Mapped[int | None] = mapped_column(ForeignKey("subscribers.id"))
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("cancel_attempts.id"))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LlmCache(Base):
    """Cached LLM answers, keyed by a hash of model + prompt, to survive free-tier rate limits."""
    __tablename__ = "llm_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
