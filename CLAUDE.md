# SaveFlow: project context for Claude Code

Solo entry by Shiva Preetham Chelimila (B.Tech CSE, JIIT Noida) in the **PayPal AI Hackathon** on Devpost.
**Hard deadline: Nov 12, 2026, 12:00 PM PST = Nov 13, 1:30 AM IST.** Target submission: Nov 12 evening IST.
The developer wants brutally honest feedback, not agreeable answers. Flag weak ideas and risks directly.

## What SaveFlow is

An AI agent that stops small businesses losing subscribers on PayPal.

- **Who:** small merchants who bill monthly via PayPal Subscriptions (courses, coaches, creators, newsletters, small apps).
- **Gap (verified):** Stripe has retention offers at cancellation and AI "Smart Retries". PayPal Subscriptions has neither: it retries a failed payment every 5 days, max 2 per cycle. Retention tools like Churnkey support Stripe/Braintree/Chargebee/Paddle/Maxio, not PayPal.
- **Pitch line:** closes a feature gap versus Stripe, PayPal's biggest competitor, with AI that understands free-text reasons instead of Stripe's fixed dropdown rules.

### Core flow
1. **Merchant sets allowed offers once** (policy): max discount % and duration, max pause months, cheaper plan available, one offer per customer, etc.
2. **Subscriber clicks Cancel** on a SaveFlow page and explains why in their own words.
3. **AI agent** classifies the reason (temporary / price / low usage / product problem / competitor / other), picks the best offer **only from the merchant's allowed list**, and writes a personal message. It can handle a short negotiation ("can you do 50%?") within limits.
4. **Execute in PayPal:** pause (suspend + scheduled reactivation), discount, switch plan (revise), or cancel.
5. **Win-back:** when a subscriber cancels inside the PayPal app (bypassing SaveFlow), a `BILLING.SUBSCRIPTION.CANCELLED` webhook triggers a personalized come-back offer, shown in-app (no real email).
6. **Merchant dashboard (AG Grid):** every cancel attempt with reason, offer, outcome, revenue saved; top reasons; AI insights ("many students leaving on price, consider a student plan").

### Safety rule (non-negotiable)
The LLM never decides alone. Deterministic code computes the allowed actions from merchant policy; the LLM picks from that set with structured output; code rejects anything outside the set and falls back to a safe default. Every decision is audit-logged with the PayPal calls made ("show its work").

