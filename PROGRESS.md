# SaveFlow progress (read this first)

_Last updated: Nov 5, 2026. Deadline: **Nov 12, 12:00 PM PST = Nov 13, 1:30 AM IST**. Target: submit Nov 12 evening IST._

## Where we are
The full app is built and pushed to GitHub. It runs locally end to end. Three things block a strong submission, and only you can do them:

| # | What | Why it matters | Time |
|---|---|---|---|
| 1 | ~~Put a real Gemini API key in `.env`~~ | Done Nov 5. Measured free-tier limit on `gemini-2.5-flash`: **5/min, 20/day**. So the agent now walks a chain of models (3.1 Flash-Lite → 2.5 Flash-Lite → 3.5 Flash-Lite → Flash-Lite latest → 2.5 Flash), each with its own quota. | ✅ |
| 2 | ~~Deploy to Render~~ | Live at https://saveflow-ufbx.onrender.com (Nov 5). Verified: health, PayPal plans reused (no duplicates), cached + live Gemini answers. **Set `PUBLIC_URL` and `FRONTEND_ORIGIN` on Render to that URL** (check: `/api/health` shows `public_url`). | ✅ |
| 3 | ~~Record the demo video~~ | Done Nov 5: `submission/saveflow-demo.mp4` (2:16, 1080p, captions). Voice: Piper neural TTS, `en_US-ljspeech-high` (public-domain training data). Recorded on the live site, including a real PayPal `suspend`. Rebuild with `tools/demo-video/`. | ✅ |
| 4 | ~~Upload the video to YouTube~~ | Public: https://youtu.be/_eDtsG07IjE (Nov 5) | ✅ |
| 5 | ~~Submit on Devpost~~ | **Submitted Nov 6, 2026**: https://devpost.com/software/saveflow (editable until Nov 12, 3:00 PM EST). | ✅ |
| 6 | **Keep everything working until Dec 21** | Organisers (Nov 6 update): keep the demo, test credentials and any trials/credits active until winners are announced on **Dec 21**. Keep the Render service, the PayPal sandbox app + buyer login, and the Gemini key. Set a free uptime monitor on `https://saveflow-ufbx.onrender.com/api/health` every 10 min from Dec 1 to Dec 21. Don't run the eval or cache warmer then (Gemini quota). | 10 min |
| 7 | **No edits after the deadline** | Organisers: *“After the deadline, submissions are locked. Don't edit your repo, video, or linked materials until after the winner announement.”* Any repo change (even docs) must be pushed **before Nov 12, 12:00 PM PST** (Nov 13, 1:30 AM IST); after that, no pushes, no video changes until Dec 21. | — |

### Judging (from the organisers' updates)
- **Stage One (eligibility):** working build, public repo with an open-source licence, public video under 3 minutes, meaningful use of PayPal and AI. SaveFlow meets all four. Submitted Nov 6, inside the “submit today to still get an early eligibility check” window; watch your Devpost email for any flagged fixes.
- **Stage Two:** judges score 1–5 on Technological Implementation, Design, Potential Impact, Innovation/Idea, and Presentation. **Judges aren't required to run the project, so the video carries a lot of weight.** An AI voiceover is explicitly fine.
- Eligibility: above the age of majority in your country; all countries except Devpost's standard exceptions (India is not excluded).
- Dates (IST): submissions close Nov 13, 1:30 AM; judging Dec 2, 3:30 AM – Dec 15, 9:30 PM; winners Dec 21, 10:30 PM.

Remaining for you: run the live PayPal path once (below), deploy, video, submit. **Also add the Gemini key on Render** (`GEMINI_API_KEY`).

## What is built (and how it was verified)
Legend: ✅ verified by tests or by running it · 🟡 built, needs your sandbox login or key to verify · ⬜ not built

