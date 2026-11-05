"""The only place SaveFlow talks to an LLM: Gemini with structured (Pydantic) output.
Answers are cached by prompt hash in the DB and in a committed demo cache, so the demo keeps
working when the free tier is rate-limited during judging."""
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LlmCache

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

DEMO_CACHE_FILE = Path(__file__).with_name("demo_cache.json")
_demo_cache: dict[str, dict] | None = None
_client = None
capture: dict[str, dict] | None = None  # set by warm_cache to record fresh answers for the committed demo cache


class LlmUnavailable(Exception):
    pass


def cache_key(system: str, prompt: str, schema: type[BaseModel]) -> str:
    raw = json.dumps([get_settings().gemini_model, system, prompt, schema.__name__])
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


def _call_gemini(system: str, prompt: str, schema: type[T]) -> T:
    from google.genai import errors, types
    config = types.GenerateContentConfig(system_instruction=system, temperature=0.2,
                                         response_mime_type="application/json", response_schema=schema,
                                         http_options=types.HttpOptions(timeout=30_000))
    for attempt in range(2):
        try:
            resp = _gemini().models.generate_content(model=get_settings().gemini_model, contents=prompt,
                                                     config=config)
            if isinstance(resp.parsed, schema):
                return resp.parsed
            return schema.model_validate_json(resp.text or "")
        except errors.APIError as e:
            log.warning("Gemini error %s (attempt %d): %s", e.code, attempt + 1, e.message)
            if e.code in (429, 500, 503) and attempt == 0:
                time.sleep(3)
                continue
            raise LlmUnavailable(f"Gemini {e.code}: {e.message}") from e
        except ValidationError as e:
            raise LlmUnavailable(f"Gemini returned output that does not match the schema: {e}") from e
    raise LlmUnavailable("Gemini did not answer")


def generate(system: str, prompt: str, schema: type[T], db: Session | None = None) -> tuple[T, str]:
    """Returns (parsed answer, source) where source is 'cache' or 'gemini'. Raises LlmUnavailable."""
    key = cache_key(system, prompt, schema)
    if key in _demo():
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
