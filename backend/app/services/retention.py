"""Save-attempt orchestration: read the subscriber's PayPal history, ask the agent, enforce the
policy, execute the accepted offer in PayPal, and audit every step."""
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.decider import decide, template_message
from app.config import get_settings
from app.models import AuditLog, CancelAttempt, Policy, Subscriber, SubscriptionState as S, utcnow
from app.paypal import subscriptions as pp_subs
from app.paypal.client import PayPalError
from app.policy.engine import CANCEL, Action, SubscriberContext
from app.policy.rules import PolicyRules
from app.services import catalogue as cat
from app.services.state import reconcile, transition

log = logging.getLogger(__name__)


class RetentionError(Exception):
    pass


def active_policy(db: Session) -> Policy:
    policy = db.scalar(select(Policy).where(Policy.status == "active"))
    if policy is None:
        raise RetentionError("No active policy")
    return policy


def audit(db: Session, action: str, detail: dict, subscriber_id: int | None = None,
          attempt_id: int | None = None) -> None:
    db.add(AuditLog(action=action, detail=detail, subscriber_id=subscriber_id, attempt_id=attempt_id))


def _simulated(calls: list, method: str, path: str) -> None:
    calls.append({"method": method, "path": path, "status": "simulated", "simulated": True,
                  "at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "note": "Demo subscriber without a real sandbox subscription: PayPal call not sent"})


def _live(sub: Subscriber) -> bool:
    return sub.is_live and bool(sub.paypal_subscription_id) and cat.paypal() is not None


def read_history(db: Session, sub: Subscriber, calls: list) -> tuple[SubscriberContext, dict]:
    """The agent's tool call: subscriber facts from PayPal (live) or the demo record."""
    extra: dict = {"tenure_months": max(0, (utcnow() - _aware(sub.started_at)).days // 30)}
    if _live(sub):
        pp = cat.paypal()
        details = pp_subs.get(pp, sub.paypal_subscription_id, record=calls)
        reconcile(sub, details.get("status", ""))
        info = details.get("billing_info", {})
        sub.months_paid = sum(c.get("cycles_completed", 0) for c in info.get("cycle_executions", []))
        sub.failed_payments = int(info.get("failed_payments_count", 0))
        if (p := cat.plan_by_paypal_id(db, details.get("plan_id", ""))) is not None:
            sub.plan_key = p.key
        txs = pp_subs.transactions(pp, sub.paypal_subscription_id, record=calls)
        extra |= {"payments_in_paypal": len(txs), "subscribed_since": details.get("start_time"),
                  "last_payment": (info.get("last_payment") or {}).get("time"),
                  "source": "PayPal Subscriptions API"}
    else:
        _simulated(calls, "GET", f"/v1/billing/subscriptions/{sub.paypal_subscription_id}")
        extra["source"] = "demo record"
    ctx = SubscriberContext(plan_key=sub.plan_key, months_paid=sub.months_paid,
                            failed_payments=sub.failed_payments, offers_received=sub.offers_received,
                            state=sub.state.value)
    return ctx, extra


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


WIN_BACK_SITUATION = ("Already cancelled inside PayPal. Any offer means resubscribing; choose the come-back "
                      "offer most likely to bring them back, and 'cancel' (no offer) only if none fits.")


def win_back_inputs(ctx: SubscriberContext, rules: PolicyRules, extra: dict) -> tuple[SubscriberContext, PolicyRules, dict]:
    """Win-back offers are for coming back: evaluate as if active, never offer a pause, and tell the agent."""
    return (SubscriberContext(**{**ctx.__dict__, "state": "ACTIVE"}),
            rules.model_copy(update={"pause_enabled": False}), {**extra, "situation": WIN_BACK_SITUATION})


def start_attempt(db: Session, sub: Subscriber, reason: str, channel: str = "save_page") -> CancelAttempt:
    if sub.state == S.CANCELLED and channel == "save_page":
        raise RetentionError("This subscription is already cancelled")
    policy = active_policy(db)
    rules = PolicyRules.model_validate(policy.rules)
    calls: list = []
    ctx, extra = read_history(db, sub, calls)
    if channel == "win_back":
        ctx, rules, extra = win_back_inputs(ctx, rules, extra)
    decision = decide(reason, ctx, cat.catalogue(db), rules, db, extra)

    attempt = CancelAttempt(
        subscriber_id=sub.id, channel=channel, reason_text=reason, category=decision.category,
        reason_summary=decision.reason_summary,
        context={**ctx.__dict__, **extra, **({"ai_model": decision.ai_model} if decision.ai_model else {})},
        allowed_actions=[a.to_dict() for a in decision.allowed], proposed_action_id=decision.proposed_action_id,
        action=decision.action.to_dict(), guardrail=decision.guardrail,
        guardrail_note=" ".join(decision.guardrail_notes) or None, injection_suspected=decision.injection_suspected,
        message=decision.message, rationale=decision.rationale, ai_source=decision.ai_source,
        outcome="offered" if decision.action.type != "cancel" else "no_offer",
        paypal_calls=calls, policy_version=policy.version)
    if decision.action.type != "cancel":
        sub.offers_received += 1
    db.add(attempt)
    db.flush()
    audit(db, "agent_decision", {
        "reason": reason, "category": decision.category, "ai_source": decision.ai_source,
        "ai_model": decision.ai_model,
        "allowed": [a.id for a in decision.allowed], "proposed": decision.proposed_action_id,
        "final": decision.action.id, "guardrail": decision.guardrail, "notes": decision.guardrail_notes,
        "paypal_calls": calls}, sub.id, attempt.id)
    db.commit()
    return attempt


def _action(attempt: CancelAttempt) -> Action:
    return Action(**attempt.action)


def _recording_failures(step: str):
    """Run a step that calls PayPal; if PayPal fails, keep the failed call (with its debug_id) on the
    attempt and in the audit log before the error goes back to the user."""
    def wrap(fn):
        def run(db: Session, attempt: CancelAttempt) -> CancelAttempt:
            calls = list(attempt.paypal_calls)
            try:
                return fn(db, attempt, calls)
            except PayPalError as e:
                db.rollback()
                attempt.paypal_calls = calls
                audit(db, "paypal_call_failed", {"step": step, "error": e.name, "debug_id": e.debug_id,
                                                 "paypal_calls": calls[-1:]}, attempt.subscriber_id, attempt.id)
                db.commit()
                raise
        return run
    return wrap


@_recording_failures("accept")
def accept(db: Session, attempt: CancelAttempt, calls: list) -> CancelAttempt:
    if attempt.outcome not in ("offered",):
        raise RetentionError(f"Offer is already {attempt.outcome}")
    sub, action = attempt.subscriber, _action(attempt)
    before, settings = len(calls), get_settings()
    key = f"saveflow-attempt-{attempt.id}-{action.id}"

    if action.type == "pause":
        if _live(sub):
            pp_subs.suspend(cat.paypal(), sub.paypal_subscription_id,
                            f"Paused {action.months} month(s) via SaveFlow", key, record=calls)
        else:
            _simulated(calls, "POST", f"/v1/billing/subscriptions/{sub.paypal_subscription_id}/suspend")
        transition(sub, S.SUSPENDED)
        sub.resume_at = utcnow() + timedelta(days=30 * action.months)
        _saved(attempt, action)
    elif action.type in ("discount", "downgrade"):
        target = cat.plan(db, action.plan_key or "")
        if target is None:
            raise RetentionError("Target plan missing from catalogue")
        if attempt.channel == "win_back":
            path = "/v1/billing/subscriptions"
            if _live(sub) and target.paypal_plan_id:
                created = pp_subs.create(cat.paypal(), target.paypal_plan_id,
                                         f"{settings.public_url}/approved?attempt={attempt.id}",
                                         f"{settings.public_url}/approved?attempt={attempt.id}&cancelled=1",
                                         key, record=calls)
                attempt.approve_url = pp_subs.approve_link(created)
                attempt.context = {**attempt.context, "new_subscription_id": created.get("id")}
                attempt.outcome = "awaiting_approval"
            else:
                _simulated(calls, "POST", path)
                _saved(attempt, action)
                sub.plan_key = target.key
        elif _live(sub) and target.paypal_plan_id:
            attempt.approve_url = pp_subs.revise(
                cat.paypal(), sub.paypal_subscription_id, target.paypal_plan_id,
                f"{settings.public_url}/approved?attempt={attempt.id}",
                f"{settings.public_url}/approved?attempt={attempt.id}&cancelled=1", key, record=calls)
            attempt.outcome = "awaiting_approval" if attempt.approve_url else "offered"
            if not attempt.approve_url:  # PayPal applied it without approval
                sub.plan_key = target.key
                _saved(attempt, action)
        else:
            _simulated(calls, "POST", f"/v1/billing/subscriptions/{sub.paypal_subscription_id}/revise")
            sub.plan_key = target.key
            _saved(attempt, action)
    else:
        return _decline(db, attempt, calls)

    attempt.paypal_calls = calls
    audit(db, "offer_accepted", {"action": action.id, "outcome": attempt.outcome, "paypal_calls": calls[before:]},
          sub.id, attempt.id)
    db.commit()
    return attempt


def _saved(attempt: CancelAttempt, action: Action) -> None:
    attempt.outcome = "saved"
    attempt.revenue_kept_12m = action.revenue_kept_12m
    attempt.decided_at = utcnow()


def confirm_approval(db: Session, attempt: CancelAttempt) -> CancelAttempt:
    """After the buyer returns from PayPal: check PayPal (the source of truth) before marking it saved."""
    if attempt.outcome != "awaiting_approval":
        return attempt
    sub, action, calls = attempt.subscriber, _action(attempt), list(attempt.paypal_calls)
    target = cat.plan(db, action.plan_key or "")
    sid = attempt.context.get("new_subscription_id") or sub.paypal_subscription_id
    details = pp_subs.get(cat.paypal(), sid, record=calls)
    attempt.paypal_calls = calls
    if attempt.channel == "win_back":
        ok = details.get("status") in ("ACTIVE", "APPROVED")
        if ok:
            sub.paypal_subscription_id, sub.state, sub.plan_key = sid, S.ACTIVE, target.key
    else:
        ok = target is not None and details.get("plan_id") == target.paypal_plan_id
        if ok:
            sub.plan_key = target.key
    if ok:
        _saved(attempt, action)
        audit(db, "approval_confirmed", {"paypal_status": details.get("status"),
                                         "plan_id": details.get("plan_id")}, sub.id, attempt.id)
    db.commit()
    return attempt


def _decline(db: Session, attempt: CancelAttempt, calls: list) -> CancelAttempt:
    """The subscriber says no: cancel for real. Cancelling is always allowed."""
    if attempt.outcome in ("saved", "cancelled"):
        raise RetentionError(f"Offer is already {attempt.outcome}")
    sub = attempt.subscriber
    if attempt.channel == "save_page" and sub.state != S.CANCELLED:
        if _live(sub):
            pp_subs.cancel(cat.paypal(), sub.paypal_subscription_id, "Cancelled by subscriber via SaveFlow",
                           f"saveflow-attempt-{attempt.id}-cancel", record=calls)
        else:
            _simulated(calls, "POST", f"/v1/billing/subscriptions/{sub.paypal_subscription_id}/cancel")
        transition(sub, S.CANCELLED)
    attempt.outcome = "cancelled" if attempt.channel == "save_page" else "declined"
    attempt.decided_at = utcnow()
    attempt.paypal_calls = calls
    audit(db, "subscriber_declined", {"channel": attempt.channel, "paypal_calls": calls[-1:]}, sub.id, attempt.id)
    db.commit()
    return attempt


decline = _recording_failures("decline")(_decline)

_PCT = re.compile(r"(\d{1,3})\s*(%|percent|per cent)", re.I)
_MONTHS = re.compile(r"(\d{1,2})\s*(months?|mahine|meses)", re.I)


def counter(db: Session, attempt: CancelAttempt, text: str) -> CancelAttempt:
    """One counter-offer, strictly inside the allowed set computed for this attempt."""
    if attempt.outcome != "offered":
        raise RetentionError("There is no open offer to negotiate")
    if attempt.counter_used:
        raise RetentionError("Only one counter-offer is allowed")
    allowed = [Action(**a) for a in attempt.allowed_actions]
    current = _action(attempt)
    pct = _PCT.search(text)
    wanted_pct = int(pct.group(1)) if pct else (50 if re.search(r"\bhalf\b|aadha|mitad", text, re.I) else None)
    months = _MONTHS.search(text)
    discounts = [a for a in allowed if a.type == "discount"]
    pauses = [a for a in allowed if a.type == "pause"]

    new, note = current, ""
    if wanted_pct is not None or re.search(r"discount|cheaper|lower|\bless\b|\boff\b|\bkam\b|descuento", text, re.I):
        if discounts:
            fits = [a for a in discounts if wanted_pct is None or a.pct <= wanted_pct]
            new = (fits or discounts)[-1]
            if wanted_pct and wanted_pct > discounts[-1].pct:
                note = f"Requested {wanted_pct}%; the merchant's limit allows at most {discounts[-1].pct}%."
        else:
            note = "No discount is allowed for this subscriber under the merchant's policy."
    elif months or re.search(r"pause|break|longer", text, re.I):
        if pauses:
            want = int(months.group(1)) if months else pauses[-1].months
            new = max((a for a in pauses if a.months <= want), key=lambda a: a.months, default=pauses[0])
            if want > pauses[-1].months:
                note = f"Requested a {want}-month pause; the merchant allows at most {pauses[-1].months}."
        else:
            note = "Pausing is not allowed for this subscriber under the merchant's policy."

    attempt.counter_used = True
    if new.id != current.id:
        attempt.action = new.to_dict()
        prefix = "The best we can do: " if note else "Deal: "
        attempt.message = prefix + template_message(new, attempt.subscriber.months_paid)
    else:
        attempt.message = ("That's the best offer we're able to make. " if note else "") + (attempt.message or "")
    audit(db, "counter_offer", {"request": text, "from": current.id, "to": new.id, "note": note},
          attempt.subscriber_id, attempt.id)
    attempt.guardrail_note = " ".join(x for x in [attempt.guardrail_note, note] if x) or None
    db.commit()
    return attempt


def resume_due(db: Session) -> int:
    """Scheduled resume after a pause. Returns how many subscriptions were reactivated."""
    due = db.scalars(select(Subscriber).where(Subscriber.state == S.SUSPENDED, Subscriber.resume_at <= utcnow()))
    return sum(resume(db, sub, "Pause period ended") for sub in list(due))


def resume(db: Session, sub: Subscriber, reason: str) -> bool:
    calls: list = []
    if _live(sub):
        pp_subs.activate(cat.paypal(), sub.paypal_subscription_id, reason,
                         f"saveflow-resume-{sub.id}-{int(_aware(sub.resume_at or utcnow()).timestamp())}", record=calls)
    else:
        _simulated(calls, "POST", f"/v1/billing/subscriptions/{sub.paypal_subscription_id}/activate")
    transition(sub, S.ACTIVE)
    sub.resume_at = None
    audit(db, "pause_resumed", {"reason": reason, "paypal_calls": calls}, sub.id)
    db.commit()
    return True


__all__ = ["CANCEL", "RetentionError", "accept", "confirm_approval", "counter", "decline", "resume",
           "resume_due", "start_attempt", "active_policy", "audit"]
