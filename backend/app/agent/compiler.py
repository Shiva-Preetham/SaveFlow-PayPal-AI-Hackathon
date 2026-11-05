"""Plain-English policy compiler: the LLM turns the merchant's rules into the PolicyRules schema,
code validates it, and the merchant approves a code-written summary before anything applies."""
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.agent import llm
from app.policy.engine import PlanInfo
from app.policy.rules import Category, PolicyRules, diff, summarize

SYSTEM = """You convert a small merchant's subscription retention rules, written in plain English, into a \
structured policy. Only encode what the merchant actually said; for anything they did not mention, use these \
defaults: pause_enabled=true, max_pause_months=3, min_paid_months_for_pause=0, discount_enabled=true, \
max_discount_pct=30, min_paid_months_for_discount=2, discount_only_for=[], downgrade_enabled=true, \
max_offers_per_subscriber=1, no_offer_for=[], prefer=[].
Reason categories: temporary (travel, exams, busy), price (money, students, budget), low_usage, product_problem, \
competitor, other. "Students get the cheaper plan" means prefer downgrade for price.
If the merchant writes a rule this schema cannot express (e.g. about specific customers by name, dates, \
free months, refunds), do NOT approximate it: list it in `unsupported` in their own words."""


class PreferOut(BaseModel):
    category: Category
    action: Literal["pause", "discount", "downgrade"]


class PolicyOut(BaseModel):
    pause_enabled: bool
    max_pause_months: int
    min_paid_months_for_pause: int
    discount_enabled: bool
    max_discount_pct: int
    min_paid_months_for_discount: int
    discount_only_for: list[Category]
    downgrade_enabled: bool
    max_offers_per_subscriber: int
    no_offer_for: list[Category]
    prefer: list[PreferOut]
    unsupported: list[str] = Field(description="Merchant rules that cannot be expressed in this schema")


@dataclass
class Compiled:
    ok: bool
    rules: PolicyRules | None = None
    summary: list[str] = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ai_source: str = "gemini"


def catalogue_warnings(rules: PolicyRules, catalogue: dict[str, PlanInfo]) -> list[str]:
    """Policies can only use discounts that exist as PayPal plans."""
    pcts = sorted({p.discount_pct for p in catalogue.values() if p.discount_pct})
    if not rules.discount_enabled or not rules.max_discount_pct or not pcts:
        return []
    usable = [p for p in pcts if p <= rules.max_discount_pct]
    if not usable:
        return [f"No discount plan is {rules.max_discount_pct}% or less (plans exist for {pcts}%), "
                "so no discount will be offered."]
    if usable[-1] != rules.max_discount_pct:
        return [f"There is no {rules.max_discount_pct}% plan in PayPal; the largest discount offered "
                f"will be {usable[-1]}%."]
    return []


def compile_policy(text: str, current: PolicyRules, catalogue: dict[str, PlanInfo],
                   db: Session | None = None) -> Compiled:
    try:
        out, source = llm.generate(SYSTEM, f"MERCHANT_RULES: <<<{text[:3000]}>>>", PolicyOut, db)
    except llm.LlmUnavailable as e:
        return Compiled(ok=False, errors=[f"AI is unavailable ({e}). Edit the policy fields in the grid instead."],
                        ai_source="fallback")
    data = out.model_dump()
    unsupported = data.pop("unsupported")
    data["prefer"] = {p["category"]: p["action"] for p in data["prefer"]}
    try:
        rules = PolicyRules.model_validate(data)
    except ValidationError as e:
        errs = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']} (got {err.get('input')!r})"
                for err in e.errors()]
        return Compiled(ok=False, errors=errs, ai_source=source)
    warnings = [f"Not enforced (SaveFlow can't express this rule yet): {u}" for u in unsupported]
    warnings += catalogue_warnings(rules, catalogue)
    return Compiled(ok=True, rules=rules, summary=summarize(rules), changes=diff(current, rules),
                    warnings=warnings, ai_source=source)
