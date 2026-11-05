"""The demo merchant's plan catalogue, its PayPal plan ids, and the shared PayPal client."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Plan
from app.paypal import subscriptions as pp_subs
from app.paypal.client import PayPalClient, PayPalError
from app.policy.engine import PlanInfo

log = logging.getLogger(__name__)

PRODUCT_NAME = "Sunrise Yoga Studio - Online Classes"
DEMO_PLANS: list[dict] = [
    {"key": "pro", "name": "Sunrise Yoga Pro (monthly)", "price": 10.0, "base_key": "pro"},
    {"key": "pro_off20", "name": "Sunrise Yoga Pro - 20% off for 2 months", "price": 10.0, "trial_price": 8.0,
     "discount_pct": 20, "discount_months": 2, "base_key": "pro"},
    {"key": "pro_off30", "name": "Sunrise Yoga Pro - 30% off for 2 months", "price": 10.0, "trial_price": 7.0,
     "discount_pct": 30, "discount_months": 2, "base_key": "pro"},
    {"key": "pro_off50", "name": "Sunrise Yoga Pro - 50% off for 1 month", "price": 10.0, "trial_price": 5.0,
     "discount_pct": 50, "discount_months": 1, "base_key": "pro"},
    {"key": "lite", "name": "Sunrise Yoga Lite (monthly)", "price": 5.0, "base_key": "lite"},
]

_paypal: PayPalClient | None = None


def paypal() -> PayPalClient | None:
    """The shared client, or None when PayPal keys are not configured (simulated mode)."""
    global _paypal
    if _paypal is None and get_settings().paypal_configured:
        _paypal = PayPalClient(get_settings())
    return _paypal


def seed_plans(db: Session, merchant_id: int) -> None:
    for spec in DEMO_PLANS:
        db.add(Plan(merchant_id=merchant_id, key=spec["key"], name=spec["name"],
                    price=spec.get("trial_price", spec["price"]), regular_price=spec["price"],
                    base_key=spec["base_key"], discount_pct=spec.get("discount_pct", 0),
                    discount_months=spec.get("discount_months", 0)))


def sync_with_paypal(db: Session) -> str:
    """Find or create every plan in PayPal and store the ids. Returns a status line."""
    pp = paypal()
    if pp is None:
        return "PayPal not configured: running in simulated mode"
    try:
        ids = pp_subs.ensure_catalogue(pp, PRODUCT_NAME, DEMO_PLANS, get_settings().currency)
    except (PayPalError, OSError) as e:
        log.error("Could not sync plans with PayPal: %s", e)
        return f"PayPal plan sync failed: {e}"
    for plan in db.scalars(select(Plan)):
        plan.paypal_plan_id = ids.get(plan.key)
    db.commit()
    return f"PayPal plans synced ({len(ids)})"


def catalogue(db: Session) -> dict[str, PlanInfo]:
    return {p.key: PlanInfo(key=p.key, name=p.name, price=p.price, base_key=p.base_key,
                            discount_pct=p.discount_pct, discount_months=p.discount_months)
            for p in db.scalars(select(Plan))}


def plan(db: Session, key: str) -> Plan | None:
    return db.scalar(select(Plan).where(Plan.key == key))


def plan_by_paypal_id(db: Session, paypal_plan_id: str) -> Plan | None:
    return db.scalar(select(Plan).where(Plan.paypal_plan_id == paypal_plan_id))
