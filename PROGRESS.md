# SaveFlow progress (read this first)

_Last updated: Nov 5, 2026. Deadline: **Nov 12, 12:00 PM PST = Nov 13, 1:30 AM IST**. Target: submit Nov 12 evening IST._

## Where we are
The full app is built and pushed to GitHub. It runs locally end to end. Three things block a strong submission, and only you can do them:

| # | What | Why it matters | Time |
|---|---|---|---|
| 1 | Put a real **Gemini API key** in `.env` (https://aistudio.google.com/apikey, free) | `.env` still has the placeholder, so the AI parts run on the labelled keyword fallback. The eval, the policy compiler and the video need the real model. | 5 min |
| 2 | **Deploy to Render** and add the URL to the README | Judges use the hosted URL. | 20 min |
| 3 | **Record the < 3 min video**, upload to YouTube, submit on Devpost | Required. Script and submission text are in `DEVPOST.md`. | 1 evening |

After step 1, tell Claude: “key is in, run the eval and warm the cache”. That runs the 50-case eval with Gemini, writes `backend/tests/eval/RESULTS.md`, records the demo cache, and commits both.

## What is built (and how it was verified)
Legend: ✅ verified by tests or by running it · 🟡 built, needs your sandbox login or key to verify · ⬜ not built

| Feature | Status | How it was verified / how you can verify |
|---|---|---|
| Policy engine: allowed offers per subscriber (tenure, one offer per customer, category rules, discount cap) | ✅ | `tests/test_policy_engine.py` (9 tests) |
| Guardrail: LLM pick outside the allowed set → blocked → safe default; message promising another amount → rewritten | ✅ | `tests/test_agent.py` with a fake LLM; seeded “Blocked” rows in the workspace |
| Prompt-injection flag (model flag + code regex) | ✅ | tests; Tom persona in *Try it* |
| Gemini decision agent (structured output, reads PayPal history, writes message in subscriber's language) | 🟡 | Code done; needs key. Without a key it falls back and says so. |
| Plain-English policy compiler + code-written summary + diff + “not enforced” warnings | 🟡 | Validation tested with a fake LLM; real compile needs key |
| Inline policy editing in AG Grid → server validation → diff → apply as new version | ✅ | Clicked through in the browser (max discount 30 → 20 showed “Apply 1 change”) |
| What-if simulator (AG Grid, changed rows highlighted, totals row) | ✅ | Browser: 32 of 73 offers change under “max 20%, no offer for product problems” |
| Cancel flow (subscriber view + “behind the scenes” merchant panel) | ✅ | Browser: Maya → pause offer → accepted → saved, $90 / 12 mo |
| Counter-offer (one, capped at the policy limit) | ✅ | API test: “Can you do 50%?” → 30% with note; 2nd counter → 409 |
| PayPal client: OAuth cache, idempotency key on every call, timeout, debug_id in errors | ✅ | `tests/test_paypal_client.py` |
| PayPal catalogue: product + Pro, 20%/30%/50% discount plans (trial cycles), Lite; find-or-create (no duplicates) | ✅ | Ran twice against your sandbox: same 5 plan ids both times |
| PayPal Subscribe button (JS SDK) on *Try it* | ✅ renders | Seen in the browser with your sandbox plan |
| Live path: subscribe with sandbox buyer → cancel via SaveFlow → real `suspend` / `revise` popup / `cancel` | 🟡 | Needs you to log in as the US sandbox buyer once (see “Verify the live PayPal path”) |
| Webhooks: signature verification, dedupe by event id, reconcile from PayPal, win-back | ✅ / 🟡 | Simulated events tested (duplicate ignored). Real webhooks need a tunnel + `PAYPAL_WEBHOOK_ID`. |
| State machine + scheduled resume after pause | ✅ | tests; “skip ahead” button in *Try it* |
| AG Grid workspace: KPIs, reasons, views, quick search, saved layout, CSV export, row drawer with the agent's work | ✅ | Browser |
| Audit log (AG Grid) | ✅ | Browser |
| Waking-up screen for Render cold starts | ✅ | Shown while `/api/health` is unreachable |
| Demo data: 72 seeded attempts, ~14% save rate, labelled | ✅ | Workspace banner |
| 50-case eval (40 normal incl. Hinglish/Spanish/sarcasm, 10 adversarial) | 🟡 | Keyword baseline done: **0 violations**, 70% category accuracy. Gemini run needs key. |
| Dockerfile + `render.yaml` (one service serves API + built frontend) | 🟡 | Not test-built: Docker isn't installed on this PC. `npm run build` and serving `frontend/dist` from FastAPI were verified locally. |
| Learning loop (Thompson sampling) | ⬜ | Stretch, cut per plan. |
| Failed-payment recovery | ⬜ | Cut per plan. |

## Verify it yourself (10 minutes)
```bash
cd backend
.venv/Scripts/python -m pytest -q                 # expect: 34 passed
```
Run the app (two terminals, from the repo root):
```bash
backend/.venv/Scripts/python -m uvicorn --app-dir backend app.main:app --port 8000
```
```bash
npm --prefix frontend run dev
```
Then open http://localhost:5173 and check:
1. **Workspace**: KPIs, “Why subscribers leave”, the grid. Click a row → drawer shows steps 1–6.
2. **Try it** → Maya → *Continue to cancel* → *Accept offer* → “Done … $90 kept”.
3. **Try it** → Ben → reason → in the box type `Can you do 50%?` → *Ask* → offer stays at 30% with a note.
4. **Policy** → change “Largest discount” in the grid → *Apply* → version goes up.
5. **What-if simulator** → toggle rules in the left grid → right grid updates.
6. **Win-backs** → pick Priya → *Send CANCELLED webhook* → then *Re-send the same event* → “duplicate delivery ignored”.

### Verify the live PayPal path (needs your US sandbox buyer)
1. *Try it* → **Subscribe** (PayPal button) → log in as the **US Personal** sandbox account → approve.
2. A new “Sandbox buyer · PayPal live” subscriber appears; select it.
3. Type “I'm travelling for 3 months” → *Accept offer* → behind the scenes shows real `GET` + `POST …/suspend` calls with PayPal debug ids.
4. Check in sandbox.paypal.com (buyer) → the subscription shows as suspended.
5. Optional: subscribe again, give a price reason, accept the discount → the PayPal popup asks for approval → after approving, the attempt flips to **Saved** (confirmed by re-reading PayPal). This also answers the open question of whether the trial-phase discount applies on a revise; tell Claude what the buyer's PayPal page shows as the next price.

## Plan to the deadline
| Date | Who | What |
|---|---|---|
| Nov 5 | Claude | Build complete, pushed ✅ |
| Nov 5–6 | You | Gemini key → Claude runs eval + warms cache. Run the live PayPal path once. |
| Nov 6–7 | You (+ Claude) | Deploy to Render; set env vars; add URL + sandbox buyer login to README. **Feature freeze Nov 7.** |
| Nov 8–10 | You | Record the video from `DEVPOST.md` script; upload to YouTube (unlisted is fine). |
| Nov 11 | You | Fill the Devpost form from `DEVPOST.md`; check repo is public, MIT visible. |
| Nov 12 (evening IST) | You | Click **Submit** (not just “save draft”). |

## Deploy to Render (free)
1. render.com → New → **Blueprint** → select this GitHub repo (it reads `render.yaml`).
2. Fill the env vars when asked: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `GEMINI_API_KEY`, and `PUBLIC_URL` + `FRONTEND_ORIGIN` = the service URL (e.g. `https://saveflow.onrender.com`). Leave `PAYPAL_WEBHOOK_ID` empty unless you set up the webhook (step 4).
3. Wait for the Docker build. Open the URL: you should see “Waking up…” then the workspace. If the build fails, paste the log to Claude.
4. Optional real webhooks: PayPal app → Webhooks → add `https://<your-url>/api/webhooks/paypal` for `BILLING.SUBSCRIPTION.*` and `PAYMENT.SALE.COMPLETED` → copy the webhook id into `PAYPAL_WEBHOOK_ID` on Render.

## Risks (honest)
- **No Gemini key yet** is the biggest risk: without it the “AI” is a keyword fallback. Fix today.
- **Render free tier** sleeps; first load 30–60 s. The waking screen handles it; mention it in the README (done).
- **Gemini free-tier limits during judging** (Dec 1–15): the scripted scenarios are cached after `warm_cache`; anything a judge types still calls Gemini live and falls back (labelled) if rate-limited.
- **Live demo depends on judges logging into the sandbox**: most won't. The simulated personas cover the story; the video must show the live PayPal path.
- **Trial-phase discount on revise is unverified** (see the live-path step 5).

## Files
- `CLAUDE.md`: project context and rules · `README.md`: judge-facing · `DEVPOST.md`: submission text + video script
- Backend: `backend/app/` (policy, agent, paypal, services, api) · tests: `backend/tests/` · eval: `backend/tests/eval/`
- Frontend: `frontend/src/pages/` (Dashboard, CancelFlow, PolicySettings, Simulator, WinBacks, AuditLog)
