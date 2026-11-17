#!/usr/bin/env python3
"""Independent reference CPM and time impact analysis (TIA) for the Demo 4 schedule model.

Written from first principles in plain Python (standard library only) to build the Demo 4 answer key
and to cross-check the JavaScript engine (assets/schedule.js). It does not share code with that engine.

Schedule model: docs/demo4-spec.md, section 1.

Conventions (stated here so the two engines can be compared line by line):
  * Working days are numbered from the project start. Day 0 is the first working day on or after
    schedule["start"]. Only calendar.workdays (ISO weekday numbers, Mon=1 ... Sun=7) that are not in
    calendar.holidays count.
  * ES and EF are working-day numbers with an exclusive end: ES = 0 and duration 5 occupy days 0-4, EF = 5.
    An activity's start date is the date of day ES; its finish date is the date of day EF - 1.
  * Milestones (duration 0) have ES = EF. Their date is the date of day EF - 1 (the working day the
    driving work finished), or day 0 when EF = 0. Project start milestones therefore sit on day 0 and
    finish milestones sit on the last day of the work that drives them, as P6 shows them.
  * Relationships, with lag L in working days (negative lags allowed):
        FS: ES(succ) >= EF(pred) + L        SS: ES(succ) >= ES(pred) + L
        FF: EF(succ) >= EF(pred) + L        SF: EF(succ) >= ES(pred) + L
  * Progress at the data date DD (a working-day number):
      - complete (actual_finish set): ES = day(actual_start), EF = day(actual_finish) + 1; fixed, not on
        any path, total float null. A completed milestone has ES = EF = day(actual_finish) + 1, so its
        date is its actual date under the milestone rule above.
      - in progress (actual_start set, no actual_finish): ES = day(actual_start) (fixed); remaining work
        runs from DD, so EF = max(DD + remaining, FF/SF predecessor constraints). FS/SS predecessor
        constraints are ignored (it already started). Its "working duration" for the backward pass is
        `remaining`.
      - not started: ES = max(DD, predecessor constraints, SNET/MSO), EF = ES + duration.
    Constraints from a completed predecessor still apply (they use its actual dates).
  * Constraints: SNET -> ES >= day(date); MSO -> ES = day(date) (forward) and LS <= day(date) (backward);
    FNLT -> LF <= finish_day(date) + 1; MFO -> EF = finish_day(date) + 1 forward and LF <= same backward.
    day(date) is the first working day on/after the date; finish_day(date) is the last working day on/before.
  * Backward pass: activities with no (incomplete) successors get LF = project finish (the largest EF).
        FS: LF(pred) <= LS(succ) - L        SS: LS(pred) <= LS(succ) - L
        FF: LF(pred) <= LF(succ) - L        SF: LS(pred) <= LF(succ) - L
    with LS = LF - working duration. SS/SF backward limits are skipped for in-progress predecessors
    (their start is history). Completed activities are skipped on both ends.
  * Total float = LF - EF (working days). Critical = total float <= 0. critical_path = critical
    activities sorted by (ES, EF, id).
  * Project finish = largest EF over all activities; finish_date = date of day (finish - 1).
  * tia(schedule, fragnet): adds the fragnet activities (not started) and relationships to a copy of
    the schedule, reruns CPM, and reports
        delay_workdays      = finish_after - finish_before        (working days)
        delay_calendar_days = finish_date_after - finish_date_before (calendar days)
    fragnet_critical is true when any fragnet activity has total float <= 0 in the impacted run.
    driving_path traces driving (binding) relationships back from the activity that sets the project
    finish in the impacted run.

Run self-tests:  python3 demo4/cpm_ref.py
"""
from datetime import date, timedelta
import copy

REL_TYPES = ("FS", "SS", "FF", "SF")


class ScheduleError(ValueError):
    pass


