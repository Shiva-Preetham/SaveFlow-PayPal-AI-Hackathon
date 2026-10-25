"""
SaveFlow - Day 1 PayPal sandbox feasibility test (Subscriptions).

Proves every PayPal action SaveFlow's AI will take:

  STEP 1  Create a product + two monthly plans: Pro $10, Lite $5   (merchant setup)
  STEP 2  Subscribe the sandbox buyer to Pro                        (buyer approves once)
  STEP 3  PAUSE  the subscription  (suspend)                       -> "pause for 2 months" offer
  STEP 4  RESUME the subscription  (activate)                      -> scheduled restart
  STEP 5  DISCOUNT: lower this one subscriber's price to $7         -> "30% off" offer   (buyer approves)
  STEP 6  SWITCH to the Lite plan                                   -> "cheaper plan" offer (buyer approves)
  STEP 7  Read payment history (transactions)                       -> dashboard data
  STEP 8  CANCEL                                                    -> customer still leaves

Run:
    pip install requests python-dotenv
    copy .env.example to .env and paste your SANDBOX keys
    python day1_subscriptions_test.py

When a link is printed: open it, log in with your SANDBOX PERSONAL (buyer) account,
approve, come back and press Enter. The browser then lands on example.com - expected, close it.
At the end, paste the SUMMARY (or day1_results.json) back to Claude.
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api-m.sandbox.paypal.com"
CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()
CURRENCY = os.getenv("CURRENCY", "USD")
RETURN_URL = "https://example.com/approved"
CANCEL_URL = "https://example.com/cancelled"
STATE_FILE = "day1_state.json"  # remembers product/plan ids so re-runs don't create duplicates

RESULTS: dict = {}
TOKEN = ""


# ----------------------------------------------------------------- helpers
class PayPalError(Exception):
    pass


def get_token() -> str:
    if not CLIENT_ID or not CLIENT_SECRET:
        sys.exit("Missing PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET in .env")
    r = requests.post(f"{BASE}/v1/oauth2/token", auth=(CLIENT_ID, CLIENT_SECRET),
                      data={"grant_type": "client_credentials"}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Could not get access token ({r.status_code}): {r.text}\n"
                 "Check you copied the SANDBOX (not live) Client ID and Secret.")
    return r.json()["access_token"]


def call(method: str, path: str, body: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "PayPal-Request-ID": str(uuid.uuid4()),  # idempotency key
        "Prefer": "return=representation",
    }
    r = requests.request(method, f"{BASE}{path}", headers=headers,
                         data=json.dumps(body) if body is not None else None, timeout=60)
    if r.status_code >= 400:
        try:
            err = r.json()
        except ValueError:
            err = {"raw": r.text}
        raise PayPalError(
            f"{method} {path} -> HTTP {r.status_code}\n"
            f"    name: {err.get('name')}\n    message: {err.get('message')}\n"
            f"    details: {json.dumps(err.get('details'))}\n    debug_id: {err.get('debug_id')}")
    return r.json() if r.text.strip() else {}


def link(resp: dict, rel: str = "approve") -> str | None:
    for l in resp.get("links", []):
        if l.get("rel") == rel:
            return l["href"]
    return None


def wait_for_buyer(url: str, what: str):
    print(f"\n  >> Open this link, log in as your SANDBOX BUYER and approve ({what}):\n  {url}\n")
    input("  Press Enter after approving in the browser... ")


def sub(sub_id: str) -> dict:
    return call("GET", f"/v1/billing/subscriptions/{sub_id}")


def wait_status(sub_id: str, wanted: set, tries: int = 10) -> dict:
    s = sub(sub_id)
    for _ in range(tries):
        if s["status"] in wanted:
            break
        time.sleep(3)
        s = sub(sub_id)
    return s


def price_of(s: dict) -> str:
    try:
        return s["billing_info"]["last_payment"]["amount"]["value"]
    except KeyError:
        return "?"


def record(name: str, ok: bool, **details):
    RESULTS[name] = {"result": "PASS" if ok else "FAIL", **details}
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")


def app_context(user_action: str = "SUBSCRIBE_NOW") -> dict:
    return {"brand_name": "SaveFlow Demo Yoga", "user_action": user_action,
            "shipping_preference": "NO_SHIPPING", "return_url": RETURN_URL, "cancel_url": CANCEL_URL}


def monthly_plan(product_id: str, name: str, price: str) -> dict:
    return call("POST", "/v1/billing/plans", {
        "product_id": product_id, "name": name, "status": "ACTIVE",
        "billing_cycles": [{
            "frequency": {"interval_unit": "MONTH", "interval_count": 1},
            "tenure_type": "REGULAR", "sequence": 1, "total_cycles": 0,
            "pricing_scheme": {"fixed_price": {"value": price, "currency_code": CURRENCY}},
        }],
        "payment_preferences": {"auto_bill_outstanding": True, "payment_failure_threshold": 2},
    })


# ------------------------------------------------------------------- steps
def step1_setup() -> tuple[str, str]:
    print("\n=== STEP 1: product + Pro ($10) and Lite ($5) plans ===")
    if os.path.exists(STATE_FILE):
        st = json.load(open(STATE_FILE))
        print(f"  Reusing plans from {STATE_FILE}: Pro {st['pro']}  Lite {st['lite']}")
        record("step1_setup", True, **st, reused=True)
        return st["pro"], st["lite"]
    product = call("POST", "/v1/catalogs/products",
                   {"name": "SaveFlow Demo - Online Yoga Course", "type": "SERVICE"})
    pro = monthly_plan(product["id"], "Yoga Pro (monthly)", "10.00")
    lite = monthly_plan(product["id"], "Yoga Lite (monthly)", "5.00")
    st = {"product": product["id"], "pro": pro["id"], "lite": lite["id"]}
    json.dump(st, open(STATE_FILE, "w"), indent=2)
    print(f"  Product {product['id']}\n  Pro plan {pro['id']}\n  Lite plan {lite['id']}")
    record("step1_setup", True, **st)
    return pro["id"], lite["id"]


def step2_subscribe(pro_id: str) -> str:
    print("\n=== STEP 2: subscribe the sandbox buyer to Pro ===")
    s = call("POST", "/v1/billing/subscriptions", {"plan_id": pro_id, "application_context": app_context()})
    print(f"  Subscription {s['id']} created (status {s['status']})")
    wait_for_buyer(link(s), "subscribe to Yoga Pro, $10/month")
    s = wait_status(s["id"], {"ACTIVE"})
    print(f"  Status now: {s['status']}")
    record("step2_subscribe", s["status"] == "ACTIVE", subscription_id=s["id"], status=s["status"])
    if s["status"] != "ACTIVE":
        sys.exit("  Subscription not active - can't continue. Paste this output to Claude.")
    return s["id"]


def step3_pause(sid: str):
    print("\n=== STEP 3: PAUSE (suspend) ===")
    call("POST", f"/v1/billing/subscriptions/{sid}/suspend", {"reason": "Customer travelling for 2 months"})
    s = wait_status(sid, {"SUSPENDED"})
    print(f"  Status: {s['status']}")
    record("step3_pause", s["status"] == "SUSPENDED", status=s["status"])


def step4_resume(sid: str):
    print("\n=== STEP 4: RESUME (activate) ===")
    call("POST", f"/v1/billing/subscriptions/{sid}/activate", {"reason": "Pause period ended"})
    s = wait_status(sid, {"ACTIVE"})
    print(f"  Status: {s['status']}")
    record("step4_resume", s["status"] == "ACTIVE", status=s["status"])


def step5_discount(sid: str, pro_id: str):
    print("\n=== STEP 5: DISCOUNT this subscriber to $7 (plan override) ===")
    try:
        r = call("POST", f"/v1/billing/subscriptions/{sid}/revise", {
            "plan_id": pro_id,
            "plan": {"billing_cycles": [{
                "sequence": 1,
                "pricing_scheme": {"fixed_price": {"value": "7.00", "currency_code": CURRENCY}},
            }]},
            "application_context": app_context("CONTINUE"),
        })
        url = link(r)
        if url:
            wait_for_buyer(url, "accept discounted price $7/month")
        s = sub(sid)
        override = json.dumps(s.get("plan_overridden", s.get("plan", {})))
        print(f"  plan_overridden: {s.get('plan_overridden')}  status: {s['status']}")
        record("step5_discount_override", True, needed_buyer_approval=bool(url),
               plan_overridden=s.get("plan_overridden"), subscription_plan_details=override[:300],
               note="Check in sandbox buyer account (Settings > Payments > Automatic payments) that the next price shows $7.")
    except PayPalError as e:
        print(f"  ERROR: {e}")
        record("step5_discount_override", False, error=str(e),
               hint="Per-subscriber price override not allowed. Fallback: create a 'Pro - 30% off' plan "
                    "($7) and switch the subscriber to it, like step 6. That still works for the demo.")


def step6_switch(sid: str, lite_id: str):
    print("\n=== STEP 6: SWITCH to Lite plan ($5) ===")
    try:
        r = call("POST", f"/v1/billing/subscriptions/{sid}/revise",
                 {"plan_id": lite_id, "application_context": app_context("CONTINUE")})
        url = link(r)
        if url:
            wait_for_buyer(url, "switch to Yoga Lite, $5/month")
        s = sub(sid)
        print(f"  plan_id now: {s.get('plan_id')}  (Lite is {lite_id})  status: {s['status']}")
        record("step6_switch_plan", s.get("plan_id") == lite_id, needed_buyer_approval=bool(url),
               plan_id=s.get("plan_id"),
               note="If plan_id is still Pro, the switch may apply from the next billing cycle - tell Claude.")
    except PayPalError as e:
        print(f"  ERROR: {e}")
        record("step6_switch_plan", False, error=str(e))


def step7_transactions(sid: str):
    print("\n=== STEP 7: payment history ===")
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end = (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    try:
        r = call("GET", f"/v1/billing/subscriptions/{sid}/transactions?start_time={start}&end_time={end}")
        txs = r.get("transactions", [])
        for t in txs:
            amt = t.get("amount_with_breakdown", {}).get("gross_amount", {})
            print(f"  {t.get('time')}  {t.get('status')}  {amt.get('value')} {amt.get('currency_code')}")
        record("step7_transactions", True, count=len(txs),
               note="0 is OK - sandbox can take a few minutes to show the first payment.")
    except PayPalError as e:
        print(f"  ERROR: {e}")
        record("step7_transactions", False, error=str(e))


def step8_cancel(sid: str):
    print("\n=== STEP 8: CANCEL ===")
    call("POST", f"/v1/billing/subscriptions/{sid}/cancel", {"reason": "Customer chose to leave"})
    s = wait_status(sid, {"CANCELLED"})
    print(f"  Status: {s['status']}")
    record("step8_cancel", s["status"] == "CANCELLED", status=s["status"])


# -------------------------------------------------------------------- main
def main():
    global TOKEN
    TOKEN = get_token()
    print("Connected to PayPal SANDBOX.")
    try:
        pro_id, lite_id = step1_setup()
        sid = step2_subscribe(pro_id)
        step3_pause(sid)
        step4_resume(sid)
        step5_discount(sid, pro_id)
        step6_switch(sid, lite_id)
        step7_transactions(sid)
        step8_cancel(sid)
    except PayPalError as e:
        print(f"\n  STOPPED with error:\n  {e}")
        RESULTS["stopped"] = {"result": "FAIL", "error": str(e)}

    print("\n" + "=" * 60 + "\nSUMMARY")
    for name, res in RESULTS.items():
        print(f"  {res['result']:4}  {name}")
        if "hint" in res:
            print(f"        hint: {res['hint']}")
    with open("day1_results.json", "w") as f:
        json.dump({"run_at": datetime.now().isoformat(), "results": RESULTS}, f, indent=2)
    print("\nSaved details to day1_results.json - paste it back to Claude.")


if __name__ == "__main__":
    main()
