"""End-to-end API flows in simulated-PayPal mode (no keys)."""
import pytest

from app.models import Subscriber, SubscriptionState as S
from app.services.state import InvalidTransition, reconcile, transition


def persona(client, name: str) -> dict:
    return next(s for s in client.get("/api/subscribers").json() if s["name"].startswith(name))


def test_pause_flow_records_calls_and_state(client):
    maya = persona(client, "Maya")
    a = client.post("/api/cancel", json={"subscriber_id": maya["id"],
                                         "reason": "I'm travelling for 3 months and money's tight"}).json()
    assert a["offer_type"] == "pause" and a["outcome"] == "offered"
    assert any(c["method"] == "GET" for c in a["paypal_calls"])  # agent read history first
    done = client.post(f"/api/attempts/{a['id']}/accept").json()
    assert done["outcome"] == "saved" and done["revenue_kept_12m"] > 0
    assert done["paypal_calls"][-1]["path"].endswith("/suspend")
    assert persona(client, "Maya")["state"] == "SUSPENDED"
    assert client.post(f"/api/attempts/{a['id']}/accept").status_code == 409  # no double execution
    assert client.post(f"/api/demo/resume/{maya['id']}").json()["state"] == "ACTIVE"


def test_second_cancel_gets_no_new_offer(client):
    ben = persona(client, "Ben")
    first = client.post("/api/cancel", json={"subscriber_id": ben["id"], "reason": "too expensive"}).json()
    assert first["offer_type"] != "cancel"
    second = client.post("/api/cancel", json={"subscriber_id": ben["id"], "reason": "too expensive"}).json()
    assert second["offer_id"] == "cancel"  # one offer per customer


def test_counter_offer_stays_within_policy_once(client):
    ben = persona(client, "Ben")
    a = client.post("/api/cancel", json={"subscriber_id": ben["id"], "reason": "Found a cheaper app"}).json()
    c = client.post(f"/api/attempts/{a['id']}/counter", json={"text": "Can you do 50%?"}).json()
    assert c["offer_id"] == "discount_30" and "at most 30%" in c["guardrail_note"]
    assert client.post(f"/api/attempts/{a['id']}/counter", json={"text": "60%?"}).status_code == 409


def test_decline_cancels(client):
    tom = persona(client, "Tom")
    a = client.post("/api/cancel", json={"subscriber_id": tom["id"], "reason": "no thanks"}).json()
    assert client.post(f"/api/attempts/{a['id']}/decline").json()["outcome"] == "cancelled"
    assert persona(client, "Tom")["state"] == "CANCELLED"
    assert client.post("/api/cancel", json={"subscriber_id": tom["id"], "reason": "x"}).status_code == 409


def test_cancel_in_paypal_creates_win_back_and_duplicates_are_ignored(client):
    priya = persona(client, "Priya")
    r = client.post(f"/api/demo/cancel-in-paypal/{priya['id']}", json={}).json()
    assert "win-back offer" in r["result"]
    again = client.post(f"/api/demo/cancel-in-paypal/{priya['id']}", json={"event_id": r["event_id"]}).json()
    assert again["duplicate"] is True
    assert len(client.get("/api/attempts", params={"channel": "win_back"}).json()) == 1


def test_real_webhook_rejected_without_verification_config(client):
    r = client.post("/api/webhooks/paypal", json={"id": "WH-1", "event_type": "BILLING.SUBSCRIPTION.CANCELLED"})
    assert r.status_code == 503


def test_policy_apply_validates_and_versions(client):
    p = client.get("/api/policy").json()
    assert client.post("/api/policy/apply", json={"rules": {**p["rules"], "max_pause_months": 12}}).status_code == 422
    new = client.post("/api/policy/apply", json={"rules": {**p["rules"], "max_discount_pct": 20}}).json()
    assert new["version"] == p["version"] + 1


def test_simulator_shows_changes(client):
    p = client.get("/api/policy").json()
    sim = client.post("/api/simulate", json={"rules": {**p["rules"], "discount_enabled": False}}).json()
    assert sim["totals"]["attempts"] > 50 and sim["totals"]["changed"] > 0
    assert all("discount" not in r["simulated_offer"].lower() or "off" not in r["simulated_offer"]
               for r in sim["rows"])


def test_dashboard_and_errors_have_no_tracebacks(client):
    d = client.get("/api/dashboard").json()
    assert d["attempts"] == 72 and 0.05 < d["save_rate"] < 0.35
    r = client.get("/api/attempts/99999")
    assert r.status_code == 404 and "Traceback" not in r.text


def test_state_machine():
    sub = Subscriber(name="x", state=S.CANCELLED)
    with pytest.raises(InvalidTransition):
        transition(sub, S.ACTIVE)
    sub = Subscriber(name="y", state=S.ACTIVE)
    transition(sub, S.SUSPENDED)
    assert sub.state == S.SUSPENDED
    assert reconcile(sub, "CANCELLED") and sub.state == S.CANCELLED  # PayPal wins, even out of order
    assert not reconcile(sub, "UNKNOWN_STATUS")