# ----------------------------------------------------------------------------- calendar
class Calendar:
    """Working-day numbering for one schedule."""

    def __init__(self, start, workdays=(1, 2, 3, 4, 5), holidays=(), horizon_days=4000):
        self.workdays = set(workdays)
        self.holidays = {date.fromisoformat(h) if isinstance(h, str) else h for h in holidays}
        self.start = date.fromisoformat(start) if isinstance(start, str) else start
        if not self.workdays:
            raise ScheduleError("calendar has no working weekdays")
        self.days = []          # day number -> date
        self.index = {}         # working date -> day number
        d = self.start
        end = self.start + timedelta(days=horizon_days)
        while d <= end:
            if self.is_workday(d):
                self.index[d] = len(self.days)
                self.days.append(d)
            d += timedelta(days=1)

    def is_workday(self, d):
        return d.isoweekday() in self.workdays and d not in self.holidays

    def _date(self, d):
        return date.fromisoformat(d) if isinstance(d, str) else d

    def day_on_or_after(self, d):
        d = self._date(d)
        if d < self.start:
            return 0
        while d not in self.index:
            d += timedelta(days=1)
            if d > self.days[-1]:
                raise ScheduleError("date beyond calendar horizon")
        return self.index[d]

    def day_on_or_before(self, d):
        d = self._date(d)
        while d not in self.index:
            d -= timedelta(days=1)
            if d < self.start:
                return -1
        return self.index[d]

    def date_of(self, n):
        if n < 0:
            raise ScheduleError(f"day {n} is before the project start")
        if n >= len(self.days):
            raise ScheduleError("day number beyond calendar horizon")
        return self.days[n]

    def iso(self, n):
        return self.date_of(n).isoformat()

    def add_workdays(self, d, n):
        """Date that is n working days after working date d (n may be 0)."""
        return self.date_of(self.day_on_or_after(d) + n)


# ----------------------------------------------------------------------------- CPM
def _status(a):
    if a.get("actual_finish"):
        return "complete"
    if a.get("actual_start"):
        return "active"
    return "open"


def _topo_order(ids, rels):
    succs = {i: [] for i in ids}
    indeg = {i: 0 for i in ids}
    for r in rels:
        succs[r["pred"]].append(r)
        indeg[r["succ"]] += 1
    ready = sorted(i for i in ids if indeg[i] == 0)
    order = []
    while ready:
        i = ready.pop(0)
        order.append(i)
        for r in succs[i]:
            indeg[r["succ"]] -= 1
            if indeg[r["succ"]] == 0:
                ready.append(r["succ"])
        ready.sort()
    if len(order) != len(ids):
        stuck = sorted(i for i in ids if indeg[i] > 0)
        raise ScheduleError("logic loop among: " + ", ".join(stuck[:10]))
    return order


