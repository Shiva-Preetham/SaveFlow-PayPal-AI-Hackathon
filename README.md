# SaveFlow

**The save-the-subscriber layer PayPal Subscriptions is missing.**

When a subscriber tries to cancel, SaveFlow reads their reason (in their own words, any language) and their PayPal history, and makes the best offer the merchant allows: a pause, a discount, or a cheaper plan. It then executes it in PayPal. Merchants write their retention rules in plain English and can test a new policy on past cancellations before turning it on.

> Everything runs against the **PayPal sandbox**. No real money moves. “Sunrise Yoga Studio” is a made-up merchant.

**Live demo:** _add your Render URL here_ (free tier: the first load can take 30–60 s while the server wakes up).

## Why
Stripe offers retention flows at cancellation; PayPal Subscriptions does not, and popular retention tools don't support PayPal. Small merchants billing through PayPal lose subscribers they could have kept. Industry data puts cancel-flow saves at roughly **15% of attempts**, so the value is real but not magic.

## What it does
| | |
|---|---|
| **Agent with PayPal context** | Reads the subscription and its transactions from the PayPal API (tenure, payments, failed payments, plan), combines them with the free-text reason, and picks one offer. Same reason, different subscriber, different offer. |
| **Guardrail by code, not by prompt** | Deterministic code computes the offers the policy allows. The LLM chooses only from that set via structured output. Code rejects anything else and falls back to a safe default, and a message check rewrites any reply that promises a different amount. |
| **Plain-English policy compiler** | “Never more than 20% off, students get Lite, no offers for app problems.” The AI produces structured rules, code validates them, and the merchant approves a summary **written by code** before anything changes. Rules it can't express are listed as “not enforced” instead of being approximated. |
| **What-if simulator** | Replays past cancel attempts against a proposed policy in an AG Grid, showing which offers would change and the value offered. It shows offers that *would have been made*, not acceptance. |
| **Real PayPal actions** | Pause = `suspend` + scheduled `activate`; discount or cheaper plan = `revise` with buyer approval in a popup; cancel = `cancel`. Every call has an idempotency key and logs PayPal's `debug_id`. |
| **Win-back** | A subscriber who cancels inside PayPal triggers `BILLING.SUBSCRIPTION.CANCELLED`; SaveFlow verifies the signature, ignores duplicate deliveries by event id, re-reads the subscription from PayPal, and prepares one come-back offer. |
| **AG Grid merchant workspace** | Every attempt with custom cell renderers, saved views, quick search, saved column layout, CSV export; click a row to see the agent's work: what it read, what was allowed, what it chose, the guardrail result, and every PayPal call. Policy rules are edited inline in a grid. AG Grid **Community** only. |

## Try it (hosted demo)
1. **Try it as a subscriber** → pick *Maya* → send the suggested reason → accept the pause. The right panel shows the agent's work.
2. Pick *Tom* and try the prompt injection; pick *Arjun* (Hinglish), then ask “Can you do 50%?” The counter-offer is capped at the policy limit.
3. To use **real PayPal calls**: in the same page click the PayPal **Subscribe** button and log in with the sandbox buyer below. Then cancel that subscriber through SaveFlow; the pause is a real `suspend` in the sandbox.
4. **Policy** → *Try an example* → *Compile with AI* → note the unsupported-rule warning → *Test on past cancellations first*.
5. **Win-backs** → send a CANCELLED webhook, then re-send the same event to see duplicate handling.

**Sandbox buyer for judges:** _add the US sandbox Personal account email and password here_ (sandbox only; it cannot spend real money).

