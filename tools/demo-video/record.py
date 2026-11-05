"""Drive the live SaveFlow site through the demo script and record it with Playwright.
Writes recording/*.webm and timeline.json (scene start times, seconds from video start).

    pip install playwright httpx pydantic-settings piper-tts && python -m playwright install ffmpeg
    python tts_piper.py <voices>/en_US-ljspeech-high.onnx 0.95   # or: powershell -File tts.ps1 -Dir .
    python record.py                                             # needs .env with the PayPal sandbox keys
    python assemble.py ../../submission/saveflow-demo.mp4"""
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
BASE = "https://saveflow-ufbx.onrender.com"
LIVE_SUB = "I-CPSRWGEEJPUN"
W, H = 1600, 900
DUR = {}
for s in json.loads((HERE / "scenes.json").read_text("utf-8")):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(HERE / f"audio_{s['id']}.wav")], capture_output=True, text=True)
    DUR[s["id"]] = float(out.stdout.strip())

CURSOR_JS = """
(() => {
  const add = () => {
    if (document.getElementById('__cursor') || !document.body) return;
    const c = document.createElement('div'); c.id = '__cursor';
    Object.assign(c.style, {position:'fixed', left:'800px', top:'450px', width:'22px', height:'22px',
      borderRadius:'50%', background:'rgba(13,148,136,0.30)', border:'2px solid #0f766e',
      pointerEvents:'none', zIndex:'2147483647', transform:'translate(-50%,-50%)',
      transition:'width .12s, height .12s'});
    document.body.appendChild(c);
    document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    document.addEventListener('mousedown', () => { c.style.width = '14px'; c.style.height = '14px'; }, true);
    document.addEventListener('mouseup', () => { c.style.width = '22px'; c.style.height = '22px'; }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
})();
"""

CARD = """<html><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:linear-gradient(135deg,#0f172a,#134e4a);font-family:'Segoe UI',system-ui,sans-serif;color:white">
<div style="max-width:1100px;padding:40px">{body}</div></body></html>"""

TITLE = CARD.format(body="""
<div style="display:flex;align-items:center;gap:18px;margin-bottom:28px">
 <div style="width:64px;height:64px;border-radius:16px;background:#0f766e;display:flex;align-items:center;
  justify-content:center;font-size:36px;font-weight:700">S</div>
 <div style="font-size:64px;font-weight:700">SaveFlow</div></div>
<div style="font-size:36px;line-height:1.3;color:#ccfbf1">The save-the-subscriber layer<br>for PayPal Subscriptions</div>
<div style="margin-top:36px;font-size:20px;color:#94a3b8">PayPal sandbox · Gemini · AG Grid Community ·
 demo merchant: Sunrise Yoga Studio (made up)</div>""")

EVAL = CARD.format(body="""
<div style="font-size:22px;color:#5eead4;letter-spacing:2px;text-transform:uppercase">50-case agent eval · all answered by Gemini</div>
<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px;margin-top:28px">
 <div style="background:#ffffff14;border-radius:16px;padding:26px"><div style="font-size:64px;font-weight:700">0</div>
  <div style="font-size:22px;color:#cbd5e1">policy violations (independent re-check)</div></div>
 <div style="background:#ffffff14;border-radius:16px;padding:26px"><div style="font-size:64px;font-weight:700">10 / 10</div>
  <div style="font-size:22px;color:#cbd5e1">prompt injections flagged, 0 false flags</div></div>
 <div style="background:#ffffff14;border-radius:16px;padding:26px"><div style="font-size:64px;font-weight:700">92%</div>
  <div style="font-size:22px;color:#cbd5e1">reason accuracy (EN, Hinglish, ES, sarcasm)</div></div>
 <div style="background:#ffffff14;border-radius:16px;padding:26px"><div style="font-size:64px;font-weight:700">50 / 50</div>
  <div style="font-size:22px;color:#cbd5e1">offers fit the reason</div></div>
</div>
<div style="margin-top:22px;font-size:18px;color:#94a3b8">Details: backend/tests/eval/RESULTS.md in the repo</div>""")