def cpm(schedule):
    """Forward and backward pass. Returns a dict like the JS engine's cpm()."""
    calm = schedule.get("calendar", {})
    cal = Calendar(schedule["start"], calm.get("workdays", [1, 2, 3, 4, 5]), calm.get("holidays", []))
    acts = {a["id"]: a for a in schedule["activities"]}
    if len(acts) != len(schedule["activities"]):
        raise ScheduleError("duplicate activity ids")
    warnings = []
    rels = []
    for r in schedule.get("relationships", []):
        if r["pred"] not in acts or r["succ"] not in acts:
            warnings.append(f"relationship {r['pred']}->{r['succ']} refers to a missing activity; ignored")
            continue
        t = r.get("type", "FS")
        if t not in REL_TYPES:
            raise ScheduleError(f"bad relationship type {t}")
        rels.append({"pred": r["pred"], "succ": r["succ"], "type": t, "lag": int(r.get("lag", 0) or 0)})
    order = _topo_order(list(acts), rels)
    preds = {i: [] for i in acts}
    succs = {i: [] for i in acts}
    for r in rels:
        preds[r["succ"]].append(r)
        succs[r["pred"]].append(r)

    dd = cal.day_on_or_after(schedule.get("data_date") or schedule["start"])
    status = {i: _status(a) for i, a in acts.items()}
    wdur = {}
    for i, a in acts.items():
        if status[i] == "complete":
            wdur[i] = 0
        elif status[i] == "active":
            rem = a.get("remaining")
            wdur[i] = int(a["duration"] if rem is None else rem)
        else:
            wdur[i] = int(a["duration"])
        if wdur[i] < 0:
            raise ScheduleError(f"{i}: negative duration")

    ES, EF = {}, {}
    for i in order:
        a = acts[i]
        st = status[i]
        if st == "complete":
            if int(a["duration"]) == 0:          # completed milestone: ES = EF, dated on its actual day
                ES[i] = EF[i] = cal.day_on_or_before(a["actual_finish"]) + 1
            else:
                ES[i] = cal.day_on_or_after(a["actual_start"])
                EF[i] = cal.day_on_or_before(a["actual_finish"]) + 1
            continue
        if st == "active":
            ES[i] = cal.day_on_or_after(a["actual_start"])
            ef = dd + wdur[i]
            for r in preds[i]:
                p, L = r["pred"], r["lag"]
                if r["type"] == "FF":
                    ef = max(ef, EF[p] + L)
                elif r["type"] == "SF":
                    ef = max(ef, ES[p] + L)
            EF[i] = ef
            continue
        d = wdur[i]
        es = dd
        for r in preds[i]:
            p, L = r["pred"], r["lag"]
            if r["type"] == "FS":
                es = max(es, EF[p] + L)
            elif r["type"] == "SS":
                es = max(es, ES[p] + L)
            elif r["type"] == "FF":
                es = max(es, EF[p] + L - d)
            else:  # SF
                es = max(es, ES[p] + L - d)
        c = a.get("constraint")
        if c:
            if c["type"] == "SNET":
                es = max(es, cal.day_on_or_after(c["date"]))
            elif c["type"] == "MSO":
                es = cal.day_on_or_after(c["date"])
            elif c["type"] == "MFO":
                es = cal.day_on_or_before(c["date"]) + 1 - d
        ES[i] = es
        EF[i] = es + d

    finish = max(EF.values()) if EF else 0

    LF, LS = {}, {}
    for i in reversed(order):
        if status[i] == "complete":
            continue
        lf = finish
        for r in succs[i]:
            s, L = r["succ"], r["lag"]
            if status[s] == "complete":
                continue
            if r["type"] == "FS":
                lf = min(lf, LS[s] - L)
            elif r["type"] == "FF":
                lf = min(lf, LF[s] - L)
            elif status[i] == "active":
                continue  # SS / SF limit the start, which already happened
            elif r["type"] == "SS":
                lf = min(lf, LS[s] - L + wdur[i])
            else:  # SF
                lf = min(lf, LF[s] - L + wdur[i])
        c = acts[i].get("constraint")
        if c:
            if c["type"] in ("FNLT", "MFO"):
                lf = min(lf, cal.day_on_or_before(c["date"]) + 1)
            elif c["type"] == "MSO":
                lf = min(lf, cal.day_on_or_after(c["date"]) + wdur[i])
        LF[i] = lf
        LS[i] = lf - wdur[i]

    out = []
    for i in order:
        st = status[i]
        tf = None if st == "complete" else LF[i] - EF[i]
        dur0 = int(acts[i]["duration"]) == 0
        out.append({
            "id": i, "status": st, "es": ES[i], "ef": EF[i],
            "ls": LS.get(i), "lf": LF.get(i), "total_float": tf,
            "critical": tf is not None and tf <= 0,
            "start": cal.iso(_ms_day(EF[i]) if dur0 else ES[i]),
            "finish": cal.iso(_ms_day(EF[i])),
        })
    out.sort(key=lambda x: (x["es"], x["ef"], x["id"]))
    crit = [x["id"] for x in out if x["critical"]]
    return {"activities": out, "finish": finish, "finish_date": cal.iso(max(finish - 1, 0)),
            "data_date_day": dd, "critical_path": crit, "warnings": warnings,
            "_rels": rels, "_ES": ES, "_EF": EF, "_status": status, "_cal": cal}


def _ms_day(ef):
    return max(ef - 1, 0)


def driving_path(result, end_id=None):
    """Trace binding relationships back from end_id (default: the activity that sets the finish)."""
    ES, EF, status = result["_ES"], result["_EF"], result["_status"]
    if end_id is None:
        cands = [i for i in EF if EF[i] == result["finish"] and status[i] != "complete"]
        # prefer a zero-duration finish milestone, then the lowest id, for a stable answer
        cands.sort(key=lambda i: (EF[i] - ES[i] != 0, i))
        if not cands:
            return []
        end_id = cands[0]
    preds = {}
    for r in result["_rels"]:
        preds.setdefault(r["succ"], []).append(r)
    path = [end_id]
    cur = end_id
    seen = {cur}
    while True:
        nxt = None
        for r in sorted(preds.get(cur, []), key=lambda r: r["pred"]):
            p, L = r["pred"], r["lag"]
            if status[p] == "complete":
                continue
            binding = ((r["type"] == "FS" and EF[p] + L == ES[cur]) or
                       (r["type"] == "SS" and ES[p] + L == ES[cur]) or
                       (r["type"] == "FF" and EF[p] + L == EF[cur]) or
                       (r["type"] == "SF" and ES[p] + L == EF[cur]))
            if binding and p not in seen:
                nxt = p
                break
        if nxt is None:
            break
        path.append(nxt)
        seen.add(nxt)
        cur = nxt
    return list(reversed(path))