## Run locally
Requirements: Python 3.11, Node 20+, a PayPal developer account and a free Gemini API key (https://aistudio.google.com/apikey).

**PayPal sandbox accounts must be United States.** With India (IN) sandbox accounts, PayPal's subscription approval fails with “Things don't appear to be working”.
1. developer.paypal.com → Testing Tools → Sandbox Accounts → create a **US Business** and a **US Personal** account.
2. Apps & Credentials (Sandbox) → Create App → link it to the US Business account.
3. `cp .env.example .env` and fill in `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `GEMINI_API_KEY`.

```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python -m uvicorn --app-dir backend app.main:app --port 8000
```
(macOS/Linux: `backend/.venv/bin/python`.) In a second terminal:
```bash
npm --prefix frontend install
npm --prefix frontend run dev
```
Open http://localhost:5173. On start the backend re-seeds demo data and finds-or-creates the merchant's plans in your sandbox (no duplicates on restart). Without keys it still runs: PayPal calls are simulated and labelled, and the agent uses a labelled keyword fallback.

**Webhooks (optional):** expose port 8000 with ngrok or Cloudflare Tunnel, add a webhook in your PayPal app pointing to `/api/webhooks/paypal` for `BILLING.SUBSCRIPTION.*` and `PAYMENT.SALE.COMPLETED`, and put its id in `PAYPAL_WEBHOOK_ID`. Unverified webhooks are always rejected.

## Tests and eval
```bash
cd backend
.venv/Scripts/python -m pytest                      # 35 unit + API tests, offline
.venv/Scripts/python -m tests.eval.run_eval         # 50-case agent eval (needs GEMINI_API_KEY)
```
The eval has 40 normal reasons (English, Hinglish, Spanish, sarcasm) and 10 adversarial ones (prompt injection, fake system messages, threats). It reports reason accuracy, offer fit, how often the LLM proposed something outside the policy (blocked by code), and **final policy violations**, which must be 0.

**Latest run (Nov 5, all 50 answered by Gemini):** 0 final policy violations · 92% reason accuracy (37/40; the misses are genuinely ambiguous: “Personal reasons”, “Just don't want it anymore”, sarcasm) · 50/50 offers fit the reason · 10/10 injections flagged, 0 false flags. The model never proposed an out-of-policy offer in this run, so the guardrail did not have to block anything here; the blocking path is covered by unit tests with a model that misbehaves on purpose. Results: [`backend/tests/eval/RESULTS.md`](backend/tests/eval/RESULTS.md); keyword-only baseline: [`BASELINE_keyword_fallback.md`](backend/tests/eval/BASELINE_keyword_fallback.md).

## How it's built
```
React + Vite + Tailwind + AG Grid Community
        │  /api
FastAPI ── policy/engine.py     deterministic allowed actions + enforce()   ← the guardrail
        ├─ agent/decider.py     Gemini structured output, picks one allowed action, writes message
        ├─ agent/compiler.py    plain English → PolicyRules (validated) + code-written summary
        ├─ services/retention   read PayPal history → decide → execute → audit
        ├─ services/webhooks    verify → dedupe by event id → reconcile from PayPal → win-back
        ├─ services/simulator   replay past attempts under a proposed policy (no LLM calls)
        └─ paypal/              OAuth token cache, idempotency keys, timeouts, debug_id errors
SQLite (re-seeded on start)        PayPal Sandbox: Catalog, Plans, Subscriptions, Webhooks, JS SDK
```
- **Discounts are separate PayPal plans** with a discounted trial phase (e.g. 30% off for 2 cycles, then the regular price), because PayPal rejects a price override on the subscriber's current plan (`OVERRIDES_ON_SAME_PLAN_NOT_ALLOWED`, found in our Day 1 sandbox test).
- **Subscription state machine** (ACTIVE / PAUSE_SCHEDULED / SUSPENDED / CANCELLED) with valid transitions only; PayPal is the source of truth and webhooks reconcile by re-reading the subscription.
- **Gemini answers are cached** (DB + a committed demo cache for the scripted scenarios) so the demo survives free-tier rate limits. Free-tier quotas are per model and small (measured on our key: `gemini-2.5-flash` = 5 requests/min and 20/day), so the agent walks a chain of Gemini Flash-Lite models (`GEMINI_MODEL`, then `GEMINI_FALLBACK_MODELS`), skipping any that is rate-limited or overloaded until its quota resets. Thinking is off for speed (2–5 s per decision). If every model is unavailable, the agent falls back to a labelled rule-based default and the guardrail still applies; the audit log records which model answered.
- **PayPal Agent Toolkit:** its published subscription tools cover show and cancel but not suspend/activate, which pausing needs, so SaveFlow calls the Subscriptions REST API directly through one small client for every action.

## Honest limits
- Subscribers can cancel inside PayPal and skip the save page; SaveFlow can then only try to win them back.
- Discounts and plan switches need the buyer to approve in PayPal, so some subscribers will drop off there. Pausing needs no approval.
- Whether PayPal applies a discount plan's trial phase when an existing subscription is *revised* onto it has not been verified in the sandbox yet; the regular price always applies afterwards.
- The demo dashboard is seeded demo data (labelled), tuned to roughly the industry save rate; it is not customer data.
- The scheduled resume runs inside the web process; on Render's free tier it catches up after the server wakes.
- Sandbox only. Production use would need a PayPal live app and review.

## License
[MIT](LICENSE)
