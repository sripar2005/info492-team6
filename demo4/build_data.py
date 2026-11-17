#!/usr/bin/env python3
"""Build all Demo 4 synthetic test data. Run from the repo root:  python3 demo4/build_data.py

Everything written here is SYNTHETIC (made up for INFO 492 C coursework). Deterministic: the same inputs
always give byte-identical JSON, CSV, XER and XML (the XLSX and PDF files carry fixed timestamps too).

Writes to demo4/data/:
  schedule.json             the schedule in the spec's model (docs/demo4-spec.md section 1)
  schedule.xer              Primavera P6 XER export of the same schedule
  schedule.xml              MS Project MSPDI ("Save as XML") export
  schedule.csv / .xlsx      table export with a Predecessors column ("A1010FS+2, A1020")
  schedule_nologic.csv      the same table without predecessors (critical path not verifiable)
  schedule.pdf              printed Gantt-style table (id, name, duration, start, finish; no logic)
  contract_b.md / .pdf      second synthetic GC/CM contract with different numbers
  contract_c.md / .pdf      third synthetic contract, HELD OUT (written after the A/B evaluation; see DATA_NOTE)
  contract_terms_key.json   expected contract terms for contracts A, B and C, with verified quotes
  cases.json                15 change proposals (CP-0401..CP-0415) plus 5 held-out ones (CP-0501..CP-0505)
                            with a time section and fragnet_truth
  answer_key.json           expected delay, extension, compensability and cost per case, from cpm_ref.tia
  pdfs/*.pdf                change-proposal PDFs for 4 dev cases
  DATA_NOTE.md              what is synthetic, how it was built, the split rule, limits

Every expected value is computed (cpm_ref for time, the contract rates for money); nothing is hand-typed.
The script re-reads every export and checks counts, relationships and the CPM finish before it exits.
"""
import copy
import csv
import io
import json
import random
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(ROOT / "demo2"))

import cpm_ref as C  # noqa: E402
import schedule_src as S  # noqa: E402
from contract_b_text import CONTRACT_B  # noqa: E402
from contract_c_text import CONTRACT_C  # noqa: E402
from deadlines import notice_due  # noqa: E402  (Demo 2's contract A Section 6.2 + 1.4 date code)

SEED = 20200601                 # fixes the dev/test split before anything is computed
SGC_DAILY_A = 3185              # contract A Section 5.2
FEE_A = 0.05                    # contract A Section 6.5.3
BURDEN_A = 0.32                 # contract A Section 5.4
FIXED_TS = datetime(2020, 6, 5, 9, 0, 0)   # stamped into XLSX/PDF metadata so output is stable

NOTICE_RULE = {"RFI response": "6.2(a)", "ASI": "6.2(a)", "Submittal return": "6.2(a)",
               "Owner direction": "6.2(b)", "Architect direction": "6.2(b)",
               "Concealed condition": "6.2(c)", "Other event": "6.2(d)"}


def r2(x):
    return round(x + 1e-9, 2)


def dump_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ============================================================================ schedule
PRED_RE = re.compile(r"^([A-Z]\d+)(FS|SS|FF|SF)?([+-]\d+)?$")


def parse_pred(tok):
    m = PRED_RE.match(tok.strip())
    if not m:
        raise ValueError(f"bad predecessor token {tok!r}")
    return m.group(1), m.group(2) or "FS", int(m.group(3) or 0)


def fmt_pred(r):
    if r["type"] == "FS" and r["lag"] == 0:
        return r["pred"]
    return r["pred"] + r["type"] + (f"{r['lag']:+d}" if r["lag"] else "")


WBS_NAME = dict(S.WBS)


def build_schedule():
    """As-planned network -> as-built progress to the data date -> updated schedule model."""
    acts, rels = [], []
    for aid, name, wbs, dur, preds in S.ACTIVITIES:
        acts.append({"id": aid, "name": name, "duration": dur, "wbs": WBS_NAME[wbs],
                     "actual_start": None, "actual_finish": None, "remaining": None,
                     "constraint": S.CONSTRAINTS.get(aid)})
        for p in preds:
            pid, t, lag = parse_pred(p)
            rels.append({"pred": pid, "succ": aid, "type": t, "lag": lag})
    base = {"name": S.PROJECT_NAME, "data_date": S.START, "start": S.START,
            "calendar": {"workdays": [1, 2, 3, 4, 5], "holidays": list(S.HOLIDAYS)},
            "activities": acts, "relationships": rels}
    planned = C.cpm(base)

    # as-built: the same network with the slipped activities running longer
    asb = copy.deepcopy(base)
    for a in asb["activities"]:
        a["duration"] += S.SLIPS.get(a["id"], 0)
    built = C.cpm(asb)
    cal = built["_cal"]
    dd = cal.day_on_or_after(S.DATA_DATE)
    bx = {x["id"]: x for x in built["activities"]}
    upd = copy.deepcopy(base)
    upd["data_date"] = S.DATA_DATE
    for a in upd["activities"]:
        x = bx[a["id"]]
        if a["duration"] == 0:
            if x["es"] < dd:
                a["actual_start"] = a["actual_finish"] = x["start"]
                a["remaining"] = 0
        elif x["ef"] <= dd:
            a["actual_start"], a["actual_finish"], a["remaining"] = cal.iso(x["es"]), cal.iso(x["ef"] - 1), 0
        elif x["es"] < dd:
            a["actual_start"], a["remaining"] = cal.iso(x["es"]), x["ef"] - dd
    upd["source"] = {"format": "json", "file": "schedule.json", "has_logic": True}
    return upd, planned


def contract_completion_date():
    return (date.fromisoformat(S.START) + timedelta(days=S.CONTRACT_DAYS)).isoformat()


# ---------------------------------------------------------------------------- XER
def excel_serial(d):
    return (d - date(1899, 12, 30)).days


def xer_clndr_data(holidays):
    days = []
    for p6day in range(1, 8):            # P6: 1 = Sunday ... 7 = Saturday
        if p6day in (1, 7):
            days.append(f"(0||{p6day}()())")
        else:
            days.append(f"(0||{p6day}()((0||0(s|08:00|f|12:00)())(0||1(s|13:00|f|17:00)())))")
    exc = "".join(f"(0||{i}(d|{excel_serial(date.fromisoformat(h))})())" for i, h in enumerate(holidays))
    return ("(0||CalendarData()((0||DaysOfWeek()(" + "".join(days) + "))(0||VIEW(ShowTotal|Y)())"
            "(0||Exceptions()(" + exc + "))))")


def p6dt(iso, end=False):
    return f"{iso} {'17:00' if end else '08:00'}" if iso else ""


P6_CSTR = {"SNET": "CS_MSOA", "MSO": "CS_MSO", "MFO": "CS_MEO", "FNLT": "CS_MEOB"}
P6_CSTR_BACK = {v: k for k, v in P6_CSTR.items()}


def write_xer(sch, res, planned):
    cal = res["_cal"]
    rx = {x["id"]: x for x in res["activities"]}
    px = {x["id"]: x for x in planned["activities"]}
    proj_id, clndr_id, root_wbs = 4492, 701, 3100
    wbs_ids = {name: root_wbs + 1 + i for i, (_, name) in enumerate(S.WBS)}
    task_ids = {a["id"]: 50000 + i for i, a in enumerate(sch["activities"])}
    out = []

    def table(name, fields, rows):
        out.append("%T\t" + name)
        out.append("%F\t" + "\t".join(fields))
        for r in rows:
            out.append("%R\t" + "\t".join("" if v is None else str(v) for v in r))

    out.append("ERMHDR\t19.12\t2020-06-05\tProject\tadmin\tClauseStream synthetic\tdbxDatabaseNoName\tProject Management\tUSD")
    table("CALENDAR", ["clndr_id", "default_flag", "clndr_name", "proj_id", "base_clndr_id", "last_chng_date",
                       "clndr_type", "day_hr_cnt", "week_hr_cnt", "month_hr_cnt", "year_hr_cnt", "rsrc_private", "clndr_data"],
          [[clndr_id, "N", "5-Day 8-Hour with WA legal holidays", proj_id, "", "2020-01-15 00:00", "CA_Project",
            8, 40, 172, 2000, "N", xer_clndr_data(sch["calendar"]["holidays"])]])
    table("PROJECT", ["proj_id", "fy_start_month_num", "proj_short_name", "clndr_id", "plan_start_date", "plan_end_date",
                      "scd_end_date", "last_recalc_date", "next_data_date", "def_duration_type", "def_task_type", "proj_url"],
          [[proj_id, 1, "ESM-2020", clndr_id, p6dt(sch["start"]), p6dt(contract_completion_date(), True),
            p6dt(res["finish_date"], True), p6dt(sch["data_date"]), p6dt(sch["data_date"]), "DT_FixedDUR2", "TT_Task", ""]])
    wrows = [[root_wbs, proj_id, 1, 0, "Y", "N", "WS_Open", "ESM-2020", S.PROJECT_NAME, ""]]
    for i, (code, name) in enumerate(S.WBS):
        wrows.append([wbs_ids[name], proj_id, 1, (i + 1) * 10, "N", "N", "WS_Open", code, name, root_wbs])
    table("PROJWBS", ["wbs_id", "proj_id", "obs_id", "seq_num", "proj_node_flag", "sum_data_flag", "status_code",
                      "wbs_short_name", "wbs_name", "parent_wbs_id"], wrows)
    trows = []
    for a in sch["activities"]:
        x, p = rx[a["id"]], px[a["id"]]
        st = x["status"]
        mile = a["duration"] == 0
        ttype = ("TT_Mile" if a["id"] == "A1000" else "TT_FinMile") if mile else "TT_Task"
        status = {"complete": "TK_Complete", "active": "TK_Active", "open": "TK_NotStart"}[st]
        rem = 0 if st == "complete" else (a["remaining"] if st == "active" else a["duration"])
        pct = 100 if st == "complete" else (round(100 * (a["duration"] - rem) / a["duration"]) if st == "active" else 0)
        c = a.get("constraint")
        ls = cal.iso(x["ls"]) if x["ls"] is not None else ""
        lf = cal.iso(max(x["lf"] - 1, 0)) if x["lf"] is not None else ""
        trows.append([
            task_ids[a["id"]], proj_id, wbs_ids[a["wbs"]], clndr_id, pct, ttype, "DT_FixedDUR2", status,
            a["id"], a["name"],
            "" if x["total_float"] is None else x["total_float"] * 8,
            rem * 8, a["duration"] * 8,
            p6dt(a["actual_start"]) if a["actual_start"] else "",
            p6dt(a["actual_finish"], True) if a["actual_finish"] else "",
            p6dt(x["start"], end=mile and ttype == "TT_FinMile"), p6dt(x["finish"], True),
            p6dt(ls, end=mile and ttype == "TT_FinMile") if ls else "", p6dt(lf, True) if lf else "",
            p6dt(p["start"], end=mile and ttype == "TT_FinMile"), p6dt(p["finish"], True),
            p6dt(sch["data_date"]) if st == "active" else "",
            P6_CSTR[c["type"]] if c else "", p6dt(c["date"]) if c else "",
            "Y" if x["critical"] else "N",
        ])
    table("TASK", ["task_id", "proj_id", "wbs_id", "clndr_id", "phys_complete_pct", "task_type", "duration_type",
                   "status_code", "task_code", "task_name", "total_float_hr_cnt", "remain_drtn_hr_cnt",
                   "target_drtn_hr_cnt", "act_start_date", "act_end_date", "early_start_date", "early_end_date",
                   "late_start_date", "late_end_date", "target_start_date", "target_end_date", "restart_date",
                   "cstr_type", "cstr_date", "driving_path_flag"], trows)
    prows = []
    for i, r in enumerate(sch["relationships"]):
        prows.append([80000 + i, task_ids[r["succ"]], task_ids[r["pred"]], proj_id, proj_id, "PR_" + r["type"], r["lag"] * 8])
    table("TASKPRED", ["task_pred_id", "task_id", "pred_task_id", "proj_id", "pred_proj_id", "pred_type", "lag_hr_cnt"], prows)
    out.append("%E")
    (DATA / "schedule.xer").write_bytes(("\r\n".join(out) + "\r\n").encode("cp1252"))


