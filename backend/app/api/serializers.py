from app.models import AuditLog, CancelAttempt, Subscriber


def attempt_row(a: CancelAttempt) -> dict:
    action = a.action or {}
    return {
        "id": a.id, "created_at": a.created_at.isoformat(), "subscriber_id": a.subscriber_id,
        "subscriber": a.subscriber.name, "is_live": a.subscriber.is_live, "channel": a.channel,
        "reason": a.reason_text, "category": a.category, "reason_summary": a.reason_summary,
        "offer": action.get("label"), "offer_type": action.get("type"), "offer_id": action.get("id"),
        "needs_buyer_approval": action.get("needs_buyer_approval", False), "outcome": a.outcome,
        "revenue_kept_12m": a.revenue_kept_12m, "potential_revenue_12m": action.get("revenue_kept_12m", 0),
        "guardrail": a.guardrail, "injection_suspected": a.injection_suspected, "ai_source": a.ai_source,
        "months_paid": (a.context or {}).get("months_paid"), "plan": (a.context or {}).get("plan_key"),
        "policy_version": a.policy_version, "is_demo_data": a.is_demo_data, "counter_used": a.counter_used,
        "paypal_call_count": len([c for c in a.paypal_calls or [] if not c.get("simulated")]),
    }


def attempt_detail(a: CancelAttempt, audit: list[AuditLog]) -> dict:
    return {**attempt_row(a), "message": a.message, "rationale": a.rationale,
            "proposed_action_id": a.proposed_action_id, "allowed_actions": a.allowed_actions,
            "guardrail_note": a.guardrail_note, "context": a.context, "paypal_calls": a.paypal_calls,
            "approve_url": a.approve_url, "audit": [audit_row(x) for x in audit]}


def subscriber_row(s: Subscriber) -> dict:
    return {"id": s.id, "name": s.name, "plan_key": s.plan_key, "state": s.state.value, "is_live": s.is_live,
            "months_paid": s.months_paid, "failed_payments": s.failed_payments,
            "offers_received": s.offers_received, "persona": s.persona,
            "paypal_subscription_id": s.paypal_subscription_id,
            "resume_at": s.resume_at.isoformat() if s.resume_at else None}


def audit_row(x: AuditLog) -> dict:
    return {"id": x.id, "created_at": x.created_at.isoformat(), "action": x.action, "subscriber_id": x.subscriber_id,
            "attempt_id": x.attempt_id, "detail": x.detail}
