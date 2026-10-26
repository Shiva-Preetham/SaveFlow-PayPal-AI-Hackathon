"""PayPal REST client: cached OAuth token, idempotency key and timeout on every call,
errors carry PayPal's debug_id."""
import logging
import time
import uuid

import httpx

from app.config import Settings

log = logging.getLogger(__name__)


class PayPalError(Exception):
    def __init__(self, status: int, name: str | None, message: str | None,
                 details: list | None = None, debug_id: str | None = None):
        self.status, self.name, self.message = status, name, message
        self.details, self.debug_id = details or [], debug_id
        issues = ", ".join(d.get("issue", "?") for d in self.details)
        super().__init__(f"PayPal {status} {name}: {message} [{issues}] debug_id={debug_id}")


class PayPalClient:
    TOKEN_MARGIN_S = 60  # refresh a minute before expiry

    def __init__(self, settings: Settings, http: httpx.Client | None = None):
        self._settings = settings
        self._http = http or httpx.Client(base_url=settings.paypal_base_url, timeout=30.0)
        self._token: str | None = None
        self._token_expires_at = 0.0

    def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        r = self._http.post("/v1/oauth2/token", data={"grant_type": "client_credentials"},
                            auth=(self._settings.paypal_client_id, self._settings.paypal_client_secret))
        if r.status_code != 200:
            raise self._error(r)
        body = r.json()
        self._token = body["access_token"]
        self._token_expires_at = time.monotonic() + body.get("expires_in", 0) - self.TOKEN_MARGIN_S
        return self._token

    def call(self, method: str, path: str, body: dict | None = None,
             idempotency_key: str | None = None, params: dict | None = None) -> dict:
        """Pass a stable idempotency_key when retrying the same logical action."""
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "PayPal-Request-ID": idempotency_key or str(uuid.uuid4()),
            "Prefer": "return=representation",
        }
        r = self._http.request(method, path, json=body, headers=headers, params=params)
        if r.status_code >= 400:
            err = self._error(r)
            log.error("PayPal call failed: %s %s -> %s", method, path, err)
            raise err
        return r.json() if r.content else {}

    @staticmethod
    def _error(r: httpx.Response) -> PayPalError:
        try:
            err = r.json()
        except ValueError:
            err = {"message": r.text[:200]}
        return PayPalError(r.status_code, err.get("name") or err.get("error"),
                           err.get("message") or err.get("error_description"),
                           err.get("details"), err.get("debug_id"))
