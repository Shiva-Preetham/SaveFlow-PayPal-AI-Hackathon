# SaveFlow

An AI agent that helps small businesses keep subscribers on PayPal Subscriptions. When a subscriber tries to cancel, SaveFlow reads their reason and their PayPal history, and makes the best offer the merchant allows (pause, discount plan, cheaper plan) — executed in PayPal.

> **Status:** early development for the PayPal AI Hackathon. Everything runs against the PayPal **sandbox**; no real money moves.

## Requirements
- Python 3.11
- Node.js 20+
- A PayPal developer account with **US** sandbox accounts (see below)

## PayPal sandbox setup
Sandbox accounts must be **United States**. With India (IN) sandbox accounts, PayPal's subscription approval page fails with "Things don't appear to be working".

1. developer.paypal.com → Testing Tools → Sandbox Accounts → create a **US Business** and a **US Personal** account.
2. Apps & Credentials (Sandbox) → Create App → link it to the US Business account.
3. Copy `.env.example` to `.env` and paste the app's Client ID and Secret.

## Run locally
Backend (from the repo root):
```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python -m uvicorn --app-dir backend app.main:app --port 8000
```
On macOS/Linux use `backend/.venv/bin/python` instead.

Frontend (second terminal):
```bash
npm --prefix frontend install
npm --prefix frontend run dev
```
Open http://localhost:5173. The header shows whether the PayPal and Gemini keys are configured.

Tests:
```bash
cd backend && .venv/Scripts/python -m pytest
```

## Day 1 sandbox feasibility test
`scripts/day1_subscriptions_test.py` creates plans and walks one subscription through subscribe → pause → resume → plan switch → transactions → cancel. Results are recorded in `CLAUDE.md`.

## License
MIT