def tia(schedule, fragnet):
    """Prospective time impact analysis (AACE 52R-06 style) of a fragnet on the schedule."""
    for a in fragnet.get("activities", []):
        if not str(a["id"]).startswith("F-"):
            raise ScheduleError(f"fragnet id {a['id']} must start with F-")
    base_ids = {a["id"] for a in schedule["activities"]}
    frag_ids = {a["id"] for a in fragnet.get("activities", [])}
    if base_ids & frag_ids:
        raise ScheduleError("fragnet ids clash with schedule ids")
    for r in fragnet.get("relationships", []):
        for k in ("pred", "succ"):
            if r[k] not in base_ids and r[k] not in frag_ids:
                raise ScheduleError(f"fragnet relationship refers to unknown activity {r[k]}")
    before = cpm(schedule)
    impacted = copy.deepcopy(schedule)
    for a in fragnet.get("activities", []):
        impacted["activities"].append({"id": a["id"], "name": a.get("name", a["id"]), "duration": int(a["duration"]),
                                       "wbs": "Fragnet", "actual_start": None, "actual_finish": None,
                                       "remaining": None, "constraint": None})
    impacted["relationships"] = list(impacted.get("relationships", [])) + [
        {"pred": r["pred"], "succ": r["succ"], "type": r.get("type", "FS"), "lag": int(r.get("lag", 0) or 0)}
        for r in fragnet.get("relationships", [])]
    after = cpm(impacted)
    bf, af = date.fromisoformat(before["finish_date"]), date.fromisoformat(after["finish_date"])
    tf = {x["id"]: x["total_float"] for x in after["activities"]}
    frag_crit = any(tf.get(i) is not None and tf[i] <= 0 for i in frag_ids)
    dw = after["finish"] - before["finish"]
    notes = []
    if dw == 0 and frag_ids:
        mins = [tf[i] for i in frag_ids if tf.get(i) is not None]
        if mins:
            notes.append(f"fragnet absorbed by float; least fragnet float {min(mins)} working days")
    return {"before_finish": before["finish_date"], "after_finish": after["finish_date"],
            "delay_workdays": dw, "delay_calendar_days": (af - bf).days,
            "fragnet_critical": frag_crit, "driving_path": driving_path(after),
            "fragnet_float": {i: tf.get(i) for i in sorted(frag_ids)}, "notes": notes}


def public(result):
    """cpm() result without the private fields (for JSON)."""
    return {k: v for k, v in result.items() if not k.startswith("_")}


# ----------------------------------------------------------------------------- self-tests
def _sched(acts, rels, start="2020-02-03", holidays=(), data_date=None):
    return {"name": "t", "start": start, "data_date": data_date or start,
            "calendar": {"workdays": [1, 2, 3, 4, 5], "holidays": list(holidays)},
            "activities": [dict({"actual_start": None, "actual_finish": None, "remaining": None, "constraint": None,
                                 "wbs": "T", "name": a[0]}, id=a[0], duration=a[1], **(a[2] if len(a) > 2 else {}))
                           for a in acts],
            "relationships": [{"pred": p, "succ": s, "type": t, "lag": l} for p, s, t, l in rels]}


def _by_id(res):
    return {x["id"]: x for x in res["activities"]}