END = CARD.format(body="""
<div style="font-size:60px;font-weight:700">SaveFlow</div>
<div style="font-size:32px;color:#ccfbf1;margin-top:10px">Keep the subscribers you're about to lose.</div>
<div style="margin-top:40px;font-size:24px;color:#e2e8f0;line-height:1.7">
 Live demo: saveflow-ufbx.onrender.com<br>Code: github.com/Shiva-Preetham/SaveFlow-PayPal-AI-Hackathon</div>
<div style="margin-top:28px;font-size:18px;color:#94a3b8">PayPal sandbox only · no real money moves · MIT license</div>""")


def prepare() -> None:
    """Fresh demo state + the live sandbox subscription registered and ACTIVE."""
    sys.path.insert(0, str(HERE.parents[1] / "backend"))
    from app.config import get_settings
    from app.paypal.client import PayPalClient
    pp = PayPalClient(get_settings())
    status = pp.call("GET", f"/v1/billing/subscriptions/{LIVE_SUB}")["status"]
    if status == "SUSPENDED":
        pp.call("POST", f"/v1/billing/subscriptions/{LIVE_SUB}/activate", {"reason": "Reset for demo recording"})
        time.sleep(3)
    c = httpx.Client(base_url=f"{BASE}/api", timeout=120)
    c.get("/health")
    c.post("/demo/reset")
    time.sleep(2)
    sub = c.post("/subscribers/live", json={"subscription_id": LIVE_SUB, "name": "Sandbox buyer"}).json()
    print("prepared:", sub["name"], sub["state"], "PayPal was", status)


