"""PayPal Subscriptions, Catalog and Webhook calls SaveFlow makes. Every function takes a `record`
list so the caller can store exactly which PayPal calls a decision caused."""
from datetime import datetime, timedelta, timezone

from app.paypal.client import PayPalClient

SUBS = "/v1/billing/subscriptions"


def approve_link(resp: dict) -> str | None:
    return next((l["href"] for l in resp.get("links", []) if l.get("rel") == "approve"), None)


def app_context(return_url: str, cancel_url: str, user_action: str = "CONTINUE") -> dict:
    return {"brand_name": "Sunrise Yoga Studio", "user_action": user_action,
            "shipping_preference": "NO_SHIPPING", "return_url": return_url, "cancel_url": cancel_url}


def get(pp: PayPalClient, sid: str, record: list | None = None) -> dict:
    return pp.call("GET", f"{SUBS}/{sid}", record=record)


def transactions(pp: PayPalClient, sid: str, days: int = 400, record: list | None = None) -> list[dict]:
    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    r = pp.call("GET", f"{SUBS}/{sid}/transactions", record=record,
                params={"start_time": (now - timedelta(days=days)).strftime(fmt),
                        "end_time": (now + timedelta(days=1)).strftime(fmt)})
    return r.get("transactions", [])


def suspend(pp: PayPalClient, sid: str, reason: str, key: str, record: list | None = None) -> None:
    pp.call("POST", f"{SUBS}/{sid}/suspend", {"reason": reason[:127]}, idempotency_key=key, record=record)


def activate(pp: PayPalClient, sid: str, reason: str, key: str, record: list | None = None) -> None:
    pp.call("POST", f"{SUBS}/{sid}/activate", {"reason": reason[:127]}, idempotency_key=key, record=record)


def cancel(pp: PayPalClient, sid: str, reason: str, key: str, record: list | None = None) -> None:
    pp.call("POST", f"{SUBS}/{sid}/cancel", {"reason": reason[:127]}, idempotency_key=key, record=record)


def revise(pp: PayPalClient, sid: str, plan_id: str, return_url: str, cancel_url: str, key: str,
           record: list | None = None) -> str | None:
    """Switch plan. PayPal needs the buyer to approve, so this returns the approval link."""
    r = pp.call("POST", f"{SUBS}/{sid}/revise",
                {"plan_id": plan_id, "application_context": app_context(return_url, cancel_url)},
                idempotency_key=key, record=record)
    return approve_link(r)


def create(pp: PayPalClient, plan_id: str, return_url: str, cancel_url: str, key: str | None = None,
           record: list | None = None) -> dict:
    return pp.call("POST", SUBS, {"plan_id": plan_id,
                                  "application_context": app_context(return_url, cancel_url, "SUBSCRIBE_NOW")},
                   idempotency_key=key, record=record)


def verify_webhook(pp: PayPalClient, headers: dict, event: dict, webhook_id: str) -> bool:
    h = {k.lower(): v for k, v in headers.items()}
    r = pp.call("POST", "/v1/notifications/verify-webhook-signature", {
        "auth_algo": h.get("paypal-auth-algo"), "cert_url": h.get("paypal-cert-url"),
        "transmission_id": h.get("paypal-transmission-id"), "transmission_sig": h.get("paypal-transmission-sig"),
        "transmission_time": h.get("paypal-transmission-time"), "webhook_id": webhook_id, "webhook_event": event})
    return r.get("verification_status") == "SUCCESS"


# ---------------------------------------------------------------- catalogue (merchant setup)
def _plan_body(product_id: str, name: str, price: float, currency: str,
               trial_price: float | None = None, trial_months: int = 0) -> dict:
    def cycle(tenure: str, seq: int, total: int, value: float) -> dict:
        return {"frequency": {"interval_unit": "MONTH", "interval_count": 1}, "tenure_type": tenure,
                "sequence": seq, "total_cycles": total,
                "pricing_scheme": {"fixed_price": {"value": f"{value:.2f}", "currency_code": currency}}}
    cycles = []
    if trial_price is not None and trial_months:
        # A discount "for N months" is a trial phase at the lower price, then the regular price
        # resumes automatically: no second buyer approval needed to end the discount.
        cycles.append(cycle("TRIAL", 1, trial_months, trial_price))
    cycles.append(cycle("REGULAR", len(cycles) + 1, 0, price))
    return {"product_id": product_id, "name": name, "status": "ACTIVE", "billing_cycles": cycles,
            "payment_preferences": {"auto_bill_outstanding": True, "payment_failure_threshold": 2}}


def ensure_catalogue(pp: PayPalClient, product_name: str, plans: list[dict], currency: str) -> dict[str, str]:
    """Find or create the product and each plan by name, so restarts never create duplicates.
    PayPal is the source of truth; returns {plan key: PayPal plan id}."""
    products = pp.call("GET", "/v1/catalogs/products", params={"page_size": 20, "total_required": "true"})
    product = next((p for p in products.get("products", []) if p["name"] == product_name), None)
    page = 2
    while product is None and page <= products.get("total_pages", 1):
        more = pp.call("GET", "/v1/catalogs/products", params={"page_size": 20, "page": page})
        product = next((p for p in more.get("products", []) if p["name"] == product_name), None)
        page += 1
    if product is None:
        product = pp.call("POST", "/v1/catalogs/products", {"name": product_name, "type": "SERVICE"})

    existing = pp.call("GET", "/v1/billing/plans", params={"product_id": product["id"], "page_size": 20})
    by_name = {p["name"]: p["id"] for p in existing.get("plans", []) if p.get("status") == "ACTIVE"}
    ids = {}
    for spec in plans:
        if spec["name"] not in by_name:
            body = _plan_body(product["id"], spec["name"], spec["price"], currency,
                              spec.get("trial_price"), spec.get("discount_months", 0))
            by_name[spec["name"]] = pp.call("POST", "/v1/billing/plans", body)["id"]
        ids[spec["key"]] = by_name[spec["name"]]
    return ids