## Stack (everything must be free)
- **Backend:** Python 3.11, FastAPI, SQLAlchemy, SQLite (re-seeded with demo data on startup, because Render's free disk resets)
- **AI:** Google Gemini API free tier, one provider only. Use structured output (Pydantic schemas). Cache demo-scenario responses to survive rate limits during judging (Dec 1–15).
- **PayPal (sandbox only):** JS SDK Subscribe button; Catalog Products + Billing Plans API; Subscriptions API (show, list transactions, suspend, activate, revise, cancel, capture outstanding balance); Webhooks with signature verification (`/v1/notifications/verify-webhook-signature`). Consider the PayPal Agent Toolkit for the agent's tool calls where it covers subscription actions.
- **Frontend:** React + Vite + TypeScript + Tailwind + **AG Grid Community** (no Enterprise-only features)
- **Hosting:** Render free tier (sleeps when idle; README must say so)
- **Local webhooks:** ngrok or Cloudflare Tunnel free tier

## Hackathon rules that affect the code
- Must meaningfully use PayPal (sandbox) **and** AI; PayPal must be central.
- Public GitHub repo, MIT license visible, full run instructions; judges may run it or use the hosted URL. Include sandbox test-buyer credentials in the README.
- Demo video < 3 minutes on YouTube. **No third-party trademarks**: use made-up brands only (e.g., "Sunrise Yoga Studio").
- Max prizes per project: one Sponsor Prize + one Grand or Honorable Mention prize. Targets: **Best Use of AG Grid** (5 winners) and **Most Impactful** / grand prizes.
- Never commit `.env` or any keys.

## Repo layout (planned)
```
backend/
  app/main.py            FastAPI app, startup seeding
  app/paypal/            client.py (token, call w/ PayPal-Request-ID idempotency), subscriptions.py, webhooks.py
  app/policy/            merchant policy model + allowed-actions engine (deterministic)
  app/agent/             reason classifier, offer selector (LLM, constrained), negotiation, message writer
  app/models/            SQLAlchemy: merchants, policies, subscribers, cancel_attempts, offers, webhook_events, audit_log
  app/jobs/              scheduler for "resume after pause"
  tests/                 unit tests + eval/ (50 labeled cancel reasons -> expected offer)
frontend/
  src/pages/             CancelFlow (subscriber), Dashboard (AG Grid), PolicySettings, AuditLog
scripts/
  day1_subscriptions_test.py   sandbox feasibility test (run first)
```

## Engineering expectations (also placement-interview material)
- Webhooks: verify signatures, store event IDs and ignore duplicates (idempotency), tolerate out-of-order events.
- Explicit subscription state machine: ACTIVE / PAUSE_SCHEDULED / SUSPENDED / CANCELLED, with valid transitions only.
- Keep the local DB consistent with PayPal: PayPal is the source of truth; reconcile by fetching subscription details.
- Every PayPal call: idempotency key, timeout, error with `debug_id` logged.
- Eval: 50-case labeled set; report accuracy and "policy violations: 0" in README and video.

## Schedule
| Dates | Work |
|---|---|
| Oct 25–26 | Run `scripts/day1_subscriptions_test.py`; repo + project skeleton |
| Oct 27–30 | Backend: policy engine, agent, PayPal actions, DB |
| Oct 31–Nov 3 | Frontend: cancel flow, AG Grid dashboard, settings |
| Nov 4 | Webhooks + win-back |
| Nov 5 | 50-case eval |
| Nov 6–7 | Deploy to Render, README. **Feature freeze Nov 7.** |
| Nov 8–10 | Demo video |
| Nov 11–12 | Devpost submission (click Submit, not just save draft) |

**Cut order if behind:** failed-payment recovery → negotiation → AI insights panel → fancy UI. Never cut: core cancel flow, PayPal actions, policy guardrail, eval, video.

## Day 1 sandbox results (Oct 26)
7/8 steps passed: create plans, subscribe, suspend, activate, revise to another plan, list transactions, cancel.
- **Sandbox accounts must be US.** With the default IN (India) Business + Personal accounts, buyer approval failed on PayPal's generic "We're sorry, things don't appear to be working" page. US Business + US Personal accounts and a REST app linked to the US Business account work. README must tell judges this.
- **Per-subscriber price override on the same plan: NO.** `revise` with `plan_id` = current plan + `plan` override returns 422 `OVERRIDES_ON_SAME_PLAN_NOT_ALLOWED`. Discounts must be pre-created discounted plans (e.g. "Pro 30% off", $7) that the subscriber is switched to. Untested: override while revising to a *different* plan.
- **`revise` to another plan requires buyer approval every time** (returns an approve link). After approval, `plan_id` showed the new plan immediately; when the new price is first billed is not yet confirmed.
- **Suspend/activate need no buyer approval**, so pause is the lowest-friction offer. Discount and plan-switch offers send the subscriber to PayPal to approve, so some will drop off there.

## Open questions
- When is the new price first billed after a plan switch: immediately, or from the next cycle?
- Can a failed renewal payment be simulated in sandbox? (Ask in the PayPal Discord if needed: https://discord.gg/sJ2G6DyvSK)

## Known limits to state honestly in the pitch
- Subscribers can cancel inside the PayPal app, bypassing the save page; SaveFlow can then only win them back.
- Cancel flows save roughly 15% of attempts (Loop data: 441K attempts, 87 brands), so the value is real but not magic.
- Saving payment methods or advanced billing features may need extra PayPal approval in production; everything here is sandbox.

## Origin note
Reuse the *patterns* (not code) from the developer's earlier repo `Shiva-Preetham/Enterprise-AI-Decision-Intelligence-Platform`: `decision_engine/policy_engine.py` + `reasoning_engine.py` (LLM restricted to policy-allowed actions), `workflow_engine.py` (state machine), `audit_service.py`. Avoid its mistakes: README overclaiming, silent exception swallowing, tracebacks returned to users, mixed LLM providers, heavy infra (Redis/Celery/RabbitMQ).
