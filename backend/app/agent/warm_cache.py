"""Record Gemini's answers for the scripted demo scenarios into the committed demo cache, so the
hosted demo and the video keep working when the free tier is rate-limited during judging.

    cd backend && .venv/Scripts/python -m app.agent.warm_cache

Only exact scripted inputs hit the cache; anything a judge types goes to Gemini live."""
import json
import os
import re
import time

os.environ.setdefault("DATABASE_URL", "sqlite:///./warm_cache.db")
os.environ["SYNC_CATALOGUE_ON_START"] = "false"

from app.agent import llm  # noqa: E402
from app.agent.compiler import compile_policy  # noqa: E402
from app.agent.decider import decide  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Subscriber  # noqa: E402
from app.policy.rules import DEFAULT_RULES, DEFAULT_SOURCE, PolicyRules  # noqa: E402
from app.services import catalogue as cat  # noqa: E402
from app.services.retention import read_history, win_back_inputs  # noqa: E402
from app.services.seed import seed  # noqa: E402
from app.services.webhooks import WIN_BACK_REASON  # noqa: E402

POLICY_EXAMPLE = ("Never give more than 20% off. Students who say it's too expensive should get the Lite plan instead. "
                  "Pauses only after 3 paid months, max 2 months. If someone has a problem with the app, don't make an "
                  "offer — just let them go. Give Jane from the Tuesday class a free month.")


def main() -> None:
    if not get_settings().gemini_configured:
        raise SystemExit("Set GEMINI_API_KEY in .env first.")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    llm.capture = {}
    with SessionLocal() as db:
        seed(db)
        catalogue = cat.catalogue(db)
        for sub in db.query(Subscriber).filter(Subscriber.persona.is_not(None)):
            ctx, extra = read_history(db, sub, [])
            reason = re.search(r'"([^"]+)"', sub.persona or "")
            if reason:
                d = decide(reason.group(1).strip(), ctx, catalogue, DEFAULT_RULES, None, extra)
                print(f"{sub.name:16} {d.ai_source:7} {d.category:10} -> {d.action.id}")
                if d.ai_source == "gemini":
                    time.sleep(5)
            win_ctx, no_pause, win_extra = win_back_inputs(ctx, DEFAULT_RULES, extra)
            d = decide(WIN_BACK_REASON, win_ctx, catalogue, no_pause, None, win_extra)
            print(f"{sub.name:16} win-back -> {d.action.id}")
            time.sleep(5)
        for text in (DEFAULT_SOURCE, POLICY_EXAMPLE):
            r = compile_policy(text, PolicyRules.model_validate(DEFAULT_RULES.model_dump()), catalogue)
            print("compile", r.ok, r.ai_source, r.warnings)
            time.sleep(5)
    # Keep exactly the answers this run used (reused or fresh), so prompts that changed drop out.
    llm.DEMO_CACHE_FILE.write_text(json.dumps(llm.capture, indent=1, ensure_ascii=False), "utf-8")
    print(f"Wrote {len(llm.capture)} answers to {llm.DEMO_CACHE_FILE}")


if __name__ == "__main__":
    main()
