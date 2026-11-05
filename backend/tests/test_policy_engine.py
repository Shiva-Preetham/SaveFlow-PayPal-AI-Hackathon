from app.policy.engine import PlanInfo, SubscriberContext, allowed_actions, enforce, safe_default
from app.policy.rules import DEFAULT_RULES, PolicyRules, summarize

CAT = {
    "pro": PlanInfo("pro", "Pro", 10.0, "pro"),
    "pro_off20": PlanInfo("pro_off20", "Pro 20%", 8.0, "pro", 20, 2),
    "pro_off30": PlanInfo("pro_off30", "Pro 30%", 7.0, "pro", 30, 2),
    "pro_off50": PlanInfo("pro_off50", "Pro 50%", 5.0, "pro", 50, 1),
    "lite": PlanInfo("lite", "Lite", 5.0, "lite"),
}


def ids(actions) -> set[str]:
    return {a.id for a in actions}


def test_discounts_capped_by_policy_and_cancel_always_allowed():
    ctx = SubscriberContext(plan_key="pro", months_paid=6)
    got = ids(allowed_actions(DEFAULT_RULES, ctx, CAT, "price"))
    assert {"discount_20", "discount_30", "pause_3", "downgrade_lite", "cancel"} <= got
    assert "discount_50" not in got  # policy max is 30%


def test_tenure_rules_and_one_offer_per_customer():
    new = SubscriberContext(plan_key="pro", months_paid=1)
    assert not any(a.startswith("discount") for a in ids(allowed_actions(DEFAULT_RULES, new, CAT, "price")))
    already = SubscriberContext(plan_key="pro", months_paid=12, offers_received=1)
    assert ids(allowed_actions(DEFAULT_RULES, already, CAT, "price")) == {"cancel"}


def test_category_rules():
    rules = PolicyRules(discount_only_for=["price"], no_offer_for=["product_problem"])
    ctx = SubscriberContext(plan_key="pro", months_paid=6)
    assert not any(a.startswith("discount") for a in ids(allowed_actions(rules, ctx, CAT, "temporary")))
    assert ids(allowed_actions(rules, ctx, CAT, "product_problem")) == {"cancel"}


def test_lite_subscriber_has_no_downgrade_and_suspended_only_cancel():
    lite = SubscriberContext(plan_key="lite", months_paid=6)
    assert not any(a.startswith("downgrade") for a in ids(allowed_actions(DEFAULT_RULES, lite, CAT, "price")))
    paused = SubscriberContext(plan_key="pro", months_paid=6, state="SUSPENDED")
    assert ids(allowed_actions(DEFAULT_RULES, paused, CAT)) == {"cancel"}


def test_enforce_blocks_out_of_policy_pick_and_falls_back():
    ctx = SubscriberContext(plan_key="pro", months_paid=6)
    allowed = allowed_actions(DEFAULT_RULES, ctx, CAT, "price")
    result = enforce("discount_100", allowed, "price", DEFAULT_RULES)
    assert result.guardrail == "blocked"
    assert result.action.id in ids(allowed) and result.action.id == "discount_30"
    assert enforce("pause_2", allowed, "price", DEFAULT_RULES).guardrail == "passed"


def test_safe_default_prefers_longest_pause_for_temporary():
    ctx = SubscriberContext(plan_key="pro", months_paid=6)
    allowed = allowed_actions(DEFAULT_RULES, ctx, CAT, "temporary")
    assert safe_default("temporary", allowed, DEFAULT_RULES).id == "pause_3"


def test_revenue_estimates():
    ctx = SubscriberContext(plan_key="pro", months_paid=6)
    by_id = {a.id: a for a in allowed_actions(DEFAULT_RULES, ctx, CAT, "price")}
    assert by_id["pause_3"].revenue_kept_12m == 90.0
    assert by_id["discount_30"].revenue_kept_12m == 2 * 7 + 10 * 10
    assert by_id["downgrade_lite"].revenue_kept_12m == 60.0


def test_summary_is_written_by_code():
    lines = summarize(PolicyRules(max_discount_pct=20, no_offer_for=["competitor"]))
    assert any("at most 20% off" in line for line in lines)
    assert any("moving to a competitor" in line for line in lines)
    assert lines[-1].startswith("Cancelling is always possible")


def test_preference_for_disabled_action_is_dropped():
    rules = PolicyRules(discount_enabled=False, prefer={"price": "discount"})
    assert rules.prefer == {}
