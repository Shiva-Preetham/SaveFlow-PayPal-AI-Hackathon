"""Subscription state machine: only these transitions are valid."""
from app.models import Subscriber, SubscriptionState as S

TRANSITIONS: dict[S, set[S]] = {
    S.ACTIVE: {S.PAUSE_SCHEDULED, S.SUSPENDED, S.CANCELLED},
    S.PAUSE_SCHEDULED: {S.SUSPENDED, S.ACTIVE, S.CANCELLED},
    S.SUSPENDED: {S.ACTIVE, S.CANCELLED},
    S.CANCELLED: set(),
}

# PayPal subscription status -> our state, used when reconciling from PayPal (the source of truth).
FROM_PAYPAL = {"ACTIVE": S.ACTIVE, "SUSPENDED": S.SUSPENDED, "CANCELLED": S.CANCELLED, "EXPIRED": S.CANCELLED}


class InvalidTransition(Exception):
    pass


def transition(sub: Subscriber, new: S) -> None:
    if new == sub.state:
        return
    if new not in TRANSITIONS[sub.state]:
        raise InvalidTransition(f"{sub.state.value} -> {new.value} is not allowed")
    sub.state = new


def reconcile(sub: Subscriber, paypal_status: str) -> bool:
    """Adopt PayPal's status even if it skips steps (e.g. events arriving out of order).
    Returns True if the local state changed."""
    new = FROM_PAYPAL.get(paypal_status)
    if new is None or new == sub.state:
        return False
    sub.state = new
    if new != S.SUSPENDED:
        sub.resume_at = None
    return True
