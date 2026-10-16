"""Shared helpers for the rules extractor (Demo 1)."""
import re

RULE_TYPES = [
    "notice_window", "response_time", "deadline", "fee_rate", "fee_exclusion",
    "markup_limit", "cap", "amount", "pricing_input", "non_chargeable_cost",
    "equipment_rule", "approval_authority", "precedence", "interpretation",
    "non_authorization", "restriction", "waiver_consequence", "claim_rule",
    "payment_term", "audit_rule", "documentation_requirement", "process",
]

UNITS = ["days", "business days", "percent", "USD", "years", "other"]

_REPLACEMENTS = (
    ("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'),
    ("\u2013", "-"), ("\u2014", "-"), ("\u00a0", " "),
)


def normalize(text: str) -> str:
    """Normalize text so quotes can be compared across PDF/markdown/export differences.

    Removes markdown emphasis markers, straightens curly quotes and dashes, and
    collapses whitespace. The same function is used to build and to check quotes.
    """
    text = text.replace("**", "").replace("*", "")
    for old, new in _REPLACEMENTS:
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def normalize_unit(unit):
    """Map unit spellings to the canonical set used in the answer key."""
    if unit is None:
        return None
    u = str(unit).strip().lower()
    aliases = {
        "day": "days", "days": "days", "calendar days": "days", "calendar day": "days",
        "business day": "business days", "business days": "business days",
        "working days": "business days", "working day": "business days",
        "%": "percent", "percent": "percent", "percentage": "percent",
        "usd": "USD", "$": "USD", "dollars": "USD", "dollar": "USD",
        "year": "years", "years": "years",
    }
    return aliases.get(u, u)


def normalize_section(section: str) -> str:
    s = str(section).lower().replace("section", "").replace("\u00a7", "")
    return re.sub(r"\s+", "", s)
