import httpx
import pytest

from app.config import Settings
from app.paypal.client import PayPalClient, PayPalError

SETTINGS = Settings(paypal_client_id="id", paypal_client_secret="secret", _env_file=None)


def make_client(handler) -> tuple[PayPalClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return handler(request)

    http = httpx.Client(base_url="https://paypal.test", transport=httpx.MockTransport(record))
    return PayPalClient(SETTINGS, http), seen


def test_every_call_has_idempotency_key_and_token_is_cached():
    client, seen = make_client(lambda r: httpx.Response(200, json={"id": "I-1"}))
    client.call("GET", "/v1/billing/subscriptions/I-1")
    client.call("GET", "/v1/billing/subscriptions/I-1")

    api_calls = [r for r in seen if r.url.path != "/v1/oauth2/token"]
    assert len(seen) - len(api_calls) == 1  # one token fetch for two calls
    keys = [r.headers["PayPal-Request-ID"] for r in api_calls]
    assert all(keys) and keys[0] != keys[1]
    assert api_calls[0].headers["Authorization"] == "Bearer tok"


def test_stable_idempotency_key_is_passed_through():
    client, seen = make_client(lambda r: httpx.Response(204))
    assert client.call("POST", "/v1/billing/subscriptions/I-1/suspend", {"reason": "x"},
                       idempotency_key="pause-42") == {}
    assert seen[-1].headers["PayPal-Request-ID"] == "pause-42"


def test_error_carries_debug_id_and_issue():
    body = {"name": "UNPROCESSABLE_ENTITY", "message": "failed business validation", "debug_id": "f476038edfeee",
            "details": [{"issue": "OVERRIDES_ON_SAME_PLAN_NOT_ALLOWED"}]}
    client, _ = make_client(lambda r: httpx.Response(422, json=body))
    with pytest.raises(PayPalError) as exc:
        client.call("POST", "/v1/billing/subscriptions/I-1/revise", {})
    assert exc.value.status == 422
    assert exc.value.debug_id == "f476038edfeee"
    assert "OVERRIDES_ON_SAME_PLAN_NOT_ALLOWED" in str(exc.value)
