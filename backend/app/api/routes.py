import json
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.compiler import catalogue_warnings, compile_policy
from app.api.serializers import attempt_detail, attempt_row, audit_row, subscriber_row
from app.config import get_settings
from app.db import get_db
from app.models import AuditLog, CancelAttempt, Policy, Subscriber, SubscriptionState as S
from app.paypal import subscriptions as pp_subs
from app.policy.rules import PolicyRules, diff, summarize
from app.services import catalogue as cat
from app.services import retention, webhooks
from app.services.simulator import simulate

router = APIRouter(prefix="/api")


def _attempt(db: Session, attempt_id: int) -> CancelAttempt:
    a = db.get(CancelAttempt, attempt_id)
    if a is None:
        raise HTTPException(404, "Attempt not found")
    return a


def _subscriber(db: Session, subscriber_id: int) -> Subscriber:
    s = db.get(Subscriber, subscriber_id)
    if s is None:
        raise HTTPException(404, "Subscriber not found")
    return s


def _detail(db: Session, a: CancelAttempt) -> dict:
    audit = db.scalars(select(AuditLog).where(AuditLog.attempt_id == a.id).order_by(AuditLog.id)).all()
    return attempt_detail(a, list(audit))


# ------------------------------------------------------------------ config & dashboard
@router.get("/config")
def config(db: Session = Depends(get_db)) -> dict:
    s, pro = get_settings(), cat.plan(db, "pro")
    return {"paypal_client_id": s.paypal_client_id if s.paypal_configured else None,
            "pro_plan_id": pro.paypal_plan_id if pro else None, "currency": s.currency,
            "demo_mode": s.demo_mode, "paypal_configured": s.paypal_configured,
            "gemini_configured": s.gemini_configured, "gemini_model": s.gemini_model,
            "plans": [{"key": k, "name": p.name, "price": p.price} for k, p in cat.catalogue(db).items()]}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    attempts = db.scalars(select(CancelAttempt).where(CancelAttempt.channel == "save_page")).all()
    total = len(attempts)
    saved = [a for a in attempts if a.outcome == "saved"]
    reasons = Counter(a.category for a in attempts if a.category)
    by_reason = []
    for category, n in reasons.most_common():
        cat_saved = sum(1 for a in saved if a.category == category)
        by_reason.append({"category": category, "attempts": n, "saved": cat_saved})
    return {
        "attempts": total, "saved": len(saved), "save_rate": round(len(saved) / total, 3) if total else 0,
        "revenue_kept_12m": round(sum(a.revenue_kept_12m for a in saved), 2),
        "blocked_by_guardrail": sum(1 for a in attempts if a.guardrail == "blocked"),
        "injection_attempts": sum(1 for a in attempts if a.injection_suspected),
        "awaiting_approval": sum(1 for a in attempts if a.outcome == "awaiting_approval"),
        "win_backs": db.query(CancelAttempt).filter(CancelAttempt.channel == "win_back").count(),
        "by_reason": by_reason,
        "demo_data_rows": sum(1 for a in attempts if a.is_demo_data),
    }


@router.get("/attempts")
def attempts(channel: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    q = select(CancelAttempt).order_by(CancelAttempt.created_at.desc())
    if channel:
        q = q.where(CancelAttempt.channel == channel)
    return [attempt_row(a) for a in db.scalars(q)]


@router.get("/attempts/{attempt_id}")
def attempt(attempt_id: int, db: Session = Depends(get_db)) -> dict:
    return _detail(db, _attempt(db, attempt_id))


@router.get("/audit")
def audit(limit: int = 500, db: Session = Depends(get_db)) -> list[dict]:
    return [audit_row(x) for x in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))]


# ------------------------------------------------------------------ subscriber cancel flow
@router.get("/subscribers")
def subscribers(featured: bool = True, db: Session = Depends(get_db)) -> list[dict]:
    q = select(Subscriber).order_by(Subscriber.is_live.desc(), Subscriber.id)
    if featured:
        q = q.where((Subscriber.persona.is_not(None)) | Subscriber.is_live)
    return [subscriber_row(s) for s in db.scalars(q)]


