"""PayPal webhook handling: verified, idempotent by event id, tolerant of out-of-order delivery
(we re-read the subscription from PayPal instead of trusting event order)."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CancelAttempt, Subscriber, SubscriptionState as S, WebhookEvent
from app.paypal import subscriptions as pp_subs
from app.paypal.client import PayPalError
from app.services import catalogue as cat
from app.services.retention import audit, start_attempt
from app.services.state import reconcile

log = logging.getLogger(__name__)

WIN_BACK_REASON = "Cancelled directly in PayPal without visiting the save page (no reason given)."


def _subscription_id(event: dict) -> str | None:
    res = event.get("resource", {})
    if event.get("event_type", "").startswith("BILLING.SUBSCRIPTION."):
        return res.get("id")
    return res.get("billing_agreement_id")  # PAYMENT.SALE.* events


def process(db: Session, event: dict, verification: str) -> tuple[str, bool]:
    """Returns (result, duplicate)."""
    event_id = event.get("id")
    if not event_id:
        return "ignored: no event id", False
    if db.get(WebhookEvent, event_id) is not None:
        return "duplicate delivery ignored", True

    etype, sid = event.get("event_type", ""), _subscription_id(event)
    sub = db.scalar(select(Subscriber).where(Subscriber.paypal_subscription_id == sid)) if sid else None
    result = "no matching subscriber"
    if sub is not None:
        result = _apply(db, sub, etype, event)
    db.add(WebhookEvent(id=event_id, event_type=etype, resource_id=sid, verification=verification,
                        result=result, payload=event))
    audit(db, "webhook", {"event_id": event_id, "type": etype, "verification": verification, "result": result},
          sub.id if sub else None)
    db.commit()
    return result, False


def _apply(db: Session, sub: Subscriber, etype: str, event: dict) -> str:
    was = sub.state
    if etype == "PAYMENT.SALE.COMPLETED":
        sub.months_paid += 1  # safe: duplicates were filtered by event id above
        return "payment recorded"
    if etype == "BILLING.SUBSCRIPTION.PAYMENT.FAILED":
        sub.failed_payments += 1
        return "failed payment recorded"

    status = event.get("resource", {}).get("status", "")
    if sub.is_live and cat.paypal() is not None:
        try:  # PayPal is the source of truth: re-read rather than trust event order
            status = pp_subs.get(cat.paypal(), sub.paypal_subscription_id).get("status", status)
        except PayPalError as e:
            log.warning("Reconcile read failed (%s); using event status", e)
    changed = reconcile(sub, status)
    result = f"state {was.value} -> {sub.state.value}" if changed else f"state unchanged ({sub.state.value})"

    if etype == "BILLING.SUBSCRIPTION.CANCELLED" and sub.state == S.CANCELLED and changed:
        via_saveflow = db.scalar(select(CancelAttempt).where(CancelAttempt.subscriber_id == sub.id,
                                                             CancelAttempt.outcome == "cancelled"))
        if via_saveflow is None:
            db.flush()
            attempt = start_attempt(db, sub, WIN_BACK_REASON, channel="win_back")
            result += f"; win-back offer #{attempt.id} created ({attempt.action['id']})"
    return result
