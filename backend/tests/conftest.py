"""Tests run offline: simulated PayPal, no Gemini key, a throwaway database."""
import os

os.environ.update({"DATABASE_URL": "sqlite:///./test_saveflow.db", "SYNC_CATALOGUE_ON_START": "false",
                   "GEMINI_API_KEY": "", "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": "",
                   "PAYPAL_WEBHOOK_ID": "", "DEMO_MODE": "true"})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:  # startup re-seeds the database for every test
        yield c