def _selftest():
    n = 0

    def check(cond, msg):
        nonlocal n
        n += 1
        if not cond:
            raise AssertionError(msg)

    # 1. calendar: 2020-02-03 is a Monday; Presidents Day 2020-02-17 is a holiday.
    cal = Calendar("2020-02-03", holidays=["2020-02-17"])
    check(cal.iso(0) == "2020-02-03" and cal.iso(4) == "2020-02-07" and cal.iso(5) == "2020-02-10", "weekend skip")
    check(cal.iso(10) == "2020-02-18", "holiday skip")
    check(cal.day_on_or_after("2020-02-08") == 5 and cal.day_on_or_before("2020-02-08") == 4, "weekend mapping")
    check(cal.day_on_or_after("2020-01-01") == 0, "before start maps to day 0")

    # 2. FS chain with a milestone at each end.
    s = _sched([("M0", 0), ("A", 5), ("B", 3), ("M1", 0)],
               [("M0", "A", "FS", 0), ("A", "B", "FS", 2), ("B", "M1", "FS", 0)])
    r = cpm(s)
    b = _by_id(r)
    check((b["A"]["es"], b["A"]["ef"]) == (0, 5), "A dates")
    check((b["B"]["es"], b["B"]["ef"]) == (7, 10), "FS+2 lag")
    check(b["M1"]["es"] == 10 and b["M1"]["finish"] == "2020-02-14", "finish milestone sits on last work day")
    check(b["M0"]["start"] == "2020-02-03", "start milestone on day 0")
    check(r["finish"] == 10 and r["finish_date"] == "2020-02-14", "project finish")
    check(r["critical_path"] == ["M0", "A", "B", "M1"], "all critical in a chain")

    # 3. Parallel paths, float, SS / FF / SF.
    s = _sched([("A", 10), ("B", 4), ("C", 6), ("D", 5), ("E", 2)],
               [("A", "B", "SS", 3), ("A", "C", "FF", 2), ("B", "D", "FS", 0), ("C", "E", "SF", 4)])
    b = _by_id(cpm(s))
    check((b["B"]["es"], b["B"]["ef"]) == (3, 7), "SS+3")
    check((b["C"]["es"], b["C"]["ef"]) == (6, 12), "FF+2 pushes finish to 12")
    check((b["D"]["es"], b["D"]["ef"]) == (7, 12), "FS after SS")
    check((b["E"]["es"], b["E"]["ef"]) == (8, 10), "SF+4: EF >= ES(C)+4 = 10")
    # finish = 12. Backward: D LF 12 -> TF 0; B LF = LS(D)=7 -> TF 0; C LF 12 -> TF 0 (FF), E LF 12 -> TF 2
    # A: via SS to B: LS(A) <= LS(B)-3 = 0 -> LF(A) <= 10; via FF to C: LF(A) <= 12-2 = 10. TF(A)=0.
    check(b["E"]["total_float"] == 2, "E float 2")
    check(b["A"]["total_float"] == 0 and b["C"]["total_float"] == 0 and b["D"]["total_float"] == 0, "critical floats")
    # SF backward: C.LS <= E.LF - 4 = 8 -> C.LF <= 14, FF/open end gives 12, so still 12.

    # 4. Negative lag (lead).
    s = _sched([("A", 10), ("B", 5)], [("A", "B", "FS", -3)])
    b = _by_id(cpm(s))
    check(b["B"]["es"] == 7 and b["B"]["ef"] == 12, "FS-3 lead")

    # 5. Progress at a data date. Data date 2020-02-10 (day 5).
    s = _sched([("A", 5, {"actual_start": "2020-02-03", "actual_finish": "2020-02-07"}),
                ("B", 6, {"actual_start": "2020-02-06", "remaining": 4}),
                ("C", 3), ("D", 2)],
               [("A", "B", "FS", 0), ("B", "C", "FS", 0), ("A", "D", "FS", 0)], data_date="2020-02-10")
    r = cpm(s)
    b = _by_id(r)
    check(b["A"]["status"] == "complete" and b["A"]["total_float"] is None and not b["A"]["critical"], "complete")
    check((b["B"]["es"], b["B"]["ef"]) == (3, 9), "in progress: actual start kept, EF = DD + remaining")
    check((b["C"]["es"], b["C"]["ef"]) == (9, 12), "successor of in-progress")
    check(b["D"]["es"] == 5 and b["D"]["total_float"] == 5, "not started cannot start before data date")
    s = _sched([("M0", 0, {"actual_start": "2020-02-03", "actual_finish": "2020-02-03"}), ("A", 4)],
               [("M0", "A", "FS", 0)], data_date="2020-02-05")
    b = _by_id(cpm(s))
    check(b["M0"]["start"] == "2020-02-03" and b["A"]["es"] == 2, "completed milestone keeps its date; open work waits for data date")

    # 6. Holidays move dates and calendar-day delay counts the weekend/holiday gap.
    s = _sched([("A", 11), ("M", 0)], [("A", "M", "FS", 0)], holidays=["2020-02-17"])
    r = cpm(s)
    check(r["finish_date"] == "2020-02-18", "holiday extends finish")
    t = tia(s, {"activities": [{"id": "F-1", "name": "wait", "duration": 1}],
                "relationships": [{"pred": "A", "succ": "F-1", "type": "FS", "lag": 0},
                                  {"pred": "F-1", "succ": "M", "type": "FS", "lag": 0}]})
    check(t["delay_workdays"] == 1 and t["delay_calendar_days"] == 1 and t["fragnet_critical"], "1-day tia")
    s2 = _sched([("A", 9), ("M", 0)], [("A", "M", "FS", 0)])     # A ends Fri 2020-02-13
    t = tia(s2, {"activities": [{"id": "F-1", "duration": 1}],
                 "relationships": [{"pred": "A", "succ": "F-1", "type": "FS", "lag": 0},
                                   {"pred": "F-1", "succ": "M", "type": "FS", "lag": 0}]})
    check(t["before_finish"] == "2020-02-13" and t["after_finish"] == "2020-02-14", "Thu -> Fri")
    s3 = _sched([("A", 10), ("M", 0)], [("A", "M", "FS", 0)])    # ends Fri 2020-02-14
    t = tia(s3, {"activities": [{"id": "F-1", "duration": 1}],
                 "relationships": [{"pred": "A", "succ": "F-1", "type": "FS", "lag": 0},
                                   {"pred": "F-1", "succ": "M", "type": "FS", "lag": 0}]})
    check(t["delay_workdays"] == 1 and t["delay_calendar_days"] == 3, "Fri -> Mon is 3 calendar days")

    # 7. Float absorbs a fragnet, partial consumption, and the driving path.
    s = _sched([("S", 0), ("A", 20), ("B", 5), ("C", 8), ("M", 0)],
               [("S", "A", "FS", 0), ("S", "B", "FS", 0), ("A", "M", "FS", 0), ("B", "C", "FS", 0), ("C", "M", "FS", 0)])
    b = _by_id(cpm(s))
    check(b["C"]["total_float"] == 7, "C float 7")
    t = tia(s, {"activities": [{"id": "F-X", "duration": 5}],
                "relationships": [{"pred": "B", "succ": "F-X", "type": "FS", "lag": 0},
                                  {"pred": "F-X", "succ": "C", "type": "FS", "lag": 0}]})
    check(t["delay_workdays"] == 0 and not t["fragnet_critical"] and t["fragnet_float"]["F-X"] == 2, "absorbed")
    t = tia(s, {"activities": [{"id": "F-X", "duration": 10}],
                "relationships": [{"pred": "B", "succ": "F-X", "type": "FS", "lag": 0},
                                  {"pred": "F-X", "succ": "C", "type": "FS", "lag": 0}]})
    check(t["delay_workdays"] == 3 and t["fragnet_critical"], "partial: 10 - 7 float = 3")
    check(t["driving_path"] == ["S", "B", "F-X", "C", "M"], "driving path through fragnet")

    # 8. SNET constraint and a loop.
    s = _sched([("A", 3), ("B", 2, {"constraint": {"type": "SNET", "date": "2020-02-12"}})], [("A", "B", "FS", 0)])
    b = _by_id(cpm(s))
    check(b["B"]["es"] == 7, "SNET holds start to Wed 2020-02-12")
    s = _sched([("A", 1), ("B", 1)], [("A", "B", "FS", 0), ("B", "A", "FS", 0)])
    try:
        cpm(s)
        check(False, "loop not caught")
    except ScheduleError:
        check(True, "loop caught")

    # 9. FNLT gives negative float (EF 10, must finish by day 7 so LF 8).
    s = _sched([("A", 10, {"constraint": {"type": "FNLT", "date": "2020-02-12"}})], [])
    b = _by_id(cpm(s))
    check(b["A"]["total_float"] == -2 and b["A"]["critical"], "FNLT negative float")

    # 10. Bad fragnet ids are refused.
    try:
        tia(_sched([("A", 1)], []), {"activities": [{"id": "X1", "duration": 1}], "relationships": []})
        check(False, "non F- id accepted")
    except ScheduleError:
        check(True, "F- prefix enforced")

    print(f"cpm_ref self-tests: {n} checks passed")


if __name__ == "__main__":
    _selftest()
