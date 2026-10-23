"""Notice-deadline rules from the synthetic contract (Demo 1's contract), as plain code.

Section 6.2 sets the notice period for a potential change:
  (a) 7 days after CM receives an RFI response, ASI, or submittal return that changes cost or time
  (b) 7 days after a written or oral direction from Owner or Architect that CM believes is a change
  (c) concealed or unknown conditions: before disturbing, and no later than 7 days after first observing
  (d) 14 days after CM first knew or should have known of any other event that may increase cost or time
Section 1.4: "Days" are calendar days. If a period ends on a Saturday, Sunday, or legal holiday,
it ends on the next business day.

The classifier (the AI) decides WHICH rule applies. This file turns that choice into a date, so the
date never depends on the model doing arithmetic.
"""
from datetime import date, timedelta

NOTICE_DAYS = {"6.2(a)": 7, "6.2(b)": 7, "6.2(c)": 7, "6.2(d)": 14}
NOTICE_RULES = list(NOTICE_DAYS) + ["none"]

# Washington State legal holidays in 2020 (RCW 1.16.050), observed dates.
HOLIDAYS_2020 = {
    date(2020, 1, 1), date(2020, 1, 20), date(2020, 2, 17), date(2020, 5, 25), date(2020, 7, 3),
    date(2020, 9, 7), date(2020, 11, 11), date(2020, 11, 26), date(2020, 11, 27), date(2020, 12, 25),
}


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS_2020


def notice_due(event_date: str, rule: str):
    """Return the notice due date (ISO string) for a rule, or None when no notice is required."""
    if rule not in NOTICE_DAYS:
        return None
    d = date.fromisoformat(event_date) + timedelta(days=NOTICE_DAYS[rule])
    while not is_business_day(d):  # Section 1.4 roll-forward
        d += timedelta(days=1)
    return d.isoformat()
