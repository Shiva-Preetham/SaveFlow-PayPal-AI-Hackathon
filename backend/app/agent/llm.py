"""The only place SaveFlow talks to an LLM: Gemini with structured (Pydantic) output.

Free-tier quotas are per model and small (measured on our key: gemini-2.5-flash = 5/min, 20/day), so
calls walk a chain of Gemini models and skip one that is rate-limited or overloaded. Answers are cached
by prompt hash in the DB and in a committed demo cache, so scripted demo scenarios never need a call."""
import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LlmCache

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

DEMO_CACHE_FILE = Path(__file__).with_name("demo_cache.json")
MAX_CHAIN_SECONDS = 25  # a subscriber is waiting; after this, use the rule-based fallback
_demo_cache: dict[str, dict] | None = None
_client = None
_no_thinking_budget: set[str] = set()  # models that reject thinking_budget (Gemini 3.5+ lite)
_cooldown_until: dict[str, float] = {}  # model -> time.time() before which we skip it
_local = threading.local()  # which model answered, per request thread
capture: dict[str, dict] | None = None  # set by warm_cache: every answer used, to rewrite the committed demo cache


class LlmUnavailable(Exception):
    pass


def models() -> list[str]:
    s = get_settings()
    chain = [s.gemini_model] + [m.strip() for m in s.gemini_fallback_models.split(",") if m.strip()]
    return list(dict.fromkeys(chain))


def last_model() -> str | None:
    """The model that produced the last live answer on this thread."""
    return getattr(_local, "model", None)


def cache_key(system: str, prompt: str, schema: type[BaseModel]) -> str:
    # Keyed on the prompt, not on which model in the chain answered, so cached demo answers stay valid.
    raw = json.dumps([system, prompt, schema.__name__])
    return hashlib.sha256(raw.encode()).hexdigest()


def _demo() -> dict[str, dict]:
    global _demo_cache
    if _demo_cache is None:
        _demo_cache = json.loads(DEMO_CACHE_FILE.read_text("utf-8")) if DEMO_CACHE_FILE.exists() else {}
    return _demo_cache


def _gemini():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=get_settings().gemini_api_key)
    return _client


def _next_pacific_midnight() -> float:
    # Free-tier daily quotas reset at midnight Pacific; PST (UTC-8) holds for the judging period.
    now = datetime.now(timezone.utc)
    reset = (now - timedelta(hours=8)).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1, hours=8)
    return reset.timestamp()


def _call_model(model: str, system: str, prompt: str, schema: type[T]) -> T:
    from google.genai import types
    budget = get_settings().gemini_thinking_budget
    thinking = (types.ThinkingConfig(thinking_budget=budget)
                if budget >= 0 and model not in _no_thinking_budget else None)
    config = types.GenerateContentConfig(system_instruction=system, temperature=0.2,
                                         response_mime_type="application/json", response_schema=schema,
                                         http_options=types.HttpOptions(timeout=20_000), thinking_config=thinking)
    resp = _gemini().models.generate_content(model=model, contents=prompt, config=config)
    if isinstance(resp.parsed, schema):
        return resp.parsed
    return schema.model_validate_json(resp.text or "")


def _call_gemini(system: str, prompt: str, schema: type[T]) -> T:
    from google.genai import errors
    started, problems = time.time(), []
    for model in models():
        if _cooldown_until.get(model, 0) > time.time():
            problems.append(f"{model}: rate-limited")
            continue
        if time.time() - started > MAX_CHAIN_SECONDS:
            problems.append("time budget used up")
            break
        for retry in range(2):
            try:
                out = _call_model(model, system, prompt, schema)
                _local.model = model
                return out
            except errors.APIError as e:
                msg = e.message or ""
                log.warning("Gemini %s error %s: %s", model, e.code,
                            "per-day quota" if "per day" in msg else "per-minute quota" if "per minute" in msg else msg[:160])
                if e.code == 400 and retry == 0 and model not in _no_thinking_budget:
                    _no_thinking_budget.add(model)  # retry once without the thinking setting
                    continue
                if e.code == 429:
                    _cooldown_until[model] = _next_pacific_midnight() if "per day" in msg else time.time() + 60
                elif e.code in (500, 503, 504):
                    _cooldown_until[model] = time.time() + 30
                problems.append(f"{model}: {e.code}")
                break
            except ValidationError:
                problems.append(f"{model}: output did not match the schema")
                break
    raise LlmUnavailable("all Gemini models unavailable (" + "; ".join(problems) + ")")


def generate(system: str, prompt: str, schema: type[T], db: Session | None = None) -> tuple[T, str]:
    """Returns (parsed answer, source) where source is 'cache' or 'gemini'. Raises LlmUnavailable."""
    key = cache_key(system, prompt, schema)
    _local.model = None
    if key in _demo():
        if capture is not None:
            capture[key] = _demo()[key]
        return schema.model_validate(_demo()[key]), "cache"
    if db is not None and (row := db.get(LlmCache, key)) is not None:
        return schema.model_validate(row.response), "cache"
    if not get_settings().gemini_configured:
        raise LlmUnavailable("GEMINI_API_KEY is not set")
    out = _call_gemini(system, prompt, schema)
    if capture is not None:
        capture[key] = out.model_dump(mode="json")
    if db is not None:
        db.merge(LlmCache(key=key, response=out.model_dump(mode="json")))
    return out, "gemini"