def read_xer(path):
    """Quick independent re-parse of the XER into the schedule model (verification only)."""
    tables, cur, fields = {}, None, None
    for line in path.read_bytes().decode("cp1252").splitlines():
        parts = line.split("\t")
        if parts[0] == "%T":
            cur = parts[1]
            tables[cur] = []
        elif parts[0] == "%F":
            fields = parts[1:]
        elif parts[0] == "%R":
            tables[cur].append(dict(zip(fields, parts[1:])))
    cdata = tables["CALENDAR"][0]["clndr_data"]
    hol = sorted((date(1899, 12, 30) + timedelta(days=int(s))).isoformat() for s in re.findall(r"\(d\|(\d+)\)", cdata))
    wbs = {w["wbs_id"]: w["wbs_name"] for w in tables["PROJWBS"]}
    code = {t["task_id"]: t["task_code"] for t in tables["TASK"]}
    acts = []
    for t in tables["TASK"]:
        st = t["status_code"]
        c = None
        if t["cstr_type"]:
            c = {"type": P6_CSTR_BACK[t["cstr_type"]], "date": t["cstr_date"][:10]}
        acts.append({"id": t["task_code"], "name": t["task_name"], "duration": int(float(t["target_drtn_hr_cnt"])) // 8,
                     "wbs": wbs[t["wbs_id"]],
                     "actual_start": t["act_start_date"][:10] or None, "actual_finish": t["act_end_date"][:10] or None,
                     "remaining": int(float(t["remain_drtn_hr_cnt"])) // 8 if st != "TK_NotStart" else None,
                     "constraint": c})
    rels = [{"pred": code[p["pred_task_id"]], "succ": code[p["task_id"]], "type": p["pred_type"][3:],
             "lag": int(float(p["lag_hr_cnt"])) // 8} for p in tables["TASKPRED"]]
    pr = tables["PROJECT"][0]
    return {"start": pr["plan_start_date"][:10], "data_date": pr["last_recalc_date"][:10],
            "calendar": {"workdays": [1, 2, 3, 4, 5], "holidays": hol}, "activities": acts, "relationships": rels,
            "_tables": {k: len(v) for k, v in tables.items()}}


# ---------------------------------------------------------------------------- MSPDI XML
MSP_TYPE = {"FF": 0, "FS": 1, "SF": 2, "SS": 3}
MSP_TYPE_BACK = {v: k for k, v in MSP_TYPE.items()}
MSP_CSTR = {"MSO": 2, "MFO": 3, "SNET": 4, "FNLT": 7}
MSP_CSTR_BACK = {v: k for k, v in MSP_CSTR.items()}
TEXT1 = 188743731
HOLIDAY_NAMES = {"01-01": "New Year's Day", "12-31": "New Year's Day (observed)", "05-25": "Memorial Day",
                 "05-31": "Memorial Day", "07-03": "Independence Day (observed)", "07-05": "Independence Day (observed)",
                 "09-07": "Labor Day", "09-06": "Labor Day", "11-11": "Veterans Day", "12-25": "Christmas Day",
                 "12-24": "Christmas Day (observed)", "01-20": "Martin Luther King Jr. Day", "01-18": "Martin Luther King Jr. Day",
                 "02-17": "Presidents' Day", "02-15": "Presidents' Day", "11-26": "Thanksgiving", "11-27": "Day after Thanksgiving",
                 "11-25": "Thanksgiving"}


def holiday_name(iso):
    d = iso[5:]
    if iso == "2021-11-26":
        return "Day after Thanksgiving"
    return HOLIDAY_NAMES.get(d, "Holiday")


def msp_dur(days):
    return f"PT{days * 8}H0M0S"


def write_mspdi(sch, res, planned):
    rx = {x["id"]: x for x in res["activities"]}
    px = {x["id"]: x for x in planned["activities"]}
    L = []
    w = L.append
    w('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    w('<Project xmlns="http://schemas.microsoft.com/project">')
    w("  <SaveVersion>14</SaveVersion>")
    w("  <Name>schedule.xml</Name>")
    w(f"  <Title>{escape(S.PROJECT_NAME)}</Title>")
    w("  <ScheduleFromStart>1</ScheduleFromStart>")
    w(f"  <StartDate>{sch['start']}T08:00:00</StartDate>")
    w(f"  <FinishDate>{res['finish_date']}T17:00:00</FinishDate>")
    w("  <CalendarUID>1</CalendarUID>")
    w("  <DefaultStartTime>08:00:00</DefaultStartTime>")
    w("  <DefaultFinishTime>17:00:00</DefaultFinishTime>")
    w("  <MinutesPerDay>480</MinutesPerDay>")
    w("  <MinutesPerWeek>2400</MinutesPerWeek>")
    w("  <DaysPerMonth>20</DaysPerMonth>")
    w(f"  <StatusDate>{sch['data_date']}T08:00:00</StatusDate>")
    w(f"  <CurrentDate>{sch['data_date']}T08:00:00</CurrentDate>")
    w("  <ExtendedAttributes>")
    w(f"    <ExtendedAttribute><FieldID>{TEXT1}</FieldID><FieldName>Text1</FieldName><Alias>Activity ID</Alias></ExtendedAttribute>")
    w("  </ExtendedAttributes>")
    w("  <Calendars>")
    w("    <Calendar>")
    w("      <UID>1</UID>")
    w("      <Name>Standard (WA legal holidays)</Name>")
    w("      <IsBaseCalendar>1</IsBaseCalendar>")
    w("      <BaseCalendarUID>-1</BaseCalendarUID>")
    w("      <WeekDays>")
    for dt in range(1, 8):            # MSP: 1 = Sunday ... 7 = Saturday
        if dt in (1, 7):
            w(f"        <WeekDay><DayType>{dt}</DayType><DayWorking>0</DayWorking></WeekDay>")
        else:
            w(f"        <WeekDay><DayType>{dt}</DayType><DayWorking>1</DayWorking><WorkingTimes>"
              "<WorkingTime><FromTime>08:00:00</FromTime><ToTime>12:00:00</ToTime></WorkingTime>"
              "<WorkingTime><FromTime>13:00:00</FromTime><ToTime>17:00:00</ToTime></WorkingTime></WorkingTimes></WeekDay>")
    for h in sch["calendar"]["holidays"]:
        w(f"        <WeekDay><DayType>0</DayType><DayWorking>0</DayWorking><TimePeriod><FromDate>{h}T00:00:00</FromDate>"
          f"<ToDate>{h}T23:59:00</ToDate></TimePeriod></WeekDay>")
    w("      </WeekDays>")
    w("      <Exceptions>")
    for h in sch["calendar"]["holidays"]:
        w(f"        <Exception><EnteredByOccurrences>0</EnteredByOccurrences><TimePeriod><FromDate>{h}T00:00:00</FromDate>"
          f"<ToDate>{h}T23:59:00</ToDate></TimePeriod><Occurrences>1</Occurrences><Name>{escape(holiday_name(h))}</Name>"
          "<Type>1</Type><DayWorking>0</DayWorking></Exception>")
    w("      </Exceptions>")
    w("    </Calendar>")
    w("  </Calendars>")
    w("  <Tasks>")
    preds_of = {}
    for r in sch["relationships"]:
        preds_of.setdefault(r["succ"], []).append(r)
    by_wbs = {}
    for a in sch["activities"]:
        by_wbs.setdefault(a["wbs"], []).append(a)

    def task(uid, row, name, level, outline, start, finish, dur_days, summary, extra=()):
        w("    <Task>")
        w(f"      <UID>{uid}</UID>")
        w(f"      <ID>{row}</ID>")
        w(f"      <Name>{escape(name)}</Name>")
        w("      <Type>1</Type>")
        w(f"      <WBS>{outline}</WBS>")
        w(f"      <OutlineNumber>{outline}</OutlineNumber>")
        w(f"      <OutlineLevel>{level}</OutlineLevel>")
        w(f"      <Start>{start}</Start>")
        w(f"      <Finish>{finish}</Finish>")
        w(f"      <Duration>{msp_dur(dur_days)}</Duration>")
        w("      <DurationFormat>7</DurationFormat>")
        w(f"      <Summary>{1 if summary else 0}</Summary>")
        for e in extra:
            w("      " + e)
        w("    </Task>")

    row = 0
    task(0, row, S.PROJECT_NAME, 0, "0", f"{sch['start']}T08:00:00", f"{res['finish_date']}T17:00:00", res["finish"], True,
         ["<Milestone>0</Milestone>"])
    for wi, (code, wname) in enumerate(S.WBS, start=1):
        kids = by_wbs.get(wname, [])
        row += 1
        st = min(rx[a["id"]]["start"] for a in kids)
        fi = max(rx[a["id"]]["finish"] for a in kids)
        task(wi, row, wname, 1, str(wi), f"{st}T08:00:00", f"{fi}T17:00:00",
             C.Calendar(sch["start"], holidays=sch["calendar"]["holidays"]).day_on_or_after(fi) -
             C.Calendar(sch["start"], holidays=sch["calendar"]["holidays"]).day_on_or_after(st) + 1, True,
             ["<Milestone>0</Milestone>"])
        for ki, a in enumerate(kids, start=1):
            row += 1
            x, p = rx[a["id"]], px[a["id"]]
            mile = a["duration"] == 0
            rem = 0 if x["status"] == "complete" else (a["remaining"] if x["status"] == "active" else a["duration"])
            pct = 100 if x["status"] == "complete" else (round(100 * (a["duration"] - rem) / a["duration"]) if x["status"] == "active" else 0)
            st_t = "17:00:00" if (mile and a["id"] != "A1000") else "08:00:00"
            extra = [f"<Milestone>{1 if mile else 0}</Milestone>",
                     f"<Critical>{1 if x['critical'] else 0}</Critical>",
                     f"<PercentComplete>{pct}</PercentComplete>",
                     f"<RemainingDuration>{msp_dur(rem)}</RemainingDuration>"]
            if a["actual_start"]:
                extra.append(f"<ActualStart>{a['actual_start']}T08:00:00</ActualStart>")
            if a["actual_finish"]:
                extra.append(f"<ActualFinish>{a['actual_finish']}T{'08:00:00' if a['id'] == 'A1000' else '17:00:00'}</ActualFinish>")
            if x["total_float"] is not None:
                extra.append(f"<TotalSlack>{x['total_float'] * 4800}</TotalSlack>")
            c = a.get("constraint")
            extra.append(f"<ConstraintType>{MSP_CSTR[c['type']] if c else 0}</ConstraintType>")
            if c:
                extra.append(f"<ConstraintDate>{c['date']}T08:00:00</ConstraintDate>")
            for r in preds_of.get(a["id"], []):
                extra.append(f"<PredecessorLink><PredecessorUID>{int(r['pred'][1:])}</PredecessorUID><Type>{MSP_TYPE[r['type']]}</Type>"
                             f"<CrossProject>0</CrossProject><LinkLag>{r['lag'] * 4800}</LinkLag><LagFormat>7</LagFormat></PredecessorLink>")
            extra.append(f"<ExtendedAttribute><FieldID>{TEXT1}</FieldID><Value>{a['id']}</Value></ExtendedAttribute>")
            extra.append(f"<Baseline><Number>0</Number><Start>{p['start']}T{st_t}</Start><Finish>{p['finish']}T17:00:00</Finish>"
                         f"<Duration>{msp_dur(a['duration'])}</Duration></Baseline>")
            task(int(a["id"][1:]), row, a["name"], 2, f"{wi}.{ki}", f"{x['start']}T{st_t}", f"{x['finish']}T17:00:00",
                 a["duration"], False, extra)
    w("  </Tasks>")
    w("</Project>")
    (DATA / "schedule.xml").write_text("\n".join(L) + "\n", encoding="utf-8")


def read_mspdi(path):
    ns = {"p": "http://schemas.microsoft.com/project"}
    root = ET.parse(path).getroot()
    hol = sorted({e.find("p:TimePeriod/p:FromDate", ns).text[:10] for e in root.findall(".//p:Calendar/p:Exceptions/p:Exception", ns)})
    tasks = [t for t in root.findall("p:Tasks/p:Task", ns) if t.findtext("p:Summary", "0", ns) == "0"]
    uid2id = {}
    for t in tasks:
        aid = [e.findtext("p:Value", None, ns) for e in t.findall("p:ExtendedAttribute", ns)
               if e.findtext("p:FieldID", None, ns) == str(TEXT1)][0]
        uid2id[t.findtext("p:UID", None, ns)] = aid

    def hours(s):
        m = re.match(r"PT(\d+)H(\d+)M(\d+)S", s)
        return int(m.group(1))

    acts, rels = [], []
    for t in tasks:
        aid = uid2id[t.findtext("p:UID", None, ns)]
        pct = int(t.findtext("p:PercentComplete", "0", ns))
        ct = int(t.findtext("p:ConstraintType", "0", ns))
        acts.append({"id": aid, "name": t.findtext("p:Name", None, ns), "duration": hours(t.findtext("p:Duration", None, ns)) // 8,
                     "actual_start": (t.findtext("p:ActualStart", "", ns) or "")[:10] or None,
                     "actual_finish": (t.findtext("p:ActualFinish", "", ns) or "")[:10] or None,
                     "remaining": hours(t.findtext("p:RemainingDuration", None, ns)) // 8 if pct > 0 else None,
                     "constraint": {"type": MSP_CSTR_BACK[ct], "date": t.findtext("p:ConstraintDate", None, ns)[:10]} if ct in MSP_CSTR_BACK else None})
        for pl in t.findall("p:PredecessorLink", ns):
            rels.append({"pred": uid2id[pl.findtext("p:PredecessorUID", None, ns)], "succ": aid,
                         "type": MSP_TYPE_BACK[int(pl.findtext("p:Type", None, ns))],
                         "lag": int(pl.findtext("p:LinkLag", "0", ns)) // 4800})
    return {"start": root.findtext("p:StartDate", None, ns)[:10], "data_date": root.findtext("p:StatusDate", None, ns)[:10],
            "calendar": {"workdays": [1, 2, 3, 4, 5], "holidays": hol}, "activities": acts, "relationships": rels,
            "_summary_tasks": len(root.findall("p:Tasks/p:Task", ns)) - len(tasks)}


# ---------------------------------------------------------------------------- CSV / XLSX
CSV_COLS = ["Activity ID", "Activity Name", "WBS", "Original Duration", "Start", "Finish", "Predecessors",
            "Actual Start", "Actual Finish", "Remaining Duration"]


def table_rows(sch, res):
    rx = {x["id"]: x for x in res["activities"]}
    preds_of = {}
    for r in sch["relationships"]:
        preds_of.setdefault(r["succ"], []).append(fmt_pred(r))
    rows = []
    for a in sch["activities"]:
        x = rx[a["id"]]
        rows.append([a["id"], a["name"], a["wbs"], a["duration"], x["start"], x["finish"], ", ".join(preds_of.get(a["id"], [])),
                     a["actual_start"] or "", a["actual_finish"] or "",
                     "" if a["remaining"] is None else a["remaining"]])
    return rows


def write_tables(sch, res):
    rows = table_rows(sch, res)
    with open(DATA / "schedule.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLS)
        wr.writerows(rows)
    keep = [i for i, c in enumerate(CSV_COLS) if c != "Predecessors"]
    with open(DATA / "schedule_nologic.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow([CSV_COLS[i] for i in keep])
        wr.writerows([[r[i] for i in keep] for r in rows])

    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule"
    ws.append(CSV_COLS)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        r = list(r)
        for i in (4, 5, 7, 8):
            if r[i]:
                r[i] = date.fromisoformat(r[i])
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for i in (4, 5, 7, 8):
            if row[i].value:
                row[i].number_format = "yyyy-mm-dd"
    for col, wdt in zip("ABCDEFGHIJ", (10, 52, 26, 10, 12, 12, 40, 12, 12, 10)):
        ws.column_dimensions[col].width = wdt
    ws.freeze_panes = "A2"
    wb.properties.creator = "ClauseStream synthetic data"
    wb.properties.created = wb.properties.modified = FIXED_TS
    buf = io.BytesIO()
    wb.save(buf)
    _stable_zip(buf.getvalue(), DATA / "schedule.xlsx")


def _stable_zip(data, path):
    """Rewrite an XLSX with fixed entry times and document dates so rebuilds are byte-identical."""
    import zipfile
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    stamp = FIXED_TS.strftime("%Y-%m-%dT%H:%M:%SZ")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            body = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                body = re.sub(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*", lambda m: m.group(1) + stamp.encode(), body)
            zi = zipfile.ZipInfo(info.filename, date_time=FIXED_TS.timetuple()[:6])
            zi.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(zi, body)
    path.write_bytes(out.getvalue())


def rows_to_model(header, rows, start, data_date, holidays):
    ix = {h: i for i, h in enumerate(header)}
    acts, rels = [], []
    for r in rows:
        acts.append({"id": r[ix["Activity ID"]], "name": r[ix["Activity Name"]], "duration": int(r[ix["Original Duration"]]),
                     "wbs": r[ix["WBS"]], "actual_start": r[ix["Actual Start"]] or None,
                     "actual_finish": r[ix["Actual Finish"]] or None,
                     "remaining": None if r[ix["Remaining Duration"]] in ("", None) else int(r[ix["Remaining Duration"]]),
                     "constraint": None})
        if "Predecessors" in ix and r[ix["Predecessors"]]:
            for tok in str(r[ix["Predecessors"]]).split(","):
                p, t, lag = parse_pred(tok)
                rels.append({"pred": p, "succ": r[ix["Activity ID"]], "type": t, "lag": lag})
    return {"start": start, "data_date": data_date, "calendar": {"workdays": [1, 2, 3, 4, 5], "holidays": holidays},
            "activities": acts, "relationships": rels}


# ---------------------------------------------------------------------------- PDF (printed Gantt)
def write_schedule_pdf(sch, res):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.pdfgen import canvas as rl_canvas

    rx = {x["id"]: x for x in res["activities"]}
    W, H = landscape(letter)
    c = rl_canvas.Canvas(str(DATA / "schedule.pdf"), pagesize=(W, H), invariant=1)
    c.setTitle("Example School Modernization - June 2020 schedule update (synthetic)")
    c.setAuthor("ClauseStream synthetic data")
    t0, t1 = date(2020, 2, 1), date(2021, 8, 1)
    gx0, gx1 = 455, W - 24

    def gx(d):
        return gx0 + (gx1 - gx0) * (d - t0).days / (t1 - t0).days

    lines = []
    for code, wname in S.WBS:
        kids = sorted((a for a in sch["activities"] if a["wbs"] == wname), key=lambda a: (rx[a["id"]]["es"], a["id"]))
        lines.append(("wbs", wname))
        lines += [("act", a) for a in kids]
    row_h, top = 10.6, H - 92
    per_page = int((top - 40) / row_h)
    pages, i = [], 0
    while i < len(lines):
        chunk = lines[i:i + per_page]
        if len(chunk) == per_page and chunk[-1][0] == "wbs":    # keep a WBS header with its first activity
            chunk = chunk[:-1]
        pages.append(chunk)
        i += len(chunk)
    for pn, chunk in enumerate(pages, start=1):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(24, H - 30, "Example School Modernization and Addition - Schedule Update (SYNTHETIC TEST DOCUMENT)")
        c.setFont("Helvetica", 8)
        c.drawString(24, H - 44, f"Data date {sch['data_date']}    Notice to Proceed {sch['start']}    "
                                 f"Forecast Substantial Completion {res['finish_date']}    Durations in working days    Page {pn} of {len(pages)}")
        c.drawString(24, H - 55, "Printed layout only. Relationships are not shown on this report.")
        hy = H - 74
        c.setFont("Helvetica-Bold", 7.5)
        for x, txt in ((24, "Activity ID"), (74, "Activity Name"), (318, "Orig Dur"), (352, "Start"), (402, "Finish")):
            c.drawString(x, hy, txt)
        m = t0
        c.setFont("Helvetica", 6)
        while m < t1:
            c.setStrokeColor(colors.lightgrey)
            c.line(gx(m), 36, gx(m), hy + 8)
            c.drawString(gx(m) + 1, hy, m.strftime("%b"))
            if m.month == 1 or m == t0:
                c.drawString(gx(m) + 1, hy + 8, str(m.year))
            m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        dd = date.fromisoformat(sch["data_date"])
        c.setStrokeColor(colors.blue)
        c.setDash(2, 2)
        c.line(gx(dd), 36, gx(dd), hy + 8)
        c.setDash()
        c.setStrokeColor(colors.black)
        c.line(24, hy - 3, W - 24, hy - 3)
        y = top
        for kind, item in chunk:
            if kind == "wbs":
                c.setFillColor(colors.HexColor("#e8e8e8"))
                c.rect(24, y - 2.5, W - 48, row_h - 0.5, stroke=0, fill=1)
                c.setFillColor(colors.black)
                c.setFont("Helvetica-Bold", 7.5)
                c.drawString(26, y, item)
            else:
                a, x = item, rx[item["id"]]
                c.setFont("Helvetica", 7)
                c.drawString(24, y, a["id"])
                c.drawString(74, y, a["name"][:58])
                c.drawRightString(340, y, str(a["duration"]))
                c.drawString(352, y, x["start"])
                c.drawString(402, y, x["finish"])
                col = colors.grey if x["status"] == "complete" else (colors.HexColor("#c0392b") if x["critical"] else colors.HexColor("#2e6da4"))
                c.setFillColor(col)
                if a["duration"] == 0:
                    cx, cy = gx(date.fromisoformat(x["finish"])), y + 2.5
                    p = c.beginPath()
                    p.moveTo(cx, cy + 3.5); p.lineTo(cx + 3.5, cy); p.lineTo(cx, cy - 3.5); p.lineTo(cx - 3.5, cy); p.close()
                    c.drawPath(p, stroke=0, fill=1)
                else:
                    x0 = gx(date.fromisoformat(x["start"]))
                    x1 = gx(date.fromisoformat(x["finish"]) + timedelta(days=1))
                    c.rect(x0, y - 0.5, max(x1 - x0, 1.2), 6, stroke=0, fill=1)
                c.setFillColor(colors.black)
            y -= row_h
        c.setFont("Helvetica", 6.5)
        c.drawString(24, 22, "Bars: grey = complete, red = critical, blue = has float. Dashed line = data date. "
                             "Synthetic schedule written for INFO 492 C coursework.")
        c.showPage()
    c.save()


# ============================================================================ contract terms
def find_section(text, quote):
    """Section number of the paragraph that holds the quote (the last bold "**n.n" heading before it)."""
    pos = text.index(quote)
    heads = [(m.start(), m.group(1)) for m in re.finditer(r"\*\*(\d+(?:\.\d+)*)\b", text) if m.start() < pos]
    return heads[-1][1]


def term(text, value, quote, section=None):
    if quote not in text:
        raise AssertionError(f"quote not found verbatim: {quote[:70]!r}")
    sec = find_section(text, quote)
    if section and sec != section:
        raise AssertionError(f"section mismatch for {quote[:40]!r}: found {sec}, expected {section}")
    return {"value": value, "quote": quote, "section": sec}


def value_in_quote(key, value, quote):
    q = quote.lower()
    if isinstance(value, bool):
        return "critical path" in q
    if key == "fee_allowed_on":
        return "direct cost" in q and "subcontractor" in q
    if key == "compensable_causes":
        return all(v in q for v in value)
    if key == "concurrent_delay":
        return "concurrent" in q and value == "time_no_money"
    if isinstance(value, dict):
        return all(f"{v} days" in q for v in set(value.values()))
    if key.endswith("_pct"):
        return f"{value:g}%" in quote
    if key in ("contract_days",):
        return f"{value} days" in quote
    return f"${value:,}" in quote


def terms_key():
    A = (ROOT / "demo1" / "data" / "synthetic_contract.md").read_text(encoding="utf-8")
    B = CONTRACT_B
    a_notice = ("(a) 7 days after CM receives an RFI response, ASI, or submittal return that CM believes changes cost or time;\n"
                "- (b) 7 days after CM receives a written or oral direction from Owner or Architect that CM believes is a change;\n"
                "- (c) before disturbing the condition, and no later than 7 days after first observing it, for concealed or "
                "unknown physical conditions that differ from the Contract Documents;\n"
                "- (d) 14 days after CM first knew or should have known of any other event that may increase cost or time.")
    a_markup = ("A subcontractor may add overhead and profit of up to 10% on its own direct cost and up to 5% on the cost of "
                "work performed by its lower-tier subcontractors.")
    a_fee = "CM may add a Fee of 5% to the direct costs and subcontractor markups of a change."
    a_time = ("A time extension is compensated only for delays caused by Owner or Architect that are on the critical path, "
              "using the SGC daily rate in Section 5.2 and with no Fee.")
    a_sgc = "SGC may be increased only by CO for an extension of Contract Time, at a daily rate of $3,185 per day."
    contract_a = {
        "name": "Contract A: Demo 1 synthetic GC/CM contract (School Modernization and Addition)",
        "file": "demo1/data/synthetic_contract.md",
        "terms": {
            "markup_own_pct": term(A, 10, a_markup, "6.5.2"),
            "markup_lower_pct": term(A, 5, a_markup, "6.5.2"),
            "markup_total_pct": term(A, 15, "Total markup on any portion of the work shall not exceed 15%.", "6.5.2"),
            "fee_pct": term(A, 5, a_fee, "6.5.3"),
            "fee_allowed_on": term(A, ["CM direct costs", "subcontractor quotes"], a_fee, "6.5.3"),
            "labor_burden_pct": term(A, 32, "plus a fixed labor burden of 32% of direct wages", "5.4"),
            "blue_book_pct": term(A, 75, "Other CM-owned equipment is charged at 75% of the current published Blue Book rental rate", "6.5.4"),
            "approval_limit": term(A, 250000, "Owner's Representative may approve a CO of up to $250,000.", "6.7"),
            "notice_days_by_cause": term(A, {"RFI response": 7, "ASI": 7, "Submittal return": 7, "Owner direction": 7,
                                             "Architect direction": 7, "Concealed condition": 7, "Other event": 14}, a_notice, "6.2"),
            "contract_days": term(A, 540, "CM shall achieve Substantial Completion within 540 days after the Notice to Proceed", "3.2"),
            "liquidated_damages_per_day": term(A, 2500, "CM shall pay Owner $2,500 for each day of delay.", "3.3"),
            "daily_delay_rate": term(A, 3185, a_sgc, "5.2"),
            "sgc_total": term(A, 1720000, "SGC is $1,720,000, billed as shown in Exhibit C.", "5.2"),
            "extension_requires_critical_path": term(A, True, "An extension is available only for delays outside CM's control "
                                                              "that are shown on the critical path", "3.4"),
            "compensable_causes": term(A, ["owner", "architect"], a_time, "6.5.6"),
            "concurrent_delay": term(A, "time_no_money", "Delays with concurrent causes receive time but no compensation.", "6.5.6"),
        },
    }
    b_markup = ("A Subcontractor may add a combined allowance for overhead and profit of not more than 8% of the cost of the "
                "changed work it performs with its own forces, and not more than 4% of the cost of changed work performed by "
                "its lower-tier subcontractors.")
    b_fee = "On each Change Order CM may add a Fee of 4.5%, computed only on CM direct costs and subcontractor quotes."
    b_notice = ("CM shall give written notice of a Potential Change within 10 days after it receives an RFI response, Architect's "
                "Supplemental Instruction, submittal return, or written or oral direction from Owner or Architect, or after it "
                "first observes a concealed or unknown physical condition, which in that case it shall not disturb before giving "
                "notice. For any other event that may increase its cost or time, CM shall give notice within 21 days after it "
                "knew or reasonably should have known of the event.")
    b_comp = ("CM is entitled to an increase in the General Conditions Costs for an extension of the Contract Time only when "
              "the delay was caused by Owner, or by a separate contractor or consultant retained by Owner other than Architect, "
              "and the delay affected the critical path.")
    contract_b = {
        "name": "Contract B: synthetic GC/CM contract (Middle School Replacement)",
        "file": "demo4/data/contract_b.md",
        "terms": {
            "markup_own_pct": term(B, 8, b_markup, "7.5.2"),
            "markup_lower_pct": term(B, 4, b_markup, "7.5.2"),
            "markup_total_pct": term(B, 12, "In no event shall the cumulative markup of all tiers on any portion of the changed work exceed 12%.", "7.5.2"),
            "fee_pct": term(B, 4.5, b_fee, "7.5.3"),
            "fee_allowed_on": term(B, ["CM direct costs", "subcontractor quotes"], b_fee, "7.5.3"),
            "labor_burden_pct": term(B, 30, "plus a fixed labor burden equal to 30% of direct wages", "5.2"),
            "blue_book_pct": term(B, 70, "Equipment owned by CM or by an entity affiliated with CM shall be charged at 70% of the monthly, "
                                         "weekly, or daily rental rate", "7.5.4"),
            "approval_limit": term(B, 150000, "The Owner's Representative may execute any Change Order whose value does not exceed $150,000.", "7.7"),
            "notice_days_by_cause": term(B, {"RFI response": 10, "ASI": 10, "Submittal return": 10, "Owner direction": 10,
                                             "Architect direction": 10, "Concealed condition": 10, "Other event": 21}, b_notice, "7.2"),
            "contract_days": term(B, 420, "CM shall achieve Substantial Completion of the entire Work not later than 420 days after "
                                          "the date of commencement", "3.2"),
            "liquidated_damages_per_day": term(B, 1800, "$1,800 for each day that Substantial Completion is late", "3.3"),
            "daily_delay_rate": term(B, 2450, "the General Conditions Costs shall be increased at the rate of $2,450 for each day of "
                                              "the extension, with no Fee added", "5.3"),
            "sgc_total": term(B, 1286000, "The General Conditions Costs are a fixed sum of $1,286,000", "5.3"),
            "extension_requires_critical_path": term(B, True, "that is shown by a time impact analysis to delay an activity on the "
                                                              "critical path of the most recent accepted schedule update", "3.4"),
            "compensable_causes": term(B, ["owner"], b_comp, "7.5.6"),
            "concurrent_delay": term(B, "time_no_money", "When a delay to the critical path has concurrent causes and one of them is "
                                                         "the responsibility of CM or its Subcontractors, CM shall receive an extension "
                                                         "of time but no additional compensation for the period of concurrency.", "7.5.6"),
        },
        "notes": {"architect_caused_delay": "time only (Section 7.5.6)",
                  "gc_base_fee": "fixed $1,214,600 (Section 5.1) is not the change-order Fee"},
    }
    for ck in (contract_a, contract_b):
        for k, t in ck["terms"].items():
            assert value_in_quote(k, t["value"], t["quote"]), (ck["name"], k)
    # contract B states each key number once
    for s in ("8%", "4%", "12%", "4.5%", "30%", "70%", "$150,000", "10 days", "21 days", "420 days", "$1,800", "$2,450", "$1,286,000"):
        n = B.count(s)
        assert n == 1, (s, n)
    return {"meta": {"spec": "docs/demo4-spec.md section 3",
                     "verification": "each quote is a verbatim substring of its contract; each value appears in its quote "
                                     "(numbers as written, lists and enums by keyword); section is the numbered paragraph holding the quote",
                     "heldout": "contract C is a held-out contract written after the A/B evaluation; do not tune the reader on it"},
            "contracts": {"A": contract_a, "B": contract_b, "C": terms_key_c()}}


# ---------------------------------------------------------------------------- contract C (held out)
def find_section_c(text, quote):
    """Contract C numbers its paragraphs "**§ 9.4.3 ...**": section of the last such heading before the quote."""
    pos = text.index(quote)
    heads = [(m.start(), m.group(1)) for m in re.finditer(r"\*\*§ (\d+(?:\.\d+)*)\b", text) if m.start() < pos]
    return heads[-1][1]


def term_c(text, value, quote, section, note=None):
    if quote not in text:
        raise AssertionError(f"contract C quote not found verbatim: {quote[:70]!r}")
    sec = find_section_c(text, quote)
    if sec != section:
        raise AssertionError(f"contract C section mismatch for {quote[:40]!r}: found {sec}, expected {section}")
    t = {"value": value, "quote": quote, "section": sec}
    if note:
        t["note"] = note
    return t


C_CAUSE_WORDS = {"owner": "district", "architect": "architect", "concealed condition": "concealed"}


def value_in_quote_c(key, value, quote):
    """Contract C writes numbers as 'twelve percent (12%)', 'five (5) days', '$2,975.00'."""
    q = quote.lower()
    if value is None:
        return True                      # term not stated; the note says so
    if key == "fee_allowed_on":
        return "direct cost" in q and "subcontractor" in q and "bonds and insurance" in q
    if key == "compensable_causes":
        return all(C_CAUSE_WORDS[v] in q for v in value)
    if key == "concurrent_delay":
        return "concurrent" in q and "apportion" in q and value == "apportioned"
    if isinstance(value, dict):
        return all(f"({v}) days" in q for v in set(value.values()))
    if key.endswith("_pct"):
        return f"({value:g}%)" in quote
    if key == "contract_days":
        return f"({value}) calendar days" in quote
    return f"${value:,}" in quote


def terms_key_c():
    T = CONTRACT_C
    c_markup = ("For changed Work performed by a Subcontractor with its own forces, the Subcontractor's overhead and profit shall "
                "not exceed twelve percent (12%) of its direct cost; for changed Work performed by its lower-tier subcontractors, "
                "the Subcontractor may add six percent (6%) to the lower-tier cost.")
    c_fee_on = ("The Contractor's Fee on a Change Order shall be four percent (4%) of the sum of the Contractor's direct costs, "
                "Subcontractor quotes as marked up under Section 9.4.2, and the premiums for bonds and insurance attributable to the change.")
    c_notice = ("The Contractor shall give the District written notice of a Potential Change within five (5) days after receipt of an "
                "RFI response, Architect's supplemental instruction, submittal return, or direction from the District or the Architect, "
                "or after first observing a concealed or unknown physical condition at the site, which the Contractor shall not disturb "
                "until the District has had an opportunity to observe it. For any other event or circumstance on which the Contractor "
                "intends to base a request for additional cost or time, notice shall be given within twenty (20) days after the "
                "Contractor knew or should have known of it.")
    c_comp = ("The Contractor shall be compensated for extended Specified General Conditions under Section 5.3 only for a delay caused "
              "by the District, by the Architect, or by a concealed physical condition at the site that differs materially from the "
              "Contract Documents.")
    c_conc = ("Where a delay results from concurrent causes, one attributable to the District and one to the Contractor, the extension "
              "shall be granted for the full period of delay, but the compensation for extended Specified General Conditions shall be "
              "apportioned between the District and the Contractor in proportion to their respective contributions to the delay.")
    no_cp = ("not stated. Section 8.3.1 extends time 'for such reasonable time as the District's Project Manager may determine' and "
             "Section 8.3.2 asks only for a narrative and 'such schedule information as ... may reasonably require'. Section 3.5 "
             "requires the schedule to show the critical path but does not make critical-path delay a condition of an extension. "
             "A reader should return null / not found, not true.")
    contract_c = {
        "name": "Contract C (HELD OUT): synthetic GC/CM contract (Middle School HVAC Replacement and Seismic Retrofit)",
        "file": "demo4/data/contract_c.md",
        "split": "heldout",
        "terms": {
            "markup_own_pct": term_c(T, 12, c_markup, "9.4.2"),
            "markup_lower_pct": term_c(T, 6, c_markup, "9.4.2"),
            "markup_total_pct": term_c(T, 17, "The total of all overhead and profit markups by all tiers on any item of changed Work, "
                                              "excluding the Contractor's Fee, shall not exceed seventeen percent (17%).", "9.4.2"),
            "fee_pct": term_c(T, 3.75, 'Section 9.4.3 is amended by deleting "four percent (4%)" and substituting '
                                       '"three and three-quarters percent (3.75%)".', "16.3",
                              note="Section 9.4.3 states 4%, but Supplementary Condition 16.3 replaces it with 3.75%; "
                                   "Section 1.2 makes Article 16 govern over the Articles."),
            "fee_allowed_on": term_c(T, ["CM direct costs", "subcontractor quotes", "bond and insurance premiums"], c_fee_on, "9.4.3",
                                     note="The base of the Fee is unchanged by 16.3; only the rate is amended."),
            "labor_burden_pct": term_c(T, 35, "plus a labor burden of thirty-five percent (35%) of base wages", "5.2"),
            "blue_book_pct": term_c(T, 80, "Equipment owned by the Contractor or an affiliate is charged at eighty percent (80%) of the "
                                           "rates in the current Equipment Watch Rental Rate Blue Book", "9.4.5"),
            "approval_limit": term_c(T, 100000, "Change Orders whose individual value does not exceed One Hundred Thousand Dollars "
                                                "($100,000) may be executed by the District's Capital Projects Director.", "9.6"),
            "notice_days_by_cause": term_c(T, {"RFI response": 5, "ASI": 5, "Submittal return": 5, "Owner direction": 5,
                                               "Architect direction": 5, "Concealed condition": 5, "Other event": 20}, c_notice, "9.2"),
            "contract_days": term_c(T, 455, "The Contractor shall achieve Substantial Completion of the entire Work within four hundred "
                                            "fifty-five (455) calendar days after the date of the Notice to Proceed for Construction.", "3.2"),
            "liquidated_damages_per_day": term_c(T, 2200, "For each calendar day after the Contract Time that Substantial Completion has "
                                                          "not been achieved, the Contractor shall pay the District Two Thousand Two "
                                                          "Hundred Dollars ($2,200) as liquidated damages and not as a penalty.", "3.3"),
            "daily_delay_rate": term_c(T, 2975, "the Specified General Conditions shall be increased by $2,975.00 per calendar day of "
                                                "the extension", "5.3",
                                       note="Repeated in Exhibit B; Section 5.3 governs (Section 1.2: Articles over Exhibits)."),
            "sgc_total": term_c(T, 1412750, "The Specified General Conditions are a lump sum of $1,412,750", "5.3"),
            "extension_requires_critical_path": term_c(T, None, "the Contract Time shall be extended by Change Order for such reasonable "
                                                                "time as the District's Project Manager may determine.", "8.3.1",
                                                       note=no_cp),
            "compensable_causes": term_c(T, ["owner", "architect", "concealed condition"], c_comp, "9.4.7",
                                         note="'District' is the Owner. Weather and other causes beyond both parties' control: time only."),
            "concurrent_delay": term_c(T, "apportioned", c_conc, "9.4.7",
                                       note="Full time extension; extended Specified General Conditions apportioned by each party's "
                                            "share of the delay (not 'time, no money')."),
        },
        "notes": {"extension_requires_critical_path": "not stated in contract C (value null); see the term's note",
                  "fee_pct": "4% in Section 9.4.3 is superseded by 3.75% in Section 16.3",
                  "gc_base_fee": "5.25% of the MACC (Section 5.1) is not the change-order Fee",
                  "phase_1_liquidated_damages": "$750 per day (Section 3.3) is an interim milestone rate, not the Substantial Completion rate",
                  "field_order_limit": "$7,500 (Section 9.5) is the site representative's Field Order limit, not the Change Order approval limit",
                  "architect_non_compensable": "Section 7.2 bars time and money for Architect review of resubmittals the Contractor caused; "
                                               "Architect-caused delay is otherwise compensable under 9.4.7"},
    }
    for k, t in contract_c["terms"].items():
        assert value_in_quote_c(k, t["value"], t["quote"]), ("C", k)
    assert set(contract_c["terms"]) == set(terms_key_a_keys()), "contract C must cover every spec term"
    # how often each key figure appears in contract C: once, except where the contract repeats or amends it
    expected = {"(12%)": 1, "(6%)": 1, "(17%)": 1, "(3.75%)": 1, "(4%)": 2, "(35%)": 1, "(80%)": 1, "$100,000": 1,
                "five (5) days": 1, "twenty (20) days": 1, "(455)": 1, "$2,200": 1, "$2,975.00": 2, "$1,412,750": 3}
    for s, n in expected.items():
        assert T.count(s) == n, (s, T.count(s), n)
    return contract_c


def terms_key_a_keys():
    return ["markup_own_pct", "markup_lower_pct", "markup_total_pct", "fee_pct", "fee_allowed_on", "labor_burden_pct",
            "blue_book_pct", "approval_limit", "notice_days_by_cause", "contract_days", "liquidated_damages_per_day",
            "daily_delay_rate", "sgc_total", "extension_requires_critical_path", "compensable_causes", "concurrent_delay"]


def md_to_pdf(md, path, title):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=12.5, spaceAfter=5)
    el = []
    for block in md.strip().split("\n\n"):
        for line in block.split("\n"):
            line = line.rstrip()
            if not line:
                continue
            txt = escape(line)
            txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
            txt = re.sub(r"\*(.+?)\*", r"<i>\1</i>", txt)
            if line.startswith("# "):
                el.append(Paragraph(txt[2:], ss["Title"]))
            elif line.startswith("## "):
                el.append(Paragraph(txt[3:], ss["Heading2"]))
            elif line.startswith("> "):
                el.append(Paragraph(txt[5:], ParagraphStyle("q", parent=body, leftIndent=14, textColor="#444444")))
            else:
                el.append(Paragraph(txt, body))
        el.append(Spacer(1, 2))

    def stamp(canv, doc):
        canv.setFont("Helvetica", 7)
        canv.drawString(0.8 * inch, 0.5 * inch, f"SYNTHETIC TEST DOCUMENT - INFO 492 C   Page {doc.page}")

    doc = SimpleDocTemplate(str(path), pagesize=letter, title=title, author="ClauseStream synthetic data",
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch, invariant=1)
    doc.build(el, onFirstPage=stamp, onLaterPages=stamp)


# ============================================================================ change proposals
def sub(name, trade, own, lower=(), own_pct=0.10, lower_pct=0.05):
    lines = [{"desc": d, "qty": q, "unit": u, "rate": rt, "amount": r2(q * rt)} for d, q, u, rt in own]
    own_direct = r2(sum(l["amount"] for l in lines))
    lower_lines = [{"firm": f, "scope": s, "amount": a} for f, s, a in lower]
    lower_total = r2(sum(l["amount"] for l in lower_lines))
    own_mk, low_mk = r2(own_direct * own_pct), r2(lower_total * lower_pct)
    return {"firm": name, "trade": trade, "markup_rates_stated": {"own_work": own_pct, "lower_tier": lower_pct},
            "own_direct": own_direct, "lower_tier_total": lower_total, "markup_on_own": own_mk,
            "markup_on_lower_tier": low_mk, "quote_total": r2(own_direct + lower_total + own_mk + low_mk),
            "lines": lines, "lower_tier": lower_lines}


def labor(desc, hours, wage):
    return {"kind": "labor", "desc": desc, "hours": hours, "wage": wage, "burden_rate": BURDEN_A,
            "amount": r2(hours * wage * (1 + BURDEN_A))}


def equip(desc, hours, bluebook):
    rate = r2(bluebook * 0.75)
    return {"kind": "equipment", "desc": desc, "owned_by_cm": True, "hours_used": hours, "idle_hours": 0,
            "blue_book_rate": bluebook, "rate_charged": rate, "amount": r2(hours * rate), "daily_logs_attached": True}


def material(desc, amount):
    return {"kind": "material", "desc": desc, "amount": amount}


def cover(subs, cm, time_money_days):
    direct = r2(sum(l["amount"] for l in cm if l["kind"] in ("labor", "equipment", "material")))
    subs_total = r2(sum(s["quote_total"] for s in subs))
    fee = r2((direct + subs_total) * FEE_A)
    time_amt = r2(time_money_days * SGC_DAILY_A)
    return {"cm_direct_costs": direct, "subcontractor_quotes": subs_total, "fee_rate": FEE_A,
            "fee_applied_to": ["CM direct costs", "subcontractor quotes"], "fee": fee,
            "bond_and_insurance": 0.0, "bo_tax": 0.0, "permit_fees": 0.0, "nss_items": 0.0, "sgc_items": 0.0,
            "extended_sgc_time": time_amt, "total_requested": r2(direct + subs_total + fee + time_amt)}


def F(fid, name, dur):
    return {"id": fid, "name": name, "duration": dur}


def R(pred, succ, t="FS", lag=0):
    return {"pred": pred, "succ": succ, "type": t, "lag": lag}


# Scenario design. Strata group the scenario types so the dev/test split covers each group.
STRATA = {
    "critical_accurate": ["CP-0401", "CP-0402", "CP-0403"],
    "off_critical_claimed": ["CP-0404", "CP-0405", "CP-0410"],
    "padded_partial_float": ["CP-0406", "CP-0407", "CP-0408"],
    "non_compensable_cause": ["CP-0409", "CP-0411", "CP-0412"],
    "concurrent_or_no_claim": ["CP-0413", "CP-0414", "CP-0415"],
}

# claim: ("accurate",) = CM claims what its own TIA shows; ("fixed", n) = CM claims n days; ("none",) = no time claimed.
# expect: what the design intends; the builder asserts the computed result matches it.
CASE_DEFS = [
    dict(id="CP-0401", scenario="On critical path, Owner-caused, accurate claim", title="Stage lift pit added at addition per Owner direction",
         cause_type="Owner direction", ref="Owner email 2020-06-08", event="2020-06-08", notice_after=3, cp_after=14,
         party="owner", concurrent=False, claim=("accurate",), calendar=True, expect="critical",
         narrative="Owner's Representative directed a hydraulic stage lift in the addition's multipurpose room. The lift needs a pit, "
                   "excavated, formed and poured with the foundations. Concrete sub prices the pit.",
         scope="Drawing S-101 shows a flat slab on grade at the multipurpose room; no pit.",
         subs=[sub("Granite Concrete", "Concrete", [("Excavate and haul pit", 1, "ls", 3800.0), ("Pit walls and slab, formed and poured", 14, "cy", 690.0),
                                                     ("Waterproofing at pit", 420, "sf", 9.5), ("Finisher", 24, "hr", 84.0)])],
         context="The pit must be built after the footings and foundation walls and before the slab on grade is poured over the area.",
         fragnet={"activities": [F("F-0401A", "Excavate, form and pour stage lift pit", 6)],
                  "relationships": [R("A1420", "F-0401A"), R("F-0401A", "A1430")]}),
    dict(id="CP-0402", scenario="On critical path, Architect-caused, accurate claim", title="Field-modified gym truss bearings per RFI-214",
         cause_type="RFI response", ref="RFI-214", event="2020-06-12", notice_after=4, cp_after=14,
         party="architect", concurrent=False, claim=("accurate",), calendar=True, expect="critical",
         narrative="RFI-214 asked how the gym roof trusses bear on the existing masonry wall. Architect's response corrects a detailing error "
                   "and requires new slotted bearing assemblies to be field-welded after the trusses are set.",
         scope="Drawing S-301 detail 4 shows a standard bearing plate, which conflicts with the existing wall's anchor layout.",
         subs=[sub("Puget Steel Erectors", "Structural steel", [("Slotted bearing assembly", 12, "ea", 640.0), ("Ironworker", 64, "hr", 96.0),
                                                                 ("Special inspection, welds", 1, "ls", 1450.0)])],
         context="The field welding can start 15 working days after steel erection starts, when the gym trusses are set, and the metal deck "
                 "cannot start until the welding is done and inspected.",
         fragnet={"activities": [F("F-0402A", "Field-weld revised gym truss bearing assemblies (RFI-214)", 4)],
                  "relationships": [R("A1460", "F-0402A", "SS", 15), R("F-0402A", "A1470")]}),
    dict(id="CP-0403", scenario="On critical path, Owner-caused, claim stated in working days", title="Acoustic wall panels in addition music room",
         cause_type="Owner direction", ref="Owner letter 2020-06-15", event="2020-06-15", notice_after=2, cp_after=12,
         party="owner", concurrent=False, claim=("accurate",), calendar=False, expect="critical",
         narrative="Owner added fabric-wrapped acoustic wall panels and wall blocking in the addition's music and band rooms.",
         scope="Spec 09 84 00 is not in the project manual; drawings show painted gypsum board in rooms 205 and 206.",
         subs=[sub("Harmony Acoustics", "Acoustic treatments", [("Fabric-wrapped wall panels", 1380, "sf", 23.0), ("Installer", 56, "hr", 72.0)],
                   lower=[("Ridgeline Carpentry", "In-wall blocking, rooms 205-206", 4100.0)])],
         context="The panels go on after the addition is painted and must be complete before the ceiling grid goes in, because the "
                 "panels run to the deck.",
         fragnet={"activities": [F("F-0403A", "Install acoustic wall panels - addition music rooms", 7)],
                  "relationships": [R("A1760", "F-0403A"), R("F-0403A", "A1740")]}),
    dict(id="CP-0404", scenario="Off critical path (sitework float), Owner-caused, days claimed", title="Added play structure at primary playground",
         cause_type="Owner direction", ref="Owner email 2020-06-17", event="2020-06-17", notice_after=3, cp_after=14,
         party="owner", concurrent=False, claim=("fixed", 14), calendar=True, expect="absorbed",
         narrative="Owner added a second play structure and its safety surfacing at the primary playground.",
         scope="Drawing L-201 shows one play structure.",
         subs=[sub("Evergreen Site Works", "Site improvements", [("Play structure, furnished", 1, "ea", 38500.0), ("Footings", 8, "ea", 610.0),
                                                                  ("Poured-in-place surfacing", 1650, "sf", 14.0), ("Laborer", 60, "hr", 64.0)])],
         context="The new structure is installed after the playground and play surfacing work and must be finished before final "
                 "striping and site cleanup.",
         fragnet={"activities": [F("F-0404A", "Install added play structure and surfacing", 10)],
                  "relationships": [R("A2140", "F-0404A"), R("F-0404A", "A2170")]}),
    dict(id="CP-0405", scenario="Off critical path (existing-building float), Architect-caused, days claimed", title="Revised casework blocking per ASI-061",
         cause_type="ASI", ref="ASI-061", event="2020-06-19", notice_after=4, cp_after=13,
         party="architect", concurrent=False, claim=("fixed", 12), calendar=True, expect="absorbed",
         narrative="ASI-061 moves the Wing A classroom casework to the opposite walls. Framing sub adds blocking and patches the moved locations.",
         scope="Drawing A-401 shows casework on the corridor walls of rooms 110 to 118.",
         subs=[sub("Evergreen Framing", "Framing and drywall", [("Blocking and backing", 9, "room", 520.0), ("Framer", 72, "hr", 74.0),
                                                              ("Drywall patch at old locations", 9, "room", 310.0)])],
         context="The blocking work follows the Wing A framing and drywall and has to be done before painting in the existing building starts.",
         fragnet={"activities": [F("F-0405A", "Rework casework blocking - Wing A (ASI-061)", 8)],
                  "relationships": [R("A1700", "F-0405A"), R("F-0405A", "A1750")]}),
    dict(id="CP-0406", scenario="Partial float consumption, Owner-caused, full event duration claimed", title="PV-ready roof upgrade at addition",
         cause_type="Owner direction", ref="Owner letter 2020-06-22", event="2020-06-22", notice_after=3, cp_after=14,
         party="owner", concurrent=False, claim=("fixed", 17), calendar=True, expect="partial",
         narrative="Owner directed a PV-ready roof at the addition: added blocking, conduit sleeves and thicker insulation under the membrane.",
         scope="Spec 07 54 23 covers a standard TPO roof with R-30 insulation and no solar provisions.",
         subs=[sub("Summit Roofing", "Roofing", [("Added insulation R-30 to R-38", 21000, "sf", 1.35), ("PV stanchion blocking", 140, "ea", 85.0),
                                                 ("Roofer", 120, "hr", 82.0)])],
         context="The added blocking and insulation work starts after the metal deck and elevated slab are complete, and the roofing "
                 "membrane cannot start until it is done. CM's claim counts the whole 12 working days of added work.",
         fragnet={"activities": [F("F-0406A", "PV-ready blocking and added roof insulation - addition", 12)],
                  "relationships": [R("A1470", "F-0406A"), R("F-0406A", "A1520")]}),
    dict(id="CP-0407", scenario="On critical path, Architect-caused, padded claim", title="Storefront head subframing per RFI-233",
         cause_type="RFI response", ref="RFI-233", event="2020-06-24", notice_after=5, cp_after=14,
         party="architect", concurrent=False, claim=("fixed", 21), calendar=True, expect="critical",
         narrative="RFI-233 response revises the storefront head detail at the addition and adds steel subframing above every storefront opening.",
         scope="Drawing A-501 detail 7 shows storefront heads anchored directly to the framing.",
         subs=[sub("Cascade Glazing", "Glazing", [("Steel head subframe", 18, "ea", 410.0), ("Glazier", 40, "hr", 88.0)])],
         context="The subframing goes in after the exterior framing and sheathing at the addition and must be in place before "
                 "windows and storefront can be set.",
         fragnet={"activities": [F("F-0407A", "Install storefront head subframing (RFI-233)", 4)],
                  "relationships": [R("A1510", "F-0407A"), R("F-0407A", "A1530")]}),
    dict(id="CP-0408", scenario="Partial float consumption, Architect-caused, padded claim", title="Rerouted sprinkler mains per ASI-070",
         cause_type="ASI", ref="ASI-070", event="2020-06-25", notice_after=4, cp_after=14,
         party="architect", concurrent=False, claim=("fixed", 14), calendar=True, expect="partial",
         narrative="ASI-070 reroutes the addition's sprinkler mains around the revised duct mains and adds two zones.",
         scope="Drawing FP-201 shows the mains running through the corridor ceiling space.",
         subs=[sub("Sentinel Fire Protection", "Fire sprinklers", [("Rerouted main, pipe and fittings", 420, "lf", 38.0), ("Zone valve assembly", 2, "ea", 2150.0),
                                                                    ("Sprinkler fitter", 96, "hr", 98.0)])],
         context="The rerouting follows the addition's sprinkler rough-in and must be done before the in-wall and above-ceiling "
                 "inspections for the addition.",
         fragnet={"activities": [F("F-0408A", "Reroute sprinkler mains - addition (ASI-070)", 9)],
                  "relationships": [R("A1640", "F-0408A"), R("F-0408A", "A1685")]}),
    dict(id="CP-0409", scenario="On critical path, contractor-caused (no extension)", title="Steel erection start: erector crane availability",
         cause_type="Other event", ref="Erector letter 2020-06-10", event="2020-06-10", notice_after=6, cp_after=14,
         party="contractor", concurrent=False, claim=("fixed", 7), calendar=True, expect="critical",
         narrative="The steel erector advised that its crawler crane is committed to another job and will arrive 5 working days later "
                   "than planned. CM asks for time and the erector's standby cost.",
         scope="Subcontract with the erector requires mobilization within 3 days of notice.",
         subs=[sub("Puget Steel Erectors", "Structural steel", [("Crane standby, remobilization", 1, "ls", 6400.0)])],
         context="The crane wait sits between the slab on grade and the start of steel erection: erection cannot start until the "
                 "crane arrives, and the wait begins when the slab is done.",
         fragnet={"activities": [F("F-0409A", "Wait for erector's crane (erector's commitment elsewhere)", 5)],
                  "relationships": [R("A1430", "F-0409A"), R("F-0409A", "A1460")]}),
    dict(id="CP-0410", scenario="Off critical path, contractor-caused, days claimed", title="Flatwork crew shortage at site",
         cause_type="Other event", ref="Sub letter 2020-06-15", event="2020-06-15", notice_after=5, cp_after=14,
         party="contractor", concurrent=False, claim=("fixed", 10), calendar=True, expect="absorbed",
         narrative="The flatwork sub reports a crew shortage and will start curbs and sidewalks 8 working days late. CM asks for time only.",
         scope="Subcontract schedule requires flatwork to follow site electrical directly.",
         subs=[],
         context="The late start sits after the site electrical and lighting conduit work and before curbs, sidewalks and flatwork.",
         fragnet={"activities": [F("F-0410A", "Flatwork crew unavailable (subcontractor shortage)", 8)],
                  "relationships": [R("A2110", "F-0410A"), R("F-0410A", "A2130")]}),
    dict(id="CP-0411", scenario="On critical path, weather (neither party), accurate claim", title="Abnormal rainfall at addition excavation",
         cause_type="Other event", ref="Daily reports 2020-06-03 to 2020-06-08", event="2020-06-03", notice_after=7, cp_after=14,
         party="neither", concurrent=False, claim=("accurate",), calendar=True, expect="critical",
         narrative="Rainfall in early June 2020 was well above the ten-year average at the nearest NOAA station and flooded the addition "
                   "footprint. CM pumped the site and asks for time only.",
         scope="Daily reports and NOAA data attached.",
         subs=[], cm=[labor("Laborer, pumping and erosion control", 24, 41.0), equip("Trash pump (CM-owned)", 24, 22.0)],
         context="The weather days fall after the haul-off and clearing of the addition footprint and before excavation and shoring "
                 "can start.",
         fragnet={"activities": [F("F-0411A", "Weather standby - abnormal rainfall at addition footprint", 4)],
                  "relationships": [R("A1340", "F-0411A"), R("F-0411A", "A1400")]}),
    dict(id="CP-0412", scenario="Partial float consumption, weather (neither party), padded claim", title="Flooded underslab utility trench",
         cause_type="Other event", ref="Daily reports 2020-06-26 to 2020-06-30", event="2020-06-26", notice_after=6, cp_after=14,
         party="neither", concurrent=False, claim=("fixed", 21), calendar=True, expect="partial",
         narrative="A second abnormal storm flooded the open underslab utility trench at the addition. The trench has to be dewatered, "
                   "re-excavated and the bedding replaced. CM asks for time only.",
         scope="Daily reports and NOAA data attached.",
         subs=[], cm=[labor("Laborer, dewatering and bedding", 40, 41.0), equip("Mini excavator (CM-owned)", 16, 68.0),
                      material("Pipe bedding gravel", 1240.0)],
         context="The recovery work follows the underslab utilities and must be finished before the slab on grade is poured. CM's claim "
                 "counts all 15 working days of recovery work.",
         fragnet={"activities": [F("F-0412A", "Dewater and re-excavate flooded underslab utility trench", 15)],
                  "relationships": [R("A1410", "F-0412A"), R("F-0412A", "A1430")]}),
    dict(id="CP-0413", scenario="Concurrent delay: Owner flooring change and flooring sub crew shortage", title="Classroom flooring change (concurrent with crew shortage)",
         cause_type="Owner direction", ref="Owner email 2020-06-29", event="2020-06-29", notice_after=3, cp_after=14,
         party="owner", concurrent=True, claim=("accurate",), calendar=True, expect="critical",
         narrative="Owner changed the addition classroom flooring from VCT to rubber tile, which adds a resubmittal and longer lead time. "
                   "Separately, the flooring sub has told CM it will be short a crew for the same period.",
         scope="Spec 09 65 19 specifies VCT in classrooms 201 to 212.",
         subs=[sub("Northwest Floors", "Flooring", [("Rubber tile upcharge over VCT", 9800, "sf", 3.4), ("Installer", 32, "hr", 76.0)])],
         context="Both delays fall between the addition ceilings and the addition classroom flooring. The Owner's change adds 6 working "
                 "days for the resubmittal and delivery; the sub's crew shortage would by itself also hold the flooring start by 6 "
                 "working days, over the same period.",
         fragnet={"activities": [F("F-0413A", "Resubmit and deliver rubber flooring (Owner change)", 6),
                                 F("F-0413B", "Flooring crew shortage (subcontractor)", 6)],
                  "relationships": [R("A1740", "F-0413A"), R("F-0413A", "A1790"), R("A1740", "F-0413B"), R("F-0413B", "A1790")]},
         concurrent_split={"owner": ["F-0413A"], "contractor": ["F-0413B"]}),
    dict(id="CP-0414", scenario="No time claimed; work off the critical path", title="Sunshades at existing windows per ASI-075",
         cause_type="ASI", ref="ASI-075", event="2020-06-30", notice_after=4, cp_after=14,
         party="architect", concurrent=False, claim=("none",), calendar=True, expect="absorbed",
         narrative="ASI-075 adds aluminum sunshades above the south-facing replacement windows in the existing building.",
         scope="Drawing A-210 shows no sunshades on the existing building.",
         subs=[sub("Cascade Glazing", "Glazing", [("Aluminum sunshade, 8 ft", 22, "ea", 1180.0), ("Glazier", 66, "hr", 88.0)])],
         context="The sunshades are installed after the existing-building window replacement and before exterior painting and sealants. "
                 "CM requests no time.",
         fragnet={"activities": [F("F-0414A", "Install sunshades - existing building (ASI-075)", 6)],
                  "relationships": [R("A1560", "F-0414A"), R("F-0414A", "A1580")]}),
    dict(id="CP-0415", scenario="No time claimed; no schedule impact", title="Added data drops in Wing B offices",
         cause_type="Owner direction", ref="Owner email 2020-06-23", event="2020-06-23", notice_after=2, cp_after=10,
         party="owner", concurrent=False, claim=("none",), calendar=True, expect="none",
         narrative="Owner added 16 data drops in the Wing B administration offices. Work fits in the existing MEP rough-in for Wing B.",
         scope="Drawing T-102 shows 20 data drops in Wing B offices.",
         subs=[sub("Sound Electric", "Electrical", [("Electrician", 24, "hr", 96.0), ("Box, ring, conduit per drop", 16, "ea", 38.0)],
                   lower=[("Lakeside Low Voltage", "Cat 6 cabling, termination, testing", 4800.0)])],
         context="No schedule activities are added; the drops are installed by the existing crew within MEP rough-in - Wing B. "
                 "CM requests no time.",
         fragnet={"activities": [], "relationships": []}),
]

# ---------------------------------------------------------------------------- held-out cases (CP-0501..CP-0505)
# Written after the A/B / CP-0401..0415 evaluation by a helper that did not see the reader or drafter code.
# Same schedule and contract A rules as above. Differences from the seen set, on purpose (realism, not difficulty):
#   * time_narrative is written by hand in a superintendent's or scheduler's words. Four of the five do not name any
#     schedule activity ID or fragnet ID; they describe the tie-in work ("drywall in the new building", "ceilings in
#     the new wing"), and one (CP-0504) is a loose field note with an aside about an unrelated RFI.
#   * claims are fixed numbers; claim_check states the design ("matches" the computed delay in the claim's units,
#     "padded", or "absorbed") and the builder asserts it.
HELDOUT_DEFS = [
    dict(id="CP-0501", stratum="heldout_critical", scenario="Held out: on critical path, Owner-caused, accurate claim, narrative without IDs",
         title="Convert addition storage room 231 to IDF with dedicated cooling",
         cause_type="Owner direction", ref="Owner email 2020-07-06", event="2020-07-06", notice_after=3, cp_after=15,
         party="owner", concurrent=False, claim=("fixed", 10), calendar=True, expect="critical", claim_check="matches",
         narrative="District IT asked, and the Owner's Representative directed by email, that storage room 231 in the addition become an "
                   "intermediate distribution frame (IDF) room with its own ductless split cooling unit, a dedicated 30-amp circuit and a "
                   "fire-rated plywood backboard.",
         scope="Drawings M-201 and E-201 show room 231 as unconditioned storage with one convenience outlet.",
         subs=[sub("Rainier Mechanical", "HVAC", [("Ductless split unit, 2-ton, furnished", 1, "ea", 6850.0), ("Line set and condensate", 1, "ls", 2400.0),
                                                  ("Refrigeration fitter", 40, "hr", 104.0)],
                   lower=[("Northwest Controls", "Unit alarm tie-in to BAS", 1850.0)]),
               sub("Sound Electric", "Electrical", [("30A dedicated circuit", 1, "ea", 1450.0), ("Electrician", 16, "hr", 96.0)])],
         time_narrative="Room 231 sits in the middle of the second-floor rough-in area of the new wing. The added line set, condensate "
                        "drain, dedicated circuit and rated penetrations for the IDF can't go in until our MEP rough-in up there is "
                        "otherwise complete, because the mechanical and electrical crews work that whole floor in sequence, and all of it "
                        "has to be in before the in-wall and above-ceiling inspection for the new wing. Mechanical and electrical together "
                        "figure 5 working days for the added rough-in. Run against the June update, this pushes Substantial Completion. "
                        "CM requests 10 calendar days of time extension and extended general conditions for those days.",
         fragnet={"activities": [F("F-0501A", "Added IDF rough-in: line set, condensate, dedicated circuit, rated penetrations - addition", 5)],
                  "relationships": [R("A1630", "F-0501A"), R("F-0501A", "A1685")]}),
    dict(id="CP-0502", stratum="heldout_off_critical", scenario="Held out: off critical path (Wing B float), Architect-caused, days claimed",
         title="Collector straps and drag struts at Wing B roof per ASI-088",
         cause_type="ASI", ref="ASI-088", event="2020-07-09", notice_after=5, cp_after=14,
         party="architect", concurrent=False, claim=("fixed", 15), calendar=True, expect="absorbed", claim_check="absorbed",
         narrative="ASI-088 adds steel collector straps and two drag struts at the Wing B roof diaphragm to complete the load path to the "
                   "new shear walls.",
         scope="Drawing S-402 shows the Wing B shear walls with no collectors at the roof diaphragm.",
         subs=[sub("Olympic Structural", "Structural steel", [("Collector strap, galvanized", 140, "lf", 46.0), ("Drag strut, fabricated", 2, "ea", 3900.0),
                                                              ("Ironworker", 80, "hr", 96.0), ("Special inspection, welds", 1, "ls", 1850.0)])],
         time_narrative="Time impact analysis against schedule update 2020-06-01. Fragnet inserted: F-0502A Install collector straps and "
                        "drag struts - Wing B roof diaphragm (ASI-088), original duration 10 working days. Predecessor: A1490 Seismic "
                        "upgrade - Wing B (finish-to-start, no lag). Successor: A1620 MEP rough-in - Wing B (finish-to-start, no lag); "
                        "the MEP trades cannot work overhead in Wing B while the ironworkers are welding at the roof diaphragm. "
                        "CM requests 15 calendar days of time extension and extended general conditions for those days.",
         fragnet={"activities": [F("F-0502A", "Install collector straps and drag struts - Wing B roof diaphragm (ASI-088)", 10)],
                  "relationships": [R("A1490", "F-0502A"), R("F-0502A", "A1620")]}),
    dict(id="CP-0503", stratum="heldout_padded", scenario="Held out: partial float consumption, Owner-caused, padded claim, narrative without IDs",
         title="Moisture vapor mitigation coating at addition gym slab",
         cause_type="Owner direction", ref="Owner letter 2020-07-13", event="2020-07-13", notice_after=4, cp_after=15,
         party="owner", concurrent=False, claim=("fixed", 21), calendar=True, expect="partial", claim_check="padded",
         narrative="After reviewing the wood flooring manufacturer's warranty terms, the Owner directed CM to add a moisture vapor "
                   "mitigation coating over the gym slab in the addition, in addition to the specified vapor retarder under the sleepers.",
         scope="Spec 09 64 66 relies on a 6-mil poly vapor retarder under the sleepers; no slab coating is specified.",
         subs=[sub("Cascade Coatings", "Concrete coatings", [("Shot-blast slab prep", 7200, "sf", 1.10), ("Two-coat epoxy vapor mitigation", 7200, "sf", 4.85),
                                                             ("Slab RH testing", 1, "ls", 1150.0), ("Applicator", 48, "hr", 78.0)])],
         time_narrative="The gym wood floor installer won't start until the slab under it is coated and cured. We can't start the coating "
                        "until the ceilings in the new wing are done, because the ceiling crew's lifts are on the gym floor until then. "
                        "The coating work is RH testing, shot-blasting and two coats of epoxy, 9 working days, and then the manufacturer "
                        "wants 5 working days of cure before the sleepers go down. That is 14 working days of added work in front of the "
                        "gym floor, about three calendar weeks. CM requests 21 calendar days of time extension and extended general "
                        "conditions for those days.",
         fragnet={"activities": [F("F-0503A", "RH test, shot-blast and apply vapor mitigation coating - gym slab", 9),
                                 F("F-0503B", "Cure vapor mitigation coating before gym wood floor", 5)],
                  "relationships": [R("A1740", "F-0503A"), R("F-0503A", "F-0503B"), R("F-0503B", "A1800")]}),
    dict(id="CP-0504", stratum="heldout_messy", scenario="Held out: on critical path, Architect-caused, field-note narrative without IDs, claim in working days",
         title="Lowered corridor ceiling and soffits at addition per RFI-341",
         cause_type="RFI response", ref="RFI-341", event="2020-07-16", notice_after=4, cp_after=15,
         party="architect", concurrent=False, claim=("fixed", 8), calendar=False, expect="critical", claim_check="matches",
         narrative="RFI-341 reported that the supply duct mains in the addition's second-floor corridor clash with the beams at the "
                   "specified ceiling height. Architect's response lowers the corridor ceiling 10 inches and adds framed soffits at the "
                   "classroom doors.",
         scope="Drawing A-521 shows the corridor ceiling at 9'-6\" with no soffits.",
         subs=[sub("Evergreen Framing", "Framing and drywall", [("Soffit framing", 380, "lf", 21.0), ("Gypsum board at soffits", 1150, "sf", 6.20),
                                                                ("Framer", 64, "hr", 74.0)]),
               sub("Rainier Mechanical", "HVAC", [("Drop and re-hang branch duct", 14, "ea", 520.0), ("Sheet metal worker", 36, "hr", 102.0)],
                   lower=[("Sentinel Fire Protection", "Lower sprinkler drops to new ceiling height", 2850.0)])],
         time_narrative="Per the RFI 341 answer (rec'd 7/16) the 2nd floor corridor lid in the new building comes down 10\" and we get "
                        "soffits at every classroom door. Talked to Rainier Mech - their guys drop and re-hang the branch ducts and the "
                        "sprinkler sub lowers the heads at the same time, figure 3 working days, and they can't start until drywall in the "
                        "new building is finished (they'd be fighting the tapers for the same lifts). After that our framers frame, board "
                        "and tape the soffits, 5 working days. Painters were going to roll straight in behind the drywall in the new "
                        "building and now they can't start until the soffits are done, and the ceiling grid and everything after it slides "
                        "with them. Inspector says she'll look at the relocated duct the same morning we close it, so no extra time for the "
                        "re-inspection. This is separate from RFI 327 (stair rail), which is answered and has no time. Requesting 8 working "
                        "days and the extended general conditions that go with them.",
         fragnet={"activities": [F("F-0504A", "Relocate branch ducts and sprinkler drops for lowered corridor ceiling - addition", 3),
                                 F("F-0504B", "Frame, board and tape corridor soffits - addition (RFI-341)", 5)],
                  "relationships": [R("A1720", "F-0504A"), R("F-0504A", "F-0504B"), R("F-0504B", "A1760")]}),
    dict(id="CP-0505", stratum="heldout_concurrent", scenario="Held out: concurrent delay, Owner's separate vendor and controls sub rework, narrative without IDs",
         title="Access control integration by Owner's vendor (concurrent with controls retest)",
         cause_type="Other event", ref="Owner letter 2020-07-20", event="2020-07-20", notice_after=8, cp_after=14,
         party="owner", concurrent=True, claim=("fixed", 7), calendar=True, expect="critical", claim_check="matches",
         narrative="The Owner's separately contracted security vendor advised, through the Owner, that it cannot integrate the addition's "
                   "access control with the fire alarm door releases until functional performance testing is complete. Separately, CM's "
                   "controls subcontractor has told CM that its smoke-control sequence for the addition will need a correction and "
                   "retest pass after functional testing.",
         scope="The Owner's security vendor contract is outside CM's scope; Spec 23 09 93 requires the smoke-control sequence to pass "
               "functional testing before final inspection.",
         subs=[],
         time_narrative="Both items fall in the same window at the end of the job: after functional performance testing and controls is "
                        "finished and before the fire marshal and building official final inspections. The Owner's vendor needs 4 working "
                        "days to integrate and demonstrate the door releases, and the fire marshal will not start the final inspection "
                        "until that is done. Our controls sub's correction and retest of the smoke-control sequence also takes 4 working "
                        "days over the same period, and the final inspection would wait for it too. CM requests 7 calendar days of time "
                        "extension and extended general conditions for those days.",
         fragnet={"activities": [F("F-0505A", "Owner's security vendor: access control and door release integration - addition", 4),
                                 F("F-0505B", "Controls subcontractor: correct and retest smoke-control sequence - addition", 4)],
                  "relationships": [R("A2220", "F-0505A"), R("F-0505A", "A2250"), R("A2220", "F-0505B"), R("F-0505B", "A2250")]},
         concurrent_split={"owner": ["F-0505A"], "contractor": ["F-0505B"]}),
]
HELDOUT_IDS = [d["id"] for d in HELDOUT_DEFS]
ID_RE = re.compile(r"\b(?:A\d{4}|F-\d{4}[A-Z])\b")


def split_cases():
    """Fix the dev/test split from the seed before anything is computed: one test case per stratum."""
    rng = random.Random(SEED)
    split = {}
    for stratum in sorted(STRATA):
        members = sorted(STRATA[stratum])
        test = rng.choice(members)
        for m in members:
            split[m] = "test" if m == test else "dev"
    assert sum(v == "test" for v in split.values()) == 5 and len(split) == 15
    return split


def act_label(i, names):
    return i if i.startswith("F-") else f"{i} ({names[i]})"   # fragnet activities are named when introduced


def describe_fragnet(frag, names):
    """Plain-English logic of a fragnet, generated from the fragnet itself so the two always agree."""
    if not frag["activities"]:
        return "No new activities are added to the schedule."
    nm = dict(names)
    for a in frag["activities"]:
        nm[a["id"]] = a["name"]
    out = []
    for a in frag["activities"]:
        out.append(f"New activity {a['id']}, {a['name']}, takes {a['duration']} working day{'s' if a['duration'] != 1 else ''}.")
    for r in frag["relationships"]:
        p, s, L = act_label(r["pred"], nm), act_label(r["succ"], nm), r["lag"]
        after = f"{L} working days after " if L else ""
        if r["type"] == "FS":
            out.append(f"{s} cannot start until {after}{p} finishes." if L else f"{s} cannot start until {p} finishes.")
        elif r["type"] == "SS":
            out.append(f"{s} cannot start until {after}{p} starts.")
        elif r["type"] == "FF":
            out.append(f"{s} cannot finish until {after}{p} finishes.")
        else:
            out.append(f"{s} cannot finish until {after}{p} starts.")
    return " ".join(out)


def build_cases(sch, split, defs=CASE_DEFS):
    """Public case packages and answer-key rows. Held-out defs carry their own split, stratum and hand-written narrative."""
    names = {a["id"]: a["name"] for a in sch["activities"]}
    ids = set(names)
    status = {a["id"]: ("complete" if a["actual_finish"] else "active" if a["actual_start"] else "open") for a in sch["activities"]}
    public, key = [], []
    for d in defs:
        frag = d["fragnet"]
        for a in frag["activities"]:
            assert a["id"].startswith("F-" + d["id"][3:]), a["id"]
        for r in frag["relationships"]:
            for end in ("pred", "succ"):
                x = r[end]
                assert x.startswith("F-") or x in ids, (d["id"], x)
            if r["succ"] in ids:
                assert status[r["succ"]] == "open", (d["id"], "fragnet drives a started activity", r["succ"])
        t = C.tia(sch, frag)
        dw, dc = t["delay_workdays"], t["delay_calendar_days"]
        # the design intent must match what the CPM says
        if d["expect"] == "critical":
            assert dw > 0 and t["fragnet_critical"], (d["id"], t)
        elif d["expect"] == "partial":
            assert 0 < dw < sum(a["duration"] for a in frag["activities"]) and t["fragnet_critical"], (d["id"], t)
        elif d["expect"] in ("absorbed", "none"):
            assert dw == 0 and not t["fragnet_critical"], (d["id"], t)
        conc = None
        if d["concurrent"]:
            parts = {}
            for who, fids in d["concurrent_split"].items():
                sub_frag = {"activities": [a for a in frag["activities"] if a["id"] in fids],
                            "relationships": [r for r in frag["relationships"] if r["pred"] in fids or r["succ"] in fids]}
                parts[who] = C.tia(sch, sub_frag)["delay_workdays"]
            assert parts["owner"] > 0 and parts["contractor"] > 0, (d["id"], parts)
            assert parts["owner"] == parts["contractor"] == dw, (d["id"], parts, dw)
            conc = {"delay_workdays_owner_part_alone": parts["owner"], "delay_workdays_contractor_part_alone": parts["contractor"]}

        mode = d["claim"][0]
        if mode == "accurate":
            claimed = dc if d["calendar"] else dw
        elif mode == "fixed":
            claimed = d["claim"][1]
        else:
            claimed = 0
        computed_in_claim_units = dc if d["calendar"] else dw
        padded = claimed > computed_in_claim_units
        if "claim_check" in d:      # held-out cases state the claim design explicitly
            assert {"matches": claimed == computed_in_claim_units > 0,
                    "padded": claimed > computed_in_claim_units > 0,
                    "absorbed": claimed > 0 and dw == 0}[d["claim_check"]], (d["id"], d["claim_check"], claimed, dc, dw)
        if d["party"] == "contractor" or claimed == 0 or dw == 0:
            ext = 0
        elif claimed >= computed_in_claim_units:
            ext = dc
        else:
            assert d["calendar"], "under-claims are only modeled in calendar days"
            ext = claimed
        compensable = ext > 0 and d["party"] in ("owner", "architect") and not d["concurrent"]
        cost = ext * SGC_DAILY_A if compensable else 0

        # what the CM puts on its cover sheet: extended SGC on every day it claims when it says Owner/Architect caused it
        money_days = claimed if d["party"] in ("owner", "architect") else 0
        cm_lines = d.get("cm", [])
        notice = (date.fromisoformat(d["event"]) + timedelta(days=d["notice_after"])).isoformat()
        submitted = (date.fromisoformat(notice) + timedelta(days=d["cp_after"])).isoformat()
        rule = NOTICE_RULE[d["cause_type"]]
        due = notice_due(d["event"], rule)
        assert notice <= due, (d["id"], notice, due)          # every notice is timely; the time question stands alone
        unit = "calendar" if d["calendar"] else "working"
        claim_txt = (f"CM requests {claimed} {unit} days of time extension"
                     + (" and extended general conditions for those days." if money_days else ", time only.")
                     if claimed else "CM requests no extension of time.")
        if "time_narrative" in d:
            time_narr = d["time_narrative"]
            assert str(claimed) in time_narr and unit in time_narr, (d["id"], "narrative must state the claim")
        else:
            time_narr = f"{d['context']} {describe_fragnet(frag, names)} {claim_txt}"
        pkg = {
            "id": d["id"], "title": d["title"],
            "cause": {"type": d["cause_type"], "reference": d["ref"], "event_date": d["event"]},
            "notice_date": notice, "cp_submitted": submitted,
            "narrative": d["narrative"], "scope_context": d["scope"],
            "subcontractor_quotes": d["subs"], "cm_lines": cm_lines,
            "time_impact_days": claimed,
            "cover_sheet": cover(d["subs"], cm_lines, money_days),
            "backup_attached": ["cause document"] + (["subcontractor quotes with breakdowns"] if d["subs"] else [])
                               + (["labor timesheets", "equipment daily logs"] if cm_lines else [])
                               + (["time impact narrative", "schedule update 2020-06-01"] if claimed else []),
            "time": {"claimed_days": claimed, "claimed_calendar": d["calendar"], "narrative": time_narr,
                     "cause_party": d["party"], "concurrent": d["concurrent"]},
            "fragnet_truth": frag,
        }
        public.append(pkg)

        if d["party"] == "contractor":
            why = (f"Contractor-caused; critical-path delay of {dc} calendar days ({dw} working) but no extension under 3.4." if dw else
                   f"Contractor-caused and absorbed by float (least float left {min(t['fragnet_float'].values())} working days); "
                   f"no extension under 3.4 for the {claimed}-day claim.")
        elif dw == 0:
            why = ("No time claimed and no schedule impact." if not frag["activities"] else
                   f"Fragnet absorbed by float (least float left {min(t['fragnet_float'].values())} working days); delay 0"
                   + (f", so the {claimed}-day claim is not supported." if claimed else "; no time claimed."))
        elif d["concurrent"]:
            why = f"Owner and contractor delays are concurrent ({dw} working days each); {ext} days of time, no money under 6.5.6."
        else:
            basis = "matches the claim" if not padded and claimed == computed_in_claim_units else f"claim of {claimed} {unit} days is padded"
            pay = {"owner": "Owner-caused, compensable", "architect": "Architect-caused, compensable under 6.5.6",
                   "neither": "weather, time only"}[d["party"]]
            why = f"Critical-path delay of {dc} calendar days ({dw} working); {basis}; {pay}."
        k = {"id": d["id"], "scenario": d["scenario"],
             "stratum": d.get("stratum") or next(s for s, m in STRATA.items() if d["id"] in m),
             "split": "heldout" if d["id"] in HELDOUT_IDS else split[d["id"]], "cause_party": d["party"], "concurrent": d["concurrent"],
             "claimed_days": claimed, "claimed_calendar": d["calendar"],
             "before_finish": t["before_finish"], "after_finish": t["after_finish"],
             "delay_workdays": dw, "delay_calendar_days": dc, "fragnet_critical": t["fragnet_critical"],
             "fragnet_float": t["fragnet_float"], "driving_path": t["driving_path"],
             "padded": padded, "extension_days_allowed": ext, "compensable": compensable,
             "daily_rate": SGC_DAILY_A, "expected_cost": cost,
             "cm_requested_time_cost": pkg["cover_sheet"]["extended_sgc_time"],
             "notice_rule": rule, "notice_due": due, "notice_timely": True, "why": why}
        if conc:
            k.update(conc)
        key.append(k)
    return public, key


# ---------------------------------------------------------------------------- CP PDFs
def m(x):
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def cp_pdf(cp, path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    H, B, Sx = ss["Heading2"], ss["BodyText"], ss["Heading4"]

    def table(rows, widths, bold_last=False):
        t = Table(rows, colWidths=widths)
        st = [("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
              ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black), ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.lightgrey),
              ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        if bold_last:
            st += [("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9), ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black)]
        t.setStyle(TableStyle(st))
        return t

    c, tm = cp["cover_sheet"], cp["time"]
    party_words = {"owner": "Owner", "architect": "Architect", "contractor": "CM or its subcontractor", "neither": "Neither party (weather)"}
    el = [Paragraph(f"CHANGE PROPOSAL {cp['id']}", H),
          Paragraph("Project: Sample school modernization (synthetic test document). From: Sample GC/CM, to: Owner's Representative.", B),
          Paragraph(f"<b>Title:</b> {escape(cp['title'])}", B), Spacer(1, 8), Paragraph("Cause", Sx),
          table([["Item", "Detail"], ["Type of cause", cp["cause"]["type"]], ["Reference", cp["cause"]["reference"]],
                 ["Date of the event", cp["cause"]["event_date"]], ["Date written notice was given", cp["notice_date"]],
                 ["Date this proposal was submitted", cp["cp_submitted"]]], [2.6 * inch, 4.2 * inch]),
          Spacer(1, 6), Paragraph(escape(cp["narrative"]), B), Spacer(1, 8), Paragraph("Time impact", Sx),
          table([["Item", "Detail"],
                 ["Time extension requested", f"{tm['claimed_days']} {'calendar' if tm['claimed_calendar'] else 'working'} days"],
                 ["Cause of delay (CM's position)", party_words[tm["cause_party"]]],
                 ["Concurrent delay", "yes" if tm["concurrent"] else "none stated"],
                 ["Schedule basis", "Schedule update, data date 2020-06-01"]], [2.6 * inch, 4.2 * inch]),
          Spacer(1, 4), Paragraph("<b>Time impact narrative.</b> " + escape(tm["narrative"]), B),
          Spacer(1, 10), Paragraph("Cover sheet", Sx)]
    rows = [["Line", "Amount"], ["CM direct costs (CM labor, material, equipment)", m(c["cm_direct_costs"])],
            ["Subcontractor quotes", m(c["subcontractor_quotes"])],
            [Paragraph(f"CM Fee at {c['fee_rate'] * 100:g}%, applied to: {', '.join(c['fee_applied_to'])}", B), m(c["fee"])],
            ["Extended general conditions (time)", m(c["extended_sgc_time"])], ["TOTAL REQUESTED", m(c["total_requested"])]]
    el += [table(rows, [5.2 * inch, 1.6 * inch], bold_last=True), Spacer(1, 6),
           Paragraph(f"Backup attached: {', '.join(cp['backup_attached'])}.", B)]
    for q in cp["subcontractor_quotes"]:
        el += [PageBreak(), Paragraph(f"Subcontractor quote: {escape(q['firm'])} ({escape(q['trade'])})", H)]
        rws = [["Item", "Qty", "Unit", "Rate", "Amount"]] + [[l["desc"], f"{l['qty']:g}", l["unit"], m(l["rate"]), m(l["amount"])] for l in q["lines"]]
        el.append(table(rws, [3.0 * inch, 0.7 * inch, 0.6 * inch, 1.1 * inch, 1.4 * inch]))
        own_pct = 100 * q["markup_on_own"] / q["own_direct"] if q["own_direct"] else 0
        rws = [["Summary", "Amount"], ["Cost of own work before markup", m(q["own_direct"])], [f"Markup on own work ({own_pct:g}%)", m(q["markup_on_own"])]]
        for l in q["lower_tier"]:
            rws.append([f"Lower-tier subcontractor: {l['firm']} ({l['scope']})", m(l["amount"])])
        if q["lower_tier_total"]:
            rws.append([f"Markup on lower-tier work ({100 * q['markup_on_lower_tier'] / q['lower_tier_total']:g}%)", m(q["markup_on_lower_tier"])])
        rws.append(["QUOTE TOTAL", m(q["quote_total"])])
        el += [Spacer(1, 8), table(rws, [5.2 * inch, 1.6 * inch], bold_last=True)]
    if cp["cm_lines"]:
        el += [PageBreak(), Paragraph("CM direct costs, detail", H),
               table([["Item", "Amount"]] + [[l["desc"], m(l["amount"])] for l in cp["cm_lines"]], [5.2 * inch, 1.6 * inch])]
    SimpleDocTemplate(str(path), pagesize=letter, title=f"{cp['id']} {cp['title']}", author="ClauseStream synthetic data",
                      leftMargin=0.8 * inch, rightMargin=0.8 * inch, invariant=1).build(el)


# ============================================================================ verification
def rel_set(model):
    return sorted((r["pred"], r["succ"], r["type"], r["lag"]) for r in model["relationships"])


def verify(sch, res, cases, key, terms):
    report = []
    n_act, n_rel = len(sch["activities"]), len(sch["relationships"])
    base_rels = rel_set(sch)
    durs = {a["id"]: a["duration"] for a in sch["activities"]}

    x = read_xer(DATA / "schedule.xer")
    assert x["_tables"]["TASK"] == n_act and x["_tables"]["TASKPRED"] == n_rel, x["_tables"]
    assert rel_set(x) == base_rels and {a["id"]: a["duration"] for a in x["activities"]} == durs
    assert x["calendar"]["holidays"] == sorted(sch["calendar"]["holidays"])
    assert C.cpm(x)["finish_date"] == res["finish_date"]
    report.append(f"XER: {n_act} TASK, {n_rel} TASKPRED, {len(x['calendar']['holidays'])} holidays; relationships, durations "
                  f"and CPM finish {res['finish_date']} match")

    xm = read_mspdi(DATA / "schedule.xml")
    assert len(xm["activities"]) == n_act and rel_set(xm) == base_rels
    assert {a["id"]: a["duration"] for a in xm["activities"]} == durs
    assert xm["calendar"]["holidays"] == sorted(sch["calendar"]["holidays"])
    assert C.cpm(xm)["finish_date"] == res["finish_date"]
    report.append(f"MSPDI XML: {n_act} tasks (+{xm['_summary_tasks']} summary tasks), {n_rel} links; CPM finish matches")

    with open(DATA / "schedule.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    cm = rows_to_model(rows[0], rows[1:], sch["start"], sch["data_date"], sch["calendar"]["holidays"])
    for a in cm["activities"]:
        a["constraint"] = next(b["constraint"] for b in sch["activities"] if b["id"] == a["id"])  # CSV has no constraint column
    assert len(cm["activities"]) == n_act and rel_set(cm) == base_rels
    assert C.cpm(cm)["finish_date"] == res["finish_date"]
    report.append(f"CSV: {n_act} rows, predecessors re-parse to the same {n_rel} relationships; CPM finish matches")

    from openpyxl import load_workbook
    ws = load_workbook(DATA / "schedule.xlsx").active
    xrows = [[(v.date().isoformat() if isinstance(v, datetime) else ("" if v is None else v)) for v in r] for r in ws.iter_rows(values_only=True)]
    assert [[str(v) for v in r] for r in xrows] == [[str(v) for v in r] for r in rows], "xlsx differs from csv"
    report.append(f"XLSX: {len(xrows) - 1} rows identical to the CSV")

    with open(DATA / "schedule_nologic.csv", newline="", encoding="utf-8") as f:
        nrows = list(csv.reader(f))
    assert "Predecessors" not in nrows[0] and len(nrows) - 1 == n_act
    report.append(f"No-logic CSV: {n_act} rows, no Predecessors column")

    try:
        from pypdf import PdfReader
        txt = "".join(p.extract_text() for p in PdfReader(str(DATA / "schedule.pdf")).pages)
        missing = [a["id"] for a in sch["activities"] if a["id"] not in txt]
        assert not missing, missing
        assert "FS" not in re.findall(r"\bA\d{4}(FS|SS|FF|SF)", txt)
        bt = "".join(p.extract_text() for p in PdfReader(str(DATA / "contract_b.pdf")).pages)
        for k, t in terms["contracts"]["B"]["terms"].items():
            head = re.sub(r"\s+", " ", t["quote"][:40])
            assert head in re.sub(r"\s+", " ", bt), (k, head)
        report.append("PDFs: schedule.pdf text has all activity ids and no logic; contract_b.pdf text holds every quote's start")
        ct = re.sub(r"\s+", " ", "".join(p.extract_text() for p in PdfReader(str(DATA / "contract_c.pdf")).pages))
        for k, t in terms["contracts"]["C"]["terms"].items():
            head = re.sub(r"\s+", " ", t["quote"][:40])
            assert head in ct, ("C", k, head)
        report.append("Contract C PDF text holds every quote's start")
    except ImportError:
        report.append("PDFs: pypdf not installed; text check skipped")

    ids = {a["id"] for a in sch["activities"]}
    for cp in cases:
        fr = cp["fragnet_truth"]
        fids = {a["id"] for a in fr["activities"]}
        assert all(i.startswith("F-") for i in fids)
        for r in fr["relationships"]:
            assert (r["pred"] in ids or r["pred"] in fids) and (r["succ"] in ids or r["succ"] in fids)
        if fids:
            assert any(r["pred"] in ids for r in fr["relationships"]) and any(r["succ"] in ids for r in fr["relationships"]), cp["id"]
        narr = cp["time"]["narrative"]
        if cp["id"] in HELDOUT_IDS and not ID_RE.search(narr):
            # ID-free held-out narrative: every fragnet duration must still be stated, and no schedule or fragnet ID named
            for a in fr["activities"]:
                assert f"{a['duration']} working days" in narr, (cp["id"], a["id"])
        else:
            for a in fr["activities"]:
                assert a["id"] in narr and a["name"] in narr, cp["id"]
    held = [cp for cp in cases if cp["id"] in HELDOUT_IDS]
    id_free = [cp["id"] for cp in held if not ID_RE.search(cp["time"]["narrative"])]
    assert len(held) == 5 and len(id_free) >= 3, id_free
    ids_open = {a["id"] for a in sch["activities"] if not a["actual_start"]}
    for cp in held:
        for r in cp["fragnet_truth"]["relationships"]:
            for end in ("pred", "succ"):
                assert r[end].startswith("F-") or r[end] in ids_open, (cp["id"], r[end], "held-out tie to a started activity")
    # recompute every key value from scratch
    for cp, k in zip(cases, key):
        t = C.tia(sch, cp["fragnet_truth"])
        assert (t["delay_workdays"], t["delay_calendar_days"], t["fragnet_critical"]) == (k["delay_workdays"], k["delay_calendar_days"], k["fragnet_critical"])
        assert k["expected_cost"] == (k["extension_days_allowed"] * SGC_DAILY_A if k["compensable"] else 0)
    report.append(f"Cases: {len(cases)} fragnets reference existing schedule ids, every F- activity appears in its narrative "
                  f"(held-out ID-free narratives {', '.join(id_free)} state every fragnet duration instead), "
                  "and every answer-key delay re-computes")
    report.append("Held-out fragnets tie only to activities not started at the data date")
    return report


# ============================================================================ DATA_NOTE
def data_note(sch, res, planned, key, report):
    tbl = ["| CP | Scenario | Cause | Claimed | Computed delay (cal / work) | Extension | Compensable | Expected cost | Split |",
           "|---|---|---|---|---|---|---|---|---|"]
    for k in key:
        unit = "cal" if k["claimed_calendar"] else "work"
        tbl.append(f"| {k['id']} | {k['scenario']} | {k['cause_party']}{' (concurrent)' if k['concurrent'] else ''} | "
                   f"{k['claimed_days']} {unit} | {k['delay_calendar_days']} / {k['delay_workdays']} | {k['extension_days_allowed']} | "
                   f"{'yes' if k['compensable'] else 'no'} | ${k['expected_cost']:,} | {k['split']} |")
    crit = [x for x in res["activities"] if x["critical"]]
    n_comp = sum(1 for a in sch["activities"] if a["actual_finish"])
    n_act = sum(1 for a in sch["activities"] if a["actual_start"] and not a["actual_finish"])
    types = {}
    for r in sch["relationships"]:
        types[r["type"]] = types.get(r["type"], 0) + 1
    lags = sum(1 for r in sch["relationships"] if r["lag"])
    words_c = len(re.findall(r"\b\w[\w'.,$%-]*\b", CONTRACT_C))
    return f"""# Demo 4 data note

## What is synthetic
Everything in this folder is synthetic test data written for INFO 492 C coursework. No real project, schedule, contract, firm, or person is represented.
- **Schedule.** A made-up school modernization and addition on contract A (`demo1/data/synthetic_contract.md`): Notice to Proceed {sch['start']}, contract Substantial Completion {contract_completion_date()} (540 calendar days), data date {sch['data_date']}.
- **Contract B** (`contract_b.md`, `contract_b.pdf`). A second invented GC/CM contract with different numbers from contract A (markup 8% / 4% / 12%, Fee 4.5% on CM direct costs and subcontractor quotes, 30% labor burden, owned equipment at 70% of Blue Book, $150,000 approval limit, 10-day notice except 21 days for other events, 420-day contract time, $1,800/day liquidated damages, $2,450/day extended general conditions, only Owner-caused critical-path delay compensable, concurrent delay gets time but no money). Each key term is stated once in prose. Unrelated numbers (insurance limits, retainage, payment days, warranty years, a fixed base Fee, CM Contingency) are there as distractors.
- **Change proposals.** 15 CPs (CP-0401 to CP-0415) on contract A, each with a time section, a plain-English time narrative, and the true fragnet.

## How it was built
Run `python3 demo4/build_data.py` from the repo root. It rebuilds every file here and stops on any failed check.
1. `schedule_src.py` lists {len(sch['activities'])} activities in {len(S.WBS)} WBS groups and their logic. `cpm_ref.py` (an independent Python CPM, standard library only; `python3 demo4/cpm_ref.py` runs its self-tests) schedules it as planned. The script then applies a few slips ({', '.join(f'{k} +{v}' for k, v in S.SLIPS.items())} working days) and records progress at the data date: {n_comp} activities complete and {n_act} in progress.
2. The updated schedule has {len(sch['relationships'])} relationships ({', '.join(f'{v} {k}' for k, v in sorted(types.items()))}; {lags} with lags), one SNET constraint (Owner furniture, A1890), and Washington State legal holidays for 2020 and 2021. Forecast Substantial Completion is {res['finish_date']} ({crit.__len__()} critical activities); the as-planned date was {planned['finish_date']}.
3. The same schedule is exported to P6 XER (CRLF line ends, cp1252, durations and lags in hours at 8 h/day, `PR_FS` etc.), MS Project MSPDI XML (activity ID in Text1 and UID = the number in the ID, summary tasks for the project and each WBS group, `LinkLag` in tenths of minutes = days x 4800), CSV and XLSX (with a `Predecessors` column like `A1010FS+2, A1020`, plus trailing Actual Start, Actual Finish and Remaining Duration columns), a printed Gantt PDF with no logic, and a CSV with no predecessors.
4. Each CP's `fragnet_truth` is run through `cpm_ref.tia` against the June 2020 update. The answer key's delay, `fragnet_critical`, `padded`, extension, compensability and cost all come from that run and from contract A's rules: extension only for non-contractor causes that delay the critical path (Section 3.4), capped at the days claimed; compensation only for Owner or Architect causes without concurrency, at $3,185 per day with no Fee (Sections 5.2 and 6.5.6). Claims marked "accurate" are set to the computed delay; other claims are fixed numbers, and the script asserts each case behaves as designed (critical, partly absorbed by float, or fully absorbed).
5. `contract_terms_key.json` holds the expected terms for both contracts. The script checks that every quote is a verbatim substring of its contract, that the value appears in the quote, that the section number is the paragraph holding the quote, and that each key number appears exactly once in contract B.

## Cases
{chr(10).join(tbl)}

"Expected cost" is only the time-related cost (allowed compensable days x the contract A daily rate). The pricing sections are simple and tie out; every notice is on time, so the time question stands alone.

## Dev/test split
The split is fixed by `random.Random({SEED})` before anything is computed. The 15 cases are grouped into 5 strata of 3 (critical-path accurate claims; off-critical claims; padded or partial-float claims; non-compensable causes; concurrent or no claim), and one case per stratum is drawn as test. That gives 10 dev and 5 test cases, with every stratum in both. Tune prompts and rules on dev only.

## Held-out set (contract C, CP-0501..0505)
Contracts A and B and CP-0401 to CP-0415 have been used to inspect failures, so they are no longer independent. This set was written **after** that evaluation, by a separate helper (an AI assistant working from this folder's formats and `cpm_ref.py`) that did **not** open the contract reader, the fragnet drafter, their test scripts, or `results/`. It is synthetic and AI-assisted, and it was not made easy or hard for any particular method; it is meant to read like ordinary project documents.
- **Contract C** (`contract_c.md`, `contract_c.pdf`, key under `contracts.C` in `contract_terms_key.json`, marked `"split": "heldout"`): a Washington middle-school HVAC replacement and seismic retrofit on a GC/CM (MACC) contract, {words_c} words, numbered "§ 9.4.3", with "District" and "Contractor" for Owner and CM and numbers spelled out ("twelve percent (12%)"). Key values: markup 12% / 6% / 17%; change-order Fee 3.75% (Section 9.4.3 says 4%, amended by Supplementary Condition 16.3, which governs under 1.2) on Contractor direct costs, subcontractor quotes and bond and insurance premiums; 35% labor burden; owned equipment at 80% of Blue Book; $100,000 approval limit; 5-day notice except 20 days for other events; 455 days; $2,200/day liquidated damages; $2,975/day extended general conditions (also repeated in Exhibit B; 5.3 governs); $1,412,750 general conditions; delay compensable for District, Architect or concealed-condition causes; concurrent delay gets full time with the extended general conditions apportioned. Whether an extension requires critical-path delay is **not stated** (key value null, with a note). Distractors sit near the real numbers: the 5.25% base Fee, a $750/day Phase 1 milestone rate, a $7,500 Field Order limit, a 50% standby rate, 60/40 savings, a 15% apprenticeship rule, and an Architect sentence in a non-compensable context (7.2).
- **CP-0501 to CP-0505** (in `cases.json` and `answer_key.json` with `"split": "heldout"`, strata `heldout_*`): five change proposals on the same June 2020 schedule, scored under contract A's rules exactly like the cases above. One critical Owner change, one Architect change absorbed by float, one padded claim with partial float use, one loose field-note narrative (Architect RFI, claimed in working days, mentions an unrelated RFI and later activities that are not tie-ins), and one concurrent Owner/contractor delay. The time narratives are written by hand; four of the five name no activity or fragnet IDs and describe the tie-in work in a superintendent's words. Every fragnet ties only to activities not started at the data date, and the answers come from `cpm_ref.tia` like the rest.
- **How to use it.** Run the reader and drafter on it once, after tuning is finished, and report it separately from dev/test. Once its failures are inspected it is no longer held out; write a new set rather than tuning on this one.

## Conventions the answer key depends on
- Day numbering follows the spec: an activity with ES = day 0 and duration 5 occupies working days 0-4 and EF = 5; its finish date is working day 4. Milestones are dated on working day EF - 1 (day 0 for the start milestone), so Substantial Completion sits on the last working day of the work that drives it.
- `delay_workdays` is the change in the project's last EF; `delay_calendar_days` is the change in the finish date, so a one-working-day slip across a weekend or holiday counts 3 or 4 calendar days.
- In-progress activities keep their actual start; their remaining duration runs from the data date. Fragnet activities are not started and cannot start before the data date.
- Float is measured to the forecast finish, not to the contract date, so the {(date.fromisoformat(contract_completion_date()) - date.fromisoformat(res['finish_date'])).days} calendar days between the forecast and the contract date are not treated as available float.
- Weather is treated as outside the CM's control, so it earns time but not money; contract A does not mention weather, which is a judgment call (contract B's Section 3.5 does).

## Verification (from the last build)
{chr(10).join('- ' + r for r in report)}

## Limits
- **Same author.** The schedule, contract B, cases, narratives and answer key were written by our team, the same people building the tool. No independent scheduler or contract reviewer checked them.
- **One update.** Every TIA uses the single June 2020 update, even for events later in June. A real AACE 52R-06 analysis would use the update just before each event.
- **Simplified progress.** No out-of-sequence progress, no resource leveling, one calendar, no retained-logic vs. progress-override choice beyond the rule above.
- **Narratives are generated from the fragnets**, with a hand-written lead-in, so they are cleaner and more explicit than a real CM's time narrative.
- **Exports are hand-built**, not saved from P6 or MS Project. They follow the published table and element names, but a real tool may write fields we omit.
- **Contract A's weather and concealed-condition treatment** is not spelled out in that contract; our labels state the assumption above.
"""


# ============================================================================ main
def main():
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "pdfs").mkdir(exist_ok=True)
    split = split_cases()                      # fixed before anything is computed

    sch, planned = build_schedule()
    res = C.cpm(sch)
    assert 70 <= len(sch["activities"]) <= 110
    assert res["finish_date"] <= contract_completion_date(), (res["finish_date"], contract_completion_date())
    assert not res["warnings"]
    dump_json(DATA / "schedule.json", sch)
    write_xer(sch, res, planned)
    write_mspdi(sch, res, planned)
    write_tables(sch, res)
    write_schedule_pdf(sch, res)

    (DATA / "contract_b.md").write_text(CONTRACT_B.lstrip(), encoding="utf-8")
    words = len(re.findall(r"\b\w[\w'.,$%-]*\b", CONTRACT_B))
    assert 2000 <= words <= 3500, words
    md_to_pdf(CONTRACT_B, DATA / "contract_b.pdf", "Contract B - synthetic GC/CM agreement")
    (DATA / "contract_c.md").write_text(CONTRACT_C.lstrip(), encoding="utf-8")
    words_c = len(re.findall(r"\b\w[\w'.,$%-]*\b", CONTRACT_C))
    assert 2500 <= words_c <= 3500, words_c
    md_to_pdf(CONTRACT_C, DATA / "contract_c.pdf", "Contract C - synthetic GC/CM contract (held out)")
    terms = terms_key()
    c_md = (DATA / "contract_c.md").read_text(encoding="utf-8")
    for k, t in terms["contracts"]["C"]["terms"].items():
        assert t["quote"] in c_md, ("contract_c.md", k)
    dump_json(DATA / "contract_terms_key.json", terms)

    cases, key = build_cases(sch, split)
    h_cases, h_key = build_cases(sch, split, HELDOUT_DEFS)
    cases, key = cases + h_cases, key + h_key
    meta = {"contract": "../../demo1/data/synthetic_contract.md", "schedule": "schedule.json", "generated_by": "demo4/build_data.py",
            "schedule_data_date": sch["data_date"], "calendar": "Washington State legal holidays 2020-2021", "synthetic": True,
            "heldout": "CP-0501..CP-0505 are held out (split 'heldout'): written after the dev/test evaluation by a helper that "
                       "did not see the reader or drafter code; same schedule and contract A rules. Do not tune on them."}
    dump_json(DATA / "cases.json", {"meta": meta, "cases": cases})
    dump_json(DATA / "answer_key.json", {"meta": dict(meta, seed=SEED, split_rule="one test case per stratum of 3, drawn with random.Random(seed)",
                                                      forecast_finish_before=res["finish_date"],
                                                      contract_substantial_completion=contract_completion_date(),
                                                      rules="contract A: 3.4 extension for non-CM critical-path delay; 6.5.6 money only for "
                                                            "Owner/Architect cause, not concurrent; 5.2 rate $3,185/day, no Fee"),
                                         "cases": key})

    by_id = {c["id"]: c for c in cases}
    picks = []
    for stratum in ("critical_accurate", "off_critical_claimed", "padded_partial_float", "concurrent_or_no_claim"):
        picks.append(next(i for i in sorted(STRATA[stratum]) if split[i] == "dev"))
    for old in (DATA / "pdfs").glob("*.pdf"):
        old.unlink()
    for cid in picks:
        slug = re.sub(r"[^a-z0-9]+", "-", by_id[cid]["title"].lower()).strip("-")[:40]
        cp_pdf(by_id[cid], DATA / "pdfs" / f"{cid}-{slug}.pdf")

    report = verify(sch, res, cases, key, terms)
    report.append(f"CP PDFs written for dev cases {', '.join(picks)}")
    report.append(f"Contract B: {words} words")
    report.append(f"Contract C (held out): {words_c} words; every key quote is verbatim in contract_c.md and holds its value")
    (DATA / "DATA_NOTE.md").write_text(data_note(sch, res, planned, key, report), encoding="utf-8")
    for r in report:
        print("ok -", r)
    print(f"{len(sch['activities'])} activities, {len(sch['relationships'])} relationships, finish {res['finish_date']} "
          f"(contract {contract_completion_date()}); {len(cases)} cases, split "
          f"{sum(k['split'] == 'dev' for k in key)} dev / {sum(k['split'] == 'test' for k in key)} test / "
          f"{sum(k['split'] == 'heldout' for k in key)} heldout")


if __name__ == "__main__":
    main()
