"""Keyword classifier used only when the LLM is unavailable. Deliberately simple and labelled
'fallback' everywhere it is used."""
import re

_KEYWORDS: list[tuple[str, str]] = [
    ("competitor", r"switch(ing)? to|moving to|another (app|studio|service)|competitor|found (a )?(better|cheaper)|"
                   r"cheaper (app|alternative)|otra (app|aplicaci)"),
    ("temporary", r"travel|trip|vacation|holiday|exam|busy|moving house|relocat|surgery|injur|pregnan|"
                  r"for (a few|\d+|two|three) (weeks|months)|break|safar|bahar ja|viaje|vacaciones"),
    ("price", r"expensive|afford|money|price|cost|budget|broke|student|salary|job|mehenga|mehnga|paise|"
              r"paisa|caro|dinero"),
    ("product_problem", r"bug|crash|broken|doesn'?t work|not working|video(s)? (won'?t|don'?t)|quality|"
                        r"support|refund|instructor|login|kaam nahi|no funciona"),
    ("low_usage", r"don'?t use|not using|rarely|never use|no time|forgot|use it less|barely|"
                  r"use nahi|no lo uso"),
]


def classify(reason: str) -> tuple[str, str]:
    text = reason.lower()
    for category, pattern in _KEYWORDS:
        if re.search(pattern, text):
            return category, f"Keyword match: {category.replace('_', ' ')}"
    return "other", "No keyword matched"