| Feature | Status | How it was verified / how you can verify |
|---|---|---|
| Policy engine: allowed offers per subscriber (tenure, one offer per customer, category rules, discount cap) | ✅ | `tests/test_policy_engine.py` (9 tests) |
| Guardrail: LLM pick outside the allowed set → blocked → safe default; message promising another amount → rewritten | ✅ | `tests/test_agent.py` with a fake LLM; seeded “Blocked” rows in the workspace |
| Prompt-injection flag (model flag + code regex) | ✅ | tests; Tom persona in *Try it* |
| Gemini decision agent (structured output, reads PayPal history, writes message in subscriber's language) | ✅ | Real Gemini: Maya → pause_3 citing 14 months; Arjun (Hinglish) → 30% off; Tom (injection) flagged. 503 overload fell back to rules, as designed. |
| Plain-English policy compiler + code-written summary + diff + “not enforced” warnings | ✅ | Real Gemini compiled the example correctly (20% max, pause 2 mo after 3 paid, no offer for app problems) and flagged “free month for Jane” as not enforced |
| Inline policy editing in AG Grid → server validation → diff → apply as new version | ✅ | Clicked through in the browser (max discount 30 → 20 showed “Apply 1 change”) |
| What-if simulator (AG Grid, changed rows highlighted, totals row) | ✅ | Browser: 32 of 73 offers change under “max 20%, no offer for product problems” |
| Cancel flow (subscriber view + “behind the scenes” merchant panel) | ✅ | Browser: Maya → pause offer → accepted → saved, $90 / 12 mo |
| Counter-offer (one, capped at the policy limit) | ✅ | API test: “Can you do 50%?” → 30% with note; 2nd counter → 409 |
| PayPal client: OAuth cache, idempotency key on every call, timeout, debug_id in errors | ✅ | `tests/test_paypal_client.py`; a failed live call is kept on the attempt + audit log (`test_paypal_failure_is_recorded_with_debug_id`) |
| PayPal catalogue: product + Pro, 20%/30%/50% discount plans (trial cycles), Lite; find-or-create (no duplicates) | ✅ | Ran twice against your sandbox: same 5 plan ids both times |
| PayPal Subscribe button (JS SDK) on *Try it* | ✅ renders | Seen in the browser with your sandbox plan |
| Live path: subscribe with sandbox buyer → cancel via SaveFlow → real `suspend` / `revise` popup / `cancel` | ✅ | Nov 5 on the hosted site: PayPal shows the subscription `SUSPENDED` (“Paused 3 months via SaveFlow”); plan switch to Lite approved in the popup and confirmed by re-reading PayPal (plan_id = Lite, new price from next billing date). Discount plan on revise (trial price) still unverified. |
| Webhooks: signature verification, dedupe by event id, reconcile from PayPal, win-back | ✅ / 🟡 | Simulated events tested (duplicate ignored). Real webhooks need a tunnel + `PAYPAL_WEBHOOK_ID`. |
| State machine + scheduled resume after pause | ✅ | tests; “skip ahead” button in *Try it* |
| AG Grid workspace: KPIs, reasons, views, quick search, saved layout, CSV export, row drawer with the agent's work | ✅ | Browser |
| Audit log (AG Grid) | ✅ | Browser |
| Waking-up screen for Render cold starts | ✅ | Shown while `/api/health` is unreachable |
| Demo data: 72 seeded attempts, ~14% save rate, labelled | ✅ | Workspace banner |
| Demo cache: Gemini answers for the 6 scripted personas, their win-backs and 2 policy compiles | ✅ | Served in 0.0–0.1 s with no quota used; regenerate with `python -m app.agent.warm_cache` only if prompts change |
| 50-case eval (40 normal incl. Hinglish/Spanish/sarcasm, 10 adversarial) | ✅ | All 50 by Gemini: **0 violations**, 92% category accuracy, 50/50 offer fit, 10/10 injections flagged, 0 false flags (`backend/tests/eval/RESULTS.md`). Keyword baseline: 70%. |
| Dockerfile + `render.yaml` (one service serves API + built frontend) | ✅ | Built and deployed on Render in 55 s; live at https://saveflow-ufbx.onrender.com |
| Learning loop (Thompson sampling) | ⬜ | Stretch, cut per plan. |
| Failed-payment recovery | ⬜ | Cut per plan. |

## Verify it yourself (10 minutes)
```bash
cd backend
.venv/Scripts/python -m pytest -q                 # expect: 35 passed
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
3. **Try it** → Arjun → reason → in the box type `Can you do 50%?` → *Ask* → offer stays at 30% with a note.
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
- **The video uses an AI voice** (Piper, LJ Speech, public domain; much more natural than the Windows voice, which is kept as `submission/saveflow-demo-zira-voice.mp4`). A human voice can still land better; the narration lines are in `tools/demo-video/scenes.json` if you ever want to re-voice it.
- **The guardrail never fired in the eval**: Gemini always picked an allowed offer. That's good, but it means the eval shows the model behaving, not the guardrail. Blocking is proven by unit tests with a deliberately misbehaving model. Say this accurately in the video.
- **LLM messages can add unrequested details**: one cancel message said access lasts “until the end of the billing period”. The message check verifies amounts only. Low risk for the demo (cached messages were reviewed); a stricter check is a possible post-submission fix.
- **Gemini free-tier quota is tiny** (20 requests/day per model on 2.5 Flash, measured). The model chain multiplies capacity, scripted demo scenarios come from the committed cache, and anything beyond falls back to labelled rules. Don't run the eval or warm the cache on video day; it spends the daily quota. Quotas reset at midnight Pacific (1:30 PM IST).
- **Render free tier** sleeps; first load 30–60 s. The waking screen handles it; mention it in the README (done).
- **Gemini free-tier limits during judging** (Dec 1–15): the scripted scenarios are cached after `warm_cache`; anything a judge types still calls Gemini live and falls back (labelled) if rate-limited.
- **Live demo depends on judges logging into the sandbox**: most won't. The simulated personas cover the story; the video must show the live PayPal path.
- **Trial-phase discount on revise is unverified** (see the live-path step 5).

## Files
- `CLAUDE.md`: project context and rules · `README.md`: judge-facing · `DEVPOST.md`: submission text + video script
- Backend: `backend/app/` (policy, agent, paypal, services, api) · tests: `backend/tests/` · eval: `backend/tests/eval/`
- Frontend: `frontend/src/pages/` (Dashboard, CancelFlow, PolicySettings, Simulator, WinBacks, AuditLog)
