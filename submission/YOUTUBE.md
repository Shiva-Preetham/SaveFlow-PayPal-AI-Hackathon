# YouTube upload kit

Upload `submission/saveflow-demo.mp4` and use `submission/youtube-thumbnail.png` (1280×720, 0.5 MB).

## Settings
- **Visibility: Public.** Devpost rules usually ask for a publicly visible video; Public is the safe choice (Unlisted is often accepted, but don't risk it).
- **Audience:** “No, it's not made for kids”.
- **Altered or synthetic content:** the narration is an AI voice reading our own script; it doesn't depict real people or events, so YouTube doesn't require the label. It's disclosed in the description anyway.
- **Custom thumbnail:** YouTube allows custom thumbnails only on phone-verified channels (youtube.com/verify, takes 2 minutes).
- **Category:** Science & Technology.

## Title (86 characters; YouTube max 100)
```
SaveFlow: AI Agent That Saves Cancelling PayPal Subscribers | PayPal AI Hackathon Demo
```
Alternatives:
- `Stop Losing Subscribers: A Guardrailed AI Agent for PayPal Subscriptions (Hackathon Demo)`
- `SaveFlow – Retention AI for PayPal Subscriptions, Built for the PayPal AI Hackathon`

## Description
```
SaveFlow is the save-the-subscriber layer PayPal Subscriptions is missing. When a subscriber clicks Cancel, an AI agent reads why they're leaving (in their own words, any language) plus their real PayPal history, and makes the best offer the merchant allows: a pause, a discount or a cheaper plan, then executes it through the PayPal API.

▶ Live demo: https://saveflow-ufbx.onrender.com (free hosting: the first load can take ~1 minute to wake up)
▶ Code (MIT): https://github.com/Shiva-Preetham/SaveFlow-PayPal-AI-Hackathon

Chapters
0:00 Why PayPal merchants lose subscribers
0:21 Live: a real PayPal sandbox subscription paused by the agent
0:52 Prompt-injection attempt vs. the code guardrail
1:02 Hinglish reply + one negotiation, capped by policy
1:13 Plain-English policy compiler + what-if simulator
1:36 AG Grid workspace: the agent's work for every decision
1:50 Win-back webhook + eval results

How it stays safe
• Code computes which offers the merchant's policy allows; the AI can only choose from that list (structured output), and code rejects anything else.
• Every decision is audit-logged with the exact PayPal calls, idempotency keys and PayPal debug IDs.
• 50-case eval incl. 10 prompt-injection attacks, all answered by the model: 0 policy violations, 92% reason accuracy, 10/10 injections flagged.

What's in the demo
• PayPal Subscriptions API (sandbox): read history, suspend/activate for pauses, revise for plan changes with buyer approval, cancel; JS SDK Subscribe button; verified, idempotent webhooks for win-back.
• Merchants write retention rules in plain English; the AI turns them into structured rules, code validates them, and the merchant approves a summary written by code.
• A what-if simulator replays past cancellations against a proposed policy before it goes live.
• Merchant workspace built on AG Grid Community.

Built with: Python, FastAPI, SQLite, Google Gemini (structured output), PayPal Subscriptions API + JS SDK + Webhooks, React, TypeScript, Tailwind CSS, AG Grid Community, Render.

Notes
• PayPal sandbox only: no real money moves. “Sunrise Yoga Studio” is a made-up merchant, and dashboard history is labelled demo data.
• Narration: AI voice (Piper TTS, LJ Speech voice, public-domain training data). No music.
• Built by Shiva Preetham Chelimila for the PayPal AI Hackathon on Devpost. Not an official PayPal product.

#PayPal #AIagents #Hackathon
```

## Tags (YouTube “Tags” field)
```
PayPal, PayPal Subscriptions, PayPal API, PayPal AI Hackathon, Devpost, hackathon project, AI agent, subscription retention, churn reduction, cancel flow, win-back, guardrails, prompt injection, LLM guardrails, Gemini API, FastAPI, React, AG Grid, SaaS, small business
```
