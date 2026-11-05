## Inspiration
Small businesses that bill monthly through PayPal Subscriptions (yoga studios, course creators, newsletter writers) lose subscribers they could have kept. Other payment platforms offer a retention step when someone clicks Cancel; PayPal Subscriptions doesn't, and popular retention tools don't support PayPal. When a PayPal subscriber cancels, they're simply gone. I wanted to build the missing **save-the-subscriber layer** for PayPal, using AI where it genuinely helps (understanding messy, free-text reasons in any language) while keeping it strictly inside the merchant's rules.

## What it does
- **Subscriber clicks Cancel and explains why in their own words**, in any language. The agent reads that reason **plus their real PayPal history** (tenure, payments, failed payments, current plan) and picks one offer: a **pause**, a **discount** or a **cheaper plan**, and writes a short, personal message.
- **The offer is executed in PayPal.** Pause = `suspend` with a scheduled `activate`; discount or cheaper plan = `revise` with the buyer's approval in a PayPal popup; otherwise a clean `cancel`.
- **The AI never decides alone.** Code computes which offers the merchant's policy allows; Gemini picks only from that list using structured output; code rejects anything else and falls back to a safe default, and rewrites any message that promises a different amount. Every decision is audit-logged with the exact PayPal calls, idempotency keys and PayPal debug IDs.
- **Plain-English policy.** Merchants write rules like *"never more than 20% off, students get the cheaper plan, no offers for app problems"*. The AI turns them into structured rules, code validates them, and the merchant approves a **summary written by code**, not by the model. Rules it can't express (e.g. "give Jane a free month") are flagged as *not enforced* instead of being guessed.
- **What-if simulator.** Before a policy goes live, it replays past cancellations in an AG Grid and shows exactly which offers would change.
- **Win-back.** If someone cancels inside PayPal instead, the verified `BILLING.SUBSCRIPTION.CANCELLED` webhook triggers one personalised come-back offer; duplicate deliveries are ignored.
- **Merchant workspace on AG Grid Community:** every attempt with custom cell renderers, saved views, quick search, saved column layouts, CSV export, inline policy editing, and a drawer that shows the agent's work for any row.

## How I built it
- **Backend:** Python 3.11, FastAPI, SQLAlchemy, SQLite (re-seeded with labelled demo data on start).
- **AI:** Google Gemini with Pydantic structured output. Free-tier quotas are small (I measured 5 requests/minute and 20/day on one model), so the agent walks a chain of Gemini Flash-Lite models, each with its own quota, and caches the scripted demo answers. If every model is unavailable it falls back to a clearly labelled rule-based default, and the guardrail still applies.
- **PayPal (sandbox):** JS SDK Subscribe button; Catalog Products and Billing Plans (found-or-created by name, so restarts never duplicate them); Subscriptions API (show, transactions, suspend, activate, revise, cancel); Webhooks with signature verification. Every call carries an idempotency key and a timeout, and errors keep PayPal's `debug_id`.
- **Frontend:** React, Vite, TypeScript, Tailwind CSS, AG Grid Community.
- **Engineering:** an explicit subscription state machine (ACTIVE / PAUSE_SCHEDULED / SUSPENDED / CANCELLED) with valid transitions only; PayPal is the source of truth, so webhooks reconcile by re-reading the subscription (handles out-of-order events); approval confirmation is a conditional update, so a popup callback and polling that race apply a change exactly once. 36 automated tests.
- **Hosting:** one Docker service on Render's free tier serving the API and the built frontend.

## Challenges I ran into
- **India-region PayPal sandbox accounts can't approve subscriptions** (PayPal shows a generic "things don't appear to be working" page), so everything runs on US sandbox accounts. The README tells judges this.
- **PayPal rejects a per-subscriber price override on the same plan** (`OVERRIDES_ON_SAME_PLAN_NOT_ALLOWED`, found in my day-1 sandbox test). I model each discount as its own plan with a discounted trial phase that returns to the regular price automatically.
- **Plan changes need the subscriber's approval in PayPal.** I open approval in a popup and only mark the offer as saved after re-reading the subscription from PayPal. Verified live: after approval the subscription's plan changes immediately, and its next billing date stays the same.
- **Keeping an LLM inside hard business limits:** moving the limits out of the prompt and into code was the key design decision.
- **Free-tier rate limits:** solved with the model chain, cooldowns and a demo cache.

## Accomplishments that I'm proud of
- **0 policy violations** in a 50-case eval (all 50 answered by Gemini), including 10 prompt-injection attacks: **10/10 flagged, 0 false flags**, **92% reason accuracy** across English, Hinglish, Spanish and sarcasm, and **50/50 offers that fit the reason**. The model never proposed an out-of-policy offer in that run; the code guardrail that blocks one is tested separately with a deliberately misbehaving model.
- **Real PayPal actions, verified end to end on the hosted demo:** a live sandbox subscription paused by the agent (PayPal shows it `SUSPENDED`), and a plan switch approved in the PayPal popup and confirmed from PayPal.
- An honest dashboard: seeded demo data is labelled and tuned to the real-world ~15% cancel-flow save rate instead of an inflated number.

## What I learned
AI agents are most useful when they choose inside rules a business already trusts. PayPal's Subscriptions API is already powerful enough to build retention on top of; the missing piece is the decision layer, plus the audit trail that lets a merchant see exactly why each offer was made.

## What's next
- Try it with real merchants' cancellation history (with consent) to measure actual save rates.
- Learn which allowed offer works best per reason (a bandit over the allowed set; the statistics decide, the LLM explains).
- Failed-payment recovery: smarter retry timing and a friendly "update your payment method" flow.
- Verify the discounted trial phase on `revise` in the sandbox (currently untested and stated as a known limit).

## Try it
- **Live demo:** https://saveflow-ufbx.onrender.com (free hosting: the first load can take up to a minute to wake up). Sandbox buyer login for the real PayPal path is in the README.
- **Code (MIT):** https://github.com/Shiva-Preetham/SaveFlow-PayPal-AI-Hackathon
- Everything runs in the PayPal sandbox; no real money moves. "Sunrise Yoga Studio" is a made-up merchant.
