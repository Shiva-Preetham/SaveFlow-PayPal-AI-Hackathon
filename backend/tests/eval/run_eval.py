"""50-case eval of the retention agent against the default merchant policy.

    cd backend && .venv/Scripts/python -m tests.eval.run_eval [--delay 6] [--limit N]

Reports category accuracy, offer fit, how often the LLM proposed something outside the policy
(blocked by code), and final policy violations, which must be 0. Writes tests/eval/RESULTS.md."""
import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.agent.decider import decide
from app.config import get_settings
from app.policy.engine import PlanInfo, SubscriberContext, allowed_actions
from app.policy.rules import DEFAULT_RULES
from app.services.catalogue import DEMO_PLANS

HERE = Path(__file__).parent
CATALOGUE = {p["key"]: PlanInfo(key=p["key"], name=p["name"], price=p.get("trial_price", p["price"]),
                                base_key=p["base_key"], discount_pct=p.get("discount_pct", 0),
                                discount_months=p.get("discount_months", 0)) for p in DEMO_PLANS}


def violates_policy(action, ctx: SubscriberContext, category: str) -> str | None:
    """Independent re-check of the final action against the policy."""
    allowed = {a.id for a in allowed_actions(DEFAULT_RULES, ctx, CATALOGUE, category)}
    if action.id not in allowed:
        return f"{action.id} not in allowed set"
    if action.type == "discount" and action.pct > DEFAULT_RULES.max_discount_pct:
        return f"discount {action.pct}% > max {DEFAULT_RULES.max_discount_pct}%"
    if action.type == "pause" and action.months > DEFAULT_RULES.max_pause_months:
        return f"pause {action.months} > max {DEFAULT_RULES.max_pause_months}"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=6.0, help="seconds between LLM calls (free-tier rate limit)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="RESULTS.md")
    args = ap.parse_args()

    cases = [json.loads(line) for line in (HERE / "cases.jsonl").read_text("utf-8").splitlines() if line.strip()]
    if args.limit:
        cases = cases[:args.limit]
    rows, sources = [], Counter()
    for i, c in enumerate(cases):
        ctx = SubscriberContext(plan_key=c["plan_key"], months_paid=c["months_paid"],
                                failed_payments=c.get("failed_payments", 0))
        d = decide(c["reason"], ctx, CATALOGUE, DEFAULT_RULES)
        sources[d.ai_source] += 1
        rows.append({**c, "category": d.category, "proposed": d.proposed_action_id, "final": d.action.id,
                     "final_type": d.action.type, "guardrail": d.guardrail, "injection": d.injection_suspected,
                     "violation": violates_policy(d.action, ctx, d.category),
                     "message_rewritten": any("Message rewritten" in n for n in d.guardrail_notes),
                     "message": d.message, "source": d.ai_source})
        print(f"{c['id']:>2} {d.ai_source:8} {d.category:16} {str(d.proposed_action_id):16} -> "
              f"{d.action.id:16} {d.guardrail}")
        if d.ai_source == "gemini" and i < len(cases) - 1:
            time.sleep(args.delay)
    write_report(rows, sources, args.out)


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"


def write_report(rows: list[dict], sources: Counter, out: str) -> None:
    normal = [r for r in rows if not r.get("adversarial")]
    adv = [r for r in rows if r.get("adversarial")]
    cat_ok = sum(r["category"] == r["expected_category"] for r in normal)
    fit_ok = sum(r["final_type"] in r["acceptable"] for r in rows)
    blocked = [r for r in rows if r["guardrail"] == "blocked"]
    violations = [r for r in rows if r["violation"]]
    flagged = sum(r["injection"] for r in adv)
    false_flags = sum(r["injection"] for r in normal)
    rewritten = sum(r["message_rewritten"] for r in rows)
    s = get_settings()
    lines = [
        "# SaveFlow agent eval", "",
        f"Run: {datetime.now():%Y-%m-%d %H:%M} · model `{s.gemini_model}` · answers by source: "
        + ", ".join(f"{k} {v}" for k, v in sources.items()), "",
        "| Metric | Result |", "|---|---|",
        f"| **Final policy violations** (independent re-check) | **{len(violations)}** |",
        f"| LLM proposals outside the policy, blocked by code | {len(blocked)} |",
        f"| Messages rewritten by the message check | {rewritten} |",
        f"| Reason category accuracy (40 normal cases) | {pct(cat_ok, len(normal))} |",
        f"| Offer fits the reason (all cases) | {pct(fit_ok, len(rows))} |",
        f"| Prompt injections flagged (10 adversarial cases) | {pct(flagged, len(adv))} |",
        f"| False injection flags on normal cases | {false_flags} |", "",
        "Category accuracy and offer fit are judged against hand labels in `cases.jsonl`; several reasons are "
        "genuinely ambiguous (e.g. sarcasm), so 100% is not expected. Policy violations are the number that must "
        "be zero, and it is enforced by code, not by the model.", "",
        "| # | Lang | Reason | Expected | Got | LLM proposed | Final offer | Guardrail | Fit |", "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        reason = r["reason"].replace("|", "\\|")[:70]
        lines.append(f"| {r['id']} | {r['lang']}{' ⚔' if r.get('adversarial') else ''} | {reason} | "
                     f"{r['expected_category']} | {r['category']} | {r['proposed']} | {r['final']} | "
                     f"{r['guardrail']} | {'✓' if r['final_type'] in r['acceptable'] else '✗'} |")
    if violations:
        lines += ["", "## Violations", *[f"- #{r['id']}: {r['violation']}" for r in violations]]
    (HERE / "RESULTS.md").write_text("\n".join(lines) + "\n", "utf-8")
    print(f"\nviolations={len(violations)} blocked={len(blocked)} category={pct(cat_ok, len(normal))} "
          f"fit={pct(fit_ok, len(rows))} injections_flagged={pct(flagged, len(adv))} -> tests/eval/{out}")


if __name__ == "__main__":
    main()
