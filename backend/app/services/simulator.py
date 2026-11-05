"""What-if policy simulator: replay past save attempts against a proposed policy.
Deterministic and LLM-free: it keeps the AI's original pick when the new policy still allows it,
otherwise uses the safe default. It shows offers that WOULD have been made, not whether they'd be accepted."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CancelAttempt
from app.policy.engine import Action, PlanInfo, SubscriberContext, allowed_actions, enforce
from app.policy.rules import PolicyRules

_CTX_FIELDS = ("plan_key", "months_paid", "failed_payments", "offers_received", "state")


def simulate(db: Session, rules: PolicyRules, catalogue: dict[str, PlanInfo]) -> dict:
    rows, totals = [], {"attempts": 0, "changed": 0, "no_offer_before": 0, "no_offer_after": 0,
                        "revenue_offered_before": 0.0, "revenue_offered_after": 0.0}
    attempts = db.scalars(select(CancelAttempt).where(CancelAttempt.channel == "save_page")
                          .order_by(CancelAttempt.created_at.desc()))
    for a in attempts:
        if not a.action or not a.category or not a.context:
            continue
        ctx = SubscriberContext(**{k: a.context[k] for k in _CTX_FIELDS if k in a.context})
        if a.channel == "save_page":
            ctx = SubscriberContext(**{**ctx.__dict__, "state": "ACTIVE"})
        before = Action(**a.action)
        allowed = allowed_actions(rules, ctx, catalogue, a.category)
        after = enforce(before.id, allowed, a.category, rules).action
        totals["attempts"] += 1
        totals["changed"] += before.id != after.id
        totals["no_offer_before"] += before.type == "cancel"
        totals["no_offer_after"] += after.type == "cancel"
        totals["revenue_offered_before"] += before.revenue_kept_12m
        totals["revenue_offered_after"] += after.revenue_kept_12m
        rows.append({"attempt_id": a.id, "subscriber": a.subscriber.name, "category": a.category,
                     "reason": a.reason_text, "months_paid": ctx.months_paid,
                     "original_offer": before.label, "original_outcome": a.outcome,
                     "simulated_offer": after.label, "changed": before.id != after.id,
                     "revenue_before": before.revenue_kept_12m, "revenue_after": after.revenue_kept_12m})
    totals["revenue_offered_before"] = round(totals["revenue_offered_before"], 2)
    totals["revenue_offered_after"] = round(totals["revenue_offered_after"], 2)
    return {"rows": rows, "totals": totals}