class LiveSubscriberIn(BaseModel):
    subscription_id: str = Field(min_length=3, max_length=64)
    name: str = Field("Sandbox buyer", max_length=120)


@router.post("/subscribers/live")
def register_live(body: LiveSubscriberIn, db: Session = Depends(get_db)) -> dict:
    """Called after the buyer approves the PayPal Subscribe button. Verified against PayPal."""
    pp = cat.paypal()
    if pp is None:
        raise HTTPException(400, "PayPal is not configured on this server")
    existing = db.scalar(select(Subscriber).where(Subscriber.paypal_subscription_id == body.subscription_id))
    if existing:
        return subscriber_row(existing)
    details = pp_subs.get(pp, body.subscription_id)
    plan = cat.plan_by_paypal_id(db, details.get("plan_id", ""))
    if plan is None:
        raise HTTPException(400, "That subscription is not for one of this merchant's plans")
    merchant_id = db.scalar(select(Policy.merchant_id).where(Policy.status == "active"))
    sub = Subscriber(merchant_id=merchant_id, name=body.name, plan_key=plan.key, is_live=True,
                     paypal_subscription_id=body.subscription_id,
                     persona="Live sandbox subscription: offers here call the real PayPal API.")
    db.add(sub)
    retention.audit(db, "live_subscriber_registered", {"subscription_id": body.subscription_id,
                                                       "paypal_status": details.get("status")})
    db.commit()
    return subscriber_row(sub)


class CancelIn(BaseModel):
    subscriber_id: int
    reason: str = Field(min_length=1, max_length=1500)


@router.post("/cancel")
def start_cancel(body: CancelIn, db: Session = Depends(get_db)) -> dict:
    sub = _subscriber(db, body.subscriber_id)
    return _detail(db, retention.start_attempt(db, sub, body.reason.strip()))


@router.post("/attempts/{attempt_id}/accept")
def accept(attempt_id: int, db: Session = Depends(get_db)) -> dict:
    return _detail(db, retention.accept(db, _attempt(db, attempt_id)))


class CounterIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.post("/attempts/{attempt_id}/counter")
def counter(attempt_id: int, body: CounterIn, db: Session = Depends(get_db)) -> dict:
    return _detail(db, retention.counter(db, _attempt(db, attempt_id), body.text))


@router.post("/attempts/{attempt_id}/decline")
def decline(attempt_id: int, db: Session = Depends(get_db)) -> dict:
    return _detail(db, retention.decline(db, _attempt(db, attempt_id)))


@router.post("/attempts/{attempt_id}/confirm")
def confirm(attempt_id: int, db: Session = Depends(get_db)) -> dict:
    return _detail(db, retention.confirm_approval(db, _attempt(db, attempt_id)))


# ------------------------------------------------------------------ policy
def _active(db: Session) -> Policy:
    return retention.active_policy(db)


@router.get("/policy")
def policy(db: Session = Depends(get_db)) -> dict:
    p = _active(db)
    rules = PolicyRules.model_validate(p.rules)
    history = db.scalars(select(Policy).order_by(Policy.version.desc())).all()
    return {"version": p.version, "rules": rules.model_dump(), "source_text": p.source_text,
            "summary": summarize(rules), "warnings": catalogue_warnings(rules, cat.catalogue(db)),
            "history": [{"version": h.version, "status": h.status, "created_at": h.created_at.isoformat(),
                         "source_text": h.source_text} for h in history]}


class CompileIn(BaseModel):
    text: str = Field(min_length=5, max_length=3000)


@router.post("/policy/compile")
def compile_(body: CompileIn, db: Session = Depends(get_db)) -> dict:
    current = PolicyRules.model_validate(_active(db).rules)
    result = compile_policy(body.text, current, cat.catalogue(db), db)
    db.commit()  # keep the LLM cache entry
    return {"ok": result.ok, "rules": result.rules.model_dump() if result.rules else None,
            "summary": result.summary, "changes": result.changes, "warnings": result.warnings,
            "errors": result.errors, "ai_source": result.ai_source}


class RulesIn(BaseModel):
    rules: dict
    source_text: str | None = None


