"""Deterministic allowed-actions engine. The LLM may only pick from what this returns, and
`enforce` is the last word on whatever it picked."""
from dataclasses import asdict, dataclass

from app.policy.rules import PolicyRules


@dataclass(frozen=True)
class PlanInfo:
    key: str
    name: str
    price: float
    base_key: str
    discount_pct: int = 0
    discount_months: int = 0


@dataclass(frozen=True)
class SubscriberContext:
    plan_key: str
    months_paid: int
    failed_payments: int = 0
    offers_received: int = 0
    state: str = "ACTIVE"


@dataclass(frozen=True)
class Action:
    id: str
    type: str  # pause | discount | downgrade | cancel
    label: str
    months: int = 0
    pct: int = 0
    plan_key: str | None = None
    needs_buyer_approval: bool = False
    revenue_kept_12m: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


CANCEL = Action(id="cancel", type="cancel", label="No offer: cancel the subscription")


def _price(catalogue: dict[str, PlanInfo], key: str) -> float:
    return catalogue[key].price


def allowed_actions(rules: PolicyRules, ctx: SubscriberContext, catalogue: dict[str, PlanInfo],
                    category: str | None = None) -> list[Action]:
    """Every offer the merchant's policy allows for this subscriber. With category=None the
    category-specific rules are skipped (used to brief the LLM before it has classified)."""
    if ctx.state not in ("ACTIVE",) or ctx.plan_key not in catalogue:
        return [CANCEL]
    if ctx.offers_received >= rules.max_offers_per_subscriber:
        return [CANCEL]
    if category is not None and category in rules.no_offer_for:
        return [CANCEL]

    current = catalogue[ctx.plan_key]
    price = current.price
    actions: list[Action] = []

    if rules.pause_enabled and ctx.months_paid >= rules.min_paid_months_for_pause:
        for m in range(1, rules.max_pause_months + 1):
            actions.append(Action(id=f"pause_{m}", type="pause", label=f"Pause for {m} month(s)", months=m,
                                  revenue_kept_12m=round((12 - m) * price, 2)))

    discount_ok = (rules.discount_enabled and ctx.months_paid >= rules.min_paid_months_for_discount
                   and (category is None or not rules.discount_only_for or category in rules.discount_only_for))
    if discount_ok and current.discount_pct == 0:
        for p in sorted(catalogue.values(), key=lambda p: p.discount_pct):
            if p.base_key == current.key and 0 < p.discount_pct <= rules.max_discount_pct:
                kept = p.discount_months * p.price + (12 - p.discount_months) * price
                actions.append(Action(id=f"discount_{p.discount_pct}", type="discount",
                                      label=f"{p.discount_pct}% off for {p.discount_months} months",
                                      pct=p.discount_pct, months=p.discount_months, plan_key=p.key,
                                      needs_buyer_approval=True, revenue_kept_12m=round(kept, 2)))

    if rules.downgrade_enabled:
        for p in catalogue.values():
            if p.discount_pct == 0 and p.key != current.key and p.price < price:
                actions.append(Action(id=f"downgrade_{p.key}", type="downgrade", label=f"Switch to {p.name}",
                                      plan_key=p.key, needs_buyer_approval=True,
                                      revenue_kept_12m=round(12 * p.price, 2)))

    actions.append(CANCEL)
    return actions


# The safe default when the LLM is unavailable or picks something outside the allowed set.
_DEFAULT_ORDER = {
    "temporary": ["pause", "discount", "downgrade"],
    "price": ["discount", "downgrade", "pause"],
    "low_usage": ["downgrade", "pause", "discount"],
    "product_problem": ["pause", "downgrade"],
    "competitor": ["discount", "downgrade"],
    "other": ["pause", "downgrade"],
}


def safe_default(category: str, allowed: list[Action], rules: PolicyRules) -> Action:
    order = list(_DEFAULT_ORDER.get(category, ["pause"]))
    if category in rules.prefer:
        order.insert(0, rules.prefer[category])  # type: ignore[index]
    for kind in order:
        options = [a for a in allowed if a.type == kind]
        if options:
            # Smallest concession first: shortest pause is not ideal for travel, so pick the longest pause
            # only for temporary reasons; for discounts pick the largest the merchant allows.
            if kind == "pause":
                return options[-1] if category == "temporary" else options[0]
            if kind == "discount":
                return options[-1]
            return options[0]
    return CANCEL


@dataclass
class Enforced:
    action: Action
    guardrail: str  # passed | blocked
    note: str | None = None


def enforce(proposed_id: str | None, allowed: list[Action], category: str, rules: PolicyRules) -> Enforced:
    """Accept the LLM's pick only if it is in the allowed set; otherwise fall back to the safe default."""
    by_id = {a.id: a for a in allowed}
    if proposed_id in by_id:
        return Enforced(by_id[proposed_id], "passed")
    fallback = safe_default(category, allowed, rules)
    return Enforced(fallback, "blocked",
                    f"AI proposed '{proposed_id}', which is outside the merchant's policy for this subscriber. "
                    f"Replaced with the safe default '{fallback.id}'.")