def main() -> None:
    prepare()
    timeline = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                                  record_video_dir=str(HERE / "recording"), record_video_size={"width": W, "height": H})
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        t0 = time.monotonic()
        now = lambda: time.monotonic() - t0
        mouse = {"x": W / 2, "y": H / 2}

        def scene(sid, fn):
            start = now()
            timeline.append({"id": sid, "start": round(start, 2)})
            print(f"{start:6.1f}s {sid}")
            fn()
            left = DUR[sid] + 0.8 - (now() - start)
            if left > 0:
                page.wait_for_timeout(left * 1000)

        def show(loc, block="center"):
            loc.evaluate(f"el => el.scrollIntoView({{behavior: 'smooth', block: '{block}'}})")
            page.wait_for_timeout(900)

        def move(loc):
            loc.scroll_into_view_if_needed()
            b = loc.bounding_box()
            x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
            page.mouse.move(x, y, steps=22)
            mouse.update(x=x, y=y)
            page.wait_for_timeout(200)

        def click(loc):
            move(loc)
            page.mouse.click(mouse["x"], mouse["y"])
            page.wait_for_timeout(350)

        def type_into(loc, text):
            click(loc)
            page.keyboard.press("Control+A")
            page.keyboard.type(text, delay=38)

        def nav(name):
            click(page.locator("header nav a", has_text=name))
            page.wait_for_timeout(700)

        btn = lambda name: page.get_by_role("button", name=name, exact=True)

        # --- scenes
        def title():
            page.set_content(TITLE)

        def workspace():
            page.goto(BASE + "/")
            page.get_by_text("Retention workspace").wait_for(timeout=90_000)
            page.locator(".ag-row").first.wait_for(timeout=30_000)
            page.wait_for_timeout(1200)
            move(page.get_by_text("Revenue kept (12-mo est.)"))
            page.wait_for_timeout(2500)
            move(page.get_by_text("Why subscribers leave"))
            page.wait_for_timeout(2500)
            show(page.locator(".ag-root-wrapper").first)

        def live_a1():
            nav("Try it as a subscriber")
            click(page.locator("button", has_text="…JPUN").first)
            type_into(page.get_by_placeholder("Any language is fine"), "I'm travelling for 3 months and money's tight")
            click(btn("Continue to cancel"))
            btn("Accept offer").wait_for(timeout=60_000)  # live Gemini call: the next line starts when it answers

        def live_a2():
            page.wait_for_timeout(1200)
            show(page.get_by_text("2 · What the agent read from PayPal"), "start")
            page.wait_for_timeout(2500)
            show(page.get_by_text("3 · Offers the merchant's policy allows (computed by code)"), "start")
            page.wait_for_timeout(2500)
            show(btn("Accept offer"))

        def live_b():
            click(btn("Accept offer"))
            page.get_by_text("Done:").wait_for(timeout=60_000)
            page.wait_for_timeout(1200)
            show(page.get_by_text("PayPal API calls ("), "start")

        def injection():
            show(page.get_by_text("Try it as a subscriber").first, "start")
            click(page.locator("button", has_text="Tom Becker"))
            click(btn("Continue to cancel"))
            page.get_by_text("Prompt injection suspected").first.wait_for(timeout=60_000)
            page.wait_for_timeout(800)
            show(page.get_by_text("4 · Decision and guardrail"), "start")

        def hinglish_a():
            show(page.get_by_text("Try it as a subscriber").first, "start")
            click(page.locator("button", has_text="Arjun Mehta"))
            click(btn("Continue to cancel"))
            btn("Accept offer").wait_for(timeout=60_000)
            page.wait_for_timeout(600)
            move(page.locator("p.whitespace-pre-line").first)

        def hinglish_b():
            type_into(page.get_by_placeholder('e.g. "Can you do 50%?"'), "Can you do 50%?")
            click(btn("Ask"))
            page.get_by_text("Requested 50%").first.wait_for(timeout=30_000)
            show(page.get_by_text("4 · Decision and guardrail"), "start")

        def policy():
            show(page.locator("header"), "start")
            nav("Policy")
            click(btn("Try an example"))
            page.wait_for_timeout(600)
            click(btn("Compile with AI"))
            page.get_by_text("Summary (written by code").wait_for(timeout=60_000)
            page.wait_for_timeout(1500)
            show(page.get_by_text("Not enforced").first)

        def simulator():
            click(btn("Test on past cancellations first"))
            page.locator(".ag-row").first.wait_for(timeout=30_000)
            page.wait_for_timeout(1500)
            move(page.get_by_text("Offers that change"))
            page.wait_for_timeout(1500)
            move(page.locator(".ag-row").nth(2))

        def grid():
            nav("Workspace")
            page.locator(".ag-row").first.wait_for(timeout=30_000)
            click(btn("Live PayPal"))
            page.wait_for_timeout(800)
            click(page.locator(".ag-row", has_text="JPUN").first)
            page.get_by_text("5 · PayPal API calls").wait_for(timeout=30_000)
            page.wait_for_timeout(2500)
            show(page.locator("aside").get_by_text("5 · PayPal API calls"), "start")
            page.wait_for_timeout(2500)
            click(page.locator("aside").get_by_role("button", name="Close"))

        def winback():
            nav("Win-backs")
            sel = page.locator("select")
            sel.wait_for()
            move(sel)
            value = sel.locator("option", has_text="Priya").get_attribute("value")
            sel.select_option(value)
            page.wait_for_timeout(500)
            click(btn("Send CANCELLED webhook"))
            page.get_by_text("win-back offer").first.wait_for(timeout=60_000)
            page.wait_for_timeout(1500)
            click(btn("Re-send the same event (duplicate)"))
            page.get_by_text("duplicate delivery ignored").wait_for(timeout=30_000)

        def eval_card():
            page.set_content(EVAL)

        def end():
            page.set_content(END)

        for sid, fn in [("title", title), ("workspace", workspace), ("live_a1", live_a1), ("live_a2", live_a2), ("live_b", live_b),
                        ("injection", injection), ("hinglish_a", hinglish_a), ("hinglish_b", hinglish_b),
                        ("policy", policy), ("simulator", simulator), ("grid", grid), ("winback", winback),
                        ("eval", eval_card), ("end", end)]:
            scene(sid, fn)
        total = now()
        video = page.video.path()
        ctx.close()
        browser.close()
    (HERE / "timeline.json").write_text(json.dumps({"scenes": timeline, "total": round(total, 2),
                                                    "video": str(video)}, indent=1), "utf-8")
    print(f"total {total:.1f}s -> {video}")


if __name__ == "__main__":
    main()