def _validate_rules(raw: dict) -> PolicyRules:
    try:
        return PolicyRules.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(422, [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()])


@router.post("/policy/preview")
def preview(body: RulesIn, db: Session = Depends(get_db)) -> dict:
    rules = _validate_rules(body.rules)
    current = PolicyRules.model_validate(_active(db).rules)
    return {"rules": rules.model_dump(), "summary": summarize(rules), "changes": diff(current, rules),
            "warnings": catalogue_warnings(rules, cat.catalogue(db))}


@router.post("/policy/apply")
def apply(body: RulesIn, db: Session = Depends(get_db)) -> dict:
    """The merchant approved the summary: code validates again, then the new version goes live."""
    rules = _validate_rules(body.rules)
    old = _active(db)
    old.status = "superseded"
    new = Policy(merchant_id=old.merchant_id, version=old.version + 1, status="active",
                 rules=rules.model_dump(), source_text=body.source_text or old.source_text)
    db.add(new)
    retention.audit(db, "policy_applied", {"version": new.version,
                                           "changes": diff(PolicyRules.model_validate(old.rules), rules)})
    db.commit()
    return policy(db)


@router.post("/simulate")
def simulate_(body: RulesIn, db: Session = Depends(get_db)) -> dict:
    return simulate(db, _validate_rules(body.rules), cat.catalogue(db))


# ------------------------------------------------------------------ webhooks
@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    s, pp = get_settings(), cat.paypal()
    raw = await request.body()
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Body is not JSON")
    if pp is None or not s.paypal_webhook_id:
        raise HTTPException(503, "Webhook verification is not configured (PAYPAL_WEBHOOK_ID); event rejected")
    if not pp_subs.verify_webhook(pp, dict(request.headers), event, s.paypal_webhook_id):
        retention.audit(db, "webhook_rejected", {"event_id": event.get("id"), "reason": "signature"})
        db.commit()
        raise HTTPException(400, "Signature verification failed")
    result, duplicate = webhooks.process(db, event, "SUCCESS")
    return {"result": result, "duplicate": duplicate}


# ------------------------------------------------------------------ demo controls
def _demo_only() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(404)


class SimulateCancelIn(BaseModel):
    event_id: str | None = None  # resend an earlier id to show duplicate handling


@router.post("/demo/cancel-in-paypal/{subscriber_id}", dependencies=[Depends(_demo_only)])
def demo_cancel_in_paypal(subscriber_id: int, body: SimulateCancelIn, db: Session = Depends(get_db)) -> dict:
    """Simulates the subscriber cancelling inside PayPal: a BILLING.SUBSCRIPTION.CANCELLED event
    goes through the same handler as real webhooks (only signature verification is skipped, and labelled)."""
    sub = _subscriber(db, subscriber_id)
    event = {"id": body.event_id or f"WH-SIM-{uuid.uuid4().hex[:16].upper()}",
             "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
             "resource": {"id": sub.paypal_subscription_id, "status": "CANCELLED"}}
    if sub.is_live and cat.paypal() is not None and sub.state != S.CANCELLED:
        pp_subs.cancel(cat.paypal(), sub.paypal_subscription_id, "Cancelled in PayPal (demo)",
                       f"demo-cancel-{sub.id}")
    result, duplicate = webhooks.process(db, event, "SIMULATED")
    return {"event_id": event["id"], "result": result, "duplicate": duplicate}


@router.post("/demo/resume/{subscriber_id}", dependencies=[Depends(_demo_only)])
def demo_resume(subscriber_id: int, db: Session = Depends(get_db)) -> dict:
    """Skip ahead: run the scheduled resume now."""
    sub = _subscriber(db, subscriber_id)
    if sub.state != S.SUSPENDED:
        raise HTTPException(409, f"Subscriber is {sub.state.value}, not paused")
    retention.resume(db, sub, "Pause ended (demo skip-ahead)")
    return subscriber_row(sub)


@router.post("/demo/reset", dependencies=[Depends(_demo_only)])
def demo_reset() -> dict:
    from app.main import reset_database
    reset_database()
    return {"status": "reset"}
