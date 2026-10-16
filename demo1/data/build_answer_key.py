"""Build data/answer_key.json for the synthetic GC/CM contract and verify it.

Every rule carries an `anchor`: a short exact phrase from the contract. The script
fails if any anchor is missing or appears more than once, so the key cannot drift
away from the contract text.
"""
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "synthetic_contract.md"
OUT = HERE / "answer_key.json"


def v(n, unit):
    return {"number": n, "unit": unit}


def money(n):
    return {"number": n, "unit": "USD"}


def pct(n):
    return {"number": n, "unit": "percent"}


# (type, sections, summary, value, anchor, core)
R = []


def add(t, secs, summary, value, anchor, core=True):
    R.append((t, secs, summary, value, anchor, core))


# ---- Article 1
add("precedence", ["1.2"], "Order of precedence: Modifications, Articles, Exhibits A-D, Exhibit E, Drawings/Specs; Exhibit E cannot shorten notice periods or lengthen response times.", None,
    "it does not shorten any notice period or lengthen any response time stated in the Articles")
add("interpretation", ["1.4"], "Time periods are calendar days unless stated otherwise.", None,
    "means calendar days unless stated otherwise")
add("interpretation", ["1.4"], "A period ending on a weekend or legal holiday ends the next business day.", None,
    "it ends on the next business day")

# ---- Article 2
add("documentation_requirement", ["2.2"], "CM must promptly report errors, inconsistencies, or omissions to the Architect as an RFI.", None,
    "shall promptly report to Architect, as an RFI, any error, inconsistency, or omission it discovers")
add("non_authorization", ["2.3"], "No RFI response, ASI, meeting minute, or oral direction authorizes added cost or time until a CO or CCD is issued.", None,
    "no RFI response, ASI, meeting minute, or oral direction authorizes added cost or time")
add("restriction", ["2.3"], "Work on a change without a CO or CCD is at the CM's risk.", None,
    "Work on a change without a CO or CCD is at")

# ---- Article 3
add("deadline", ["3.2"], "Substantial Completion within 540 days after Notice to Proceed.", v(540, "days"),
    "within 540 days after the Notice to Proceed")
add("deadline", ["3.2"], "Final Completion within 60 days after Substantial Completion.", v(60, "days"),
    "Final Completion within 60 days after Substantial Completion")
add("amount", ["3.3"], "Liquidated damages of $2,500 per day of delay.", money(2500),
    "CM shall pay Owner $2,500 for each day of delay")
add("restriction", ["3.4"], "Contract Time is extended only by Change Order.", None,
    "Contract Time is extended only by CO")
add("restriction", ["3.4"], "A time extension requires that notice was given under Section 6.2.", None,
    "only if CM has given notice under Section 6.2")

# ---- Article 4
add("cap", ["4.1"], "GMP is $26,240,507; CM pays any cost that would exceed it unless a CO adjusts the GMP.", money(26240507),
    "CM shall pay any cost that would cause the GMP to be exceeded")
add("restriction", ["4.2"], "Savings in the GMP belong to the Owner.", None,
    "Any savings in the GMP belong to Owner", False)
add("amount", ["4.3"], "CM Contingency amount.", money(338007),
    "The CM Contingency is $338,007")
add("restriction", ["4.3"], "CM Contingency only for costs within CM's reasonable control.", None,
    "may use it only for costs within CM")
add("approval_authority", ["4.3"], "Owner's written approval is required before a contingency cost is incurred.", None,
    "before the cost is incurred")
add("fee_exclusion", ["4.3"], "CM Contingency may not be used for Owner-requested changes or RFI/ASI changes.", None,
    "The CM Contingency may not be used for Owner-requested changes")
add("restriction", ["4.4"], "GMP is adjusted only by Change Order.", None,
    "The GMP is adjusted only by CO")

# ---- Article 5
add("fee_rate", ["5.1"], "CM Fee is 5% of Subcontract Work plus SPW ($1,122,500).", pct(5),
    "is 5% of the sum of the Subcontract Work and SPW")
add("restriction", ["5.1"], "The Fee is fixed and changes only as stated in Article 6.", None,
    "The Fee is fixed and changes only as stated in Article 6")
add("amount", ["5.2"], "Specified General Conditions amount.", money(1720000),
    "SGC is $1,720,000")
add("amount", ["5.2"], "SGC increases only by CO for a time extension, at $3,185 per day.", money(3185),
    "SGC may be increased only by CO for an extension of Contract Time, at a daily rate of $3,185 per day")
add("fee_exclusion", ["5.2"], "No Fee is added to SGC.", None,
    "No Fee is added to SGC")
add("amount", ["5.3"], "Negotiated Support Services amount.", money(610000),
    "NSS is $610,000")
add("fee_exclusion", ["5.3"], "No Fee is added to NSS, and NSS changes only by CO.", None,
    "No Fee is added to NSS, and NSS changes only by CO")
add("pricing_input", ["5.4"], "CM labor carries a fixed burden of 32% of direct wages.", pct(32),
    "a fixed labor burden of 32% of direct wages")
add("pricing_input", ["5.4"], "Bond and insurance premiums, B&O taxes, and permit fees are reimbursable at actual cost.", None,
    "bond and insurance premiums at actual cost, Washington B&O taxes at actual cost, and permit fees")
add("non_chargeable_cost", ["5.5"], "Home office overhead, estimating, accounting, purchasing, and executive salaries are covered by the Fee and not billed separately.", None,
    "home office overhead; estimating, accounting, and purchasing")
add("non_chargeable_cost", ["5.5"], "Supervisory/management positions in Exhibit C, field office, and project vehicles are covered by Fee/SGC.", None,
    "the supervisory and management positions listed in Exhibit C; field office and project vehicles")
add("non_chargeable_cost", ["5.5"], "Hand tools and small tools under $1,000 per item are not billable.", money(1000),
    "hand tools and small tools under $1,000 per item")
add("non_chargeable_cost", ["5.5"], "The cost of preparing, pricing, and negotiating Change Proposals is not billable.", None,
    "the cost of preparing, pricing, and negotiating Change Proposals")
add("cap", ["5.6"], "Self-performed work may not exceed 30% of Subcontract Work plus SPW.", pct(30),
    "SPW shall not exceed 30% of the Subcontract Work and SPW combined")
add("restriction", ["5.6"], "CM may self-perform only trades where its sealed bid was the lowest responsive bid.", None,
    "CM may self-perform only trades for which its sealed bid was the lowest responsive bid")
add("documentation_requirement", ["5.6"], "CM reports the running SPW percentage with each pay application.", None,
    "shall report the running SPW percentage with each Application for Payment")
add("restriction", ["5.7"], "CM must competitively bid all Subcontract Work.", None,
    "CM shall competitively bid all Subcontract Work")
add("notice_window", ["5.7"], "At least 10 days' written notice to Owner before awarding a subcontract to a related firm.", v(10, "days"),
    "written notice before awarding any subcontract to a firm related to CM")

# ---- Article 6
add("notice_window", ["6.2(a)"], "Notice of Potential Change within 7 days after receiving an RFI response, ASI, or submittal return that CM believes changes cost or time.", v(7, "days"),
    "7 days after CM receives an RFI response, ASI, or submittal return that CM believes changes cost or time")
add("notice_window", ["6.2(b)"], "Notice within 7 days after a written or oral direction from Owner or Architect that CM believes is a change.", v(7, "days"),
    "7 days after CM receives a written or oral direction from Owner or Architect that CM believes is a change")
add("notice_window", ["6.2(c)"], "Concealed conditions: notice before disturbing the condition and within 7 days after first observing it.", v(7, "days"),
    "before disturbing the condition, and no later than 7 days after first observing it")
add("notice_window", ["6.2(d)"], "Any other event: notice within 14 days after CM first knew or should have known.", v(14, "days"),
    "14 days after CM first knew or should have known of any other event that may increase cost or time")
add("documentation_requirement", ["6.2"], "Notice must describe the event, identify the document or direction, and give a preliminary cost and time estimate.", None,
    "give a preliminary estimate of cost and time")
add("waiver_consequence", ["6.2"], "Late notice waives adjustment for costs incurred before notice and may waive adjustment of time.", None,
    "CM waives any adjustment for costs incurred before notice is given and may waive any adjustment of time")
add("deadline", ["6.3"], "CM-initiated Change Proposal due within 21 days after the notice.", v(21, "days"),
    "CM shall submit a CP within 21 days")
add("deadline", ["6.3", "Exhibit E 01 26 00"], "After an Architect Proposal Request, CP due within 14 days after receipt.", v(14, "days"),
    "CM shall submit a CP within 14 days after receiving it")
add("documentation_requirement", ["6.3"], "CP must reference the originating RFI/ASI/direction/CCD and the notice date.", None,
    "reference the RFI, ASI, direction, or CCD that caused it, and the notice date")
add("documentation_requirement", ["6.3"], "CP must break down labor hours and rates, materials, equipment, subcontractor pricing, markup, and Fee.", None,
    "give a breakdown of labor hours and rates, materials, equipment, subcontractor pricing, markup, and Fee")
add("documentation_requirement", ["6.3"], "CP must include subcontractor quotes and signed T&M tags for time-and-material work.", None,
    "include subcontractor quotes and signed T&M tags for any time-and-material work")
add("documentation_requirement", ["6.3"], "CP must state any claimed time impact in days.", None,
    "state any claimed time impact in days")
add("response_time", ["6.4"], "Owner (through Architect) responds to a complete CP within 14 days after receipt.", v(14, "days"),
    "shall respond to a complete CP within 14 days after receipt")
add("response_time", ["6.4"], "An incomplete CP is returned within 7 days with missing items identified.", v(7, "days"),
    "An incomplete CP shall be returned within 7 days with the missing items identified")
add("non_authorization", ["6.4"], "Silence is not acceptance of a CP.", None,
    "Silence is not acceptance")
add("claim_rule", ["6.4"], "If no response after 14 days, CM may send a written reminder and treat the lack of response as a basis for a claim.", v(14, "days"),
    "If Owner has not responded after 14 days, CM may send a written reminder")
add("markup_limit", ["6.5.2"], "Subcontractor overhead and profit up to 10% on its own direct cost.", pct(10),
    "overhead and profit of up to 10% on its own direct cost")
add("markup_limit", ["6.5.2"], "Subcontractor markup up to 5% on lower-tier subcontractor work.", pct(5),
    "up to 5% on the cost of work performed by its lower-tier subcontractors")
add("cap", ["6.5.2"], "Total markup on any portion of the work may not exceed 15%.", pct(15),
    "Total markup on any portion of the work shall not exceed 15%")
add("fee_rate", ["6.5.3"], "CM may add a 5% Fee to the direct costs and subcontractor markups of a change.", pct(5),
    "CM may add a Fee of 5% to the direct costs and subcontractor markups of a change")
add("fee_exclusion", ["6.5.3"], "No Fee on NSS, SGC adjustments, bond and insurance premiums, B&O taxes, or permit fees.", None,
    "No Fee is added to NSS, SGC adjustments, bond and insurance premiums, B&O taxes, or permit fees")
add("fee_rate", ["6.5.3"], "On deductive changes the Fee is reduced at the same 5% rate.", pct(5),
    "On deductive changes, the Fee is reduced at the same 5% rate")
add("equipment_rule", ["6.5.4", "Exhibit B"], "Equipment listed as included in SGC (Exhibit B) may not be charged to a CP.", None,
    "Equipment listed as included in SGC in Exhibit B shall not be charged to a CP")
add("equipment_rule", ["6.5.4"], "CM-owned equipment is charged at 75% of the current published Blue Book rental rate.", pct(75),
    "is charged at 75% of the current published Blue Book rental rate")
add("equipment_rule", ["6.5.4"], "Rented equipment is charged at invoiced cost with no markup other than the Fee.", None,
    "rented equipment at the invoiced cost with no markup other than the Fee")
add("equipment_rule", ["6.5.4"], "Equipment is charged only for hours actually used on the changed Work, supported by daily logs.", None,
    "Equipment is charged only for the hours it is actually used on the changed Work, supported by daily logs")
add("equipment_rule", ["6.5.4"], "Idle equipment is charged at 50% of the rate, only when idle time is caused by the change.", pct(50),
    "Idle equipment is charged at 50% of the applicable rate and only when the idle time is caused by the change")
add("non_chargeable_cost", ["6.5.5"], "Items in Section 5.5 may not be included in a CP.", None,
    "The items in Section 5.5 shall not be included in a CP")
add("restriction", ["6.5.6"], "Time extension is compensated only for Owner/Architect-caused delays on the critical path.", None,
    "A time extension is compensated only for delays caused by Owner or Architect that are on the critical path")
add("fee_exclusion", ["6.5.6"], "Compensable delay is priced at the SGC daily rate with no Fee.", None,
    "using the SGC daily rate in Section 5.2 and with no Fee")
add("restriction", ["6.5.6"], "Concurrent delays receive time but no compensation.", None,
    "Delays with concurrent causes receive time but no compensation")
add("deadline", ["6.5.7"], "T&M tags are submitted within 3 business days after the work is performed.", v(3, "business days"),
    "T&M tags shall be submitted within 3 business days after the work is performed")
add("documentation_requirement", ["6.5.7"], "T&M tags must be signed by the CM's superintendent and Owner's Representative; unsigned tags are not accepted as backup.", None,
    "Unsigned tags are not accepted as backup")
add("process", ["6.6"], "Owner may issue a CCD directing work to proceed before the price is agreed.", None,
    "Owner may issue a CCD directing CM to proceed with a change before the price is agreed")
add("deadline", ["6.6"], "After a CCD, CP due within 14 days.", v(14, "days"),
    "CM shall submit its CP within 14 days after receiving the CCD")
add("deadline", ["6.6"], "If not agreed within 30 days after the CP is submitted, cost is actual Cost of the Work plus Fee.", v(30, "days"),
    "If the parties have not agreed within 30 days after the CP is submitted")
add("pricing_input", ["6.6"], "Unagreed CCD cost is the actual Cost of the Work under Section 6.5 plus the Fee.", None,
    "the cost is determined as the actual Cost of the Work calculated under Section 6.5, plus the Fee")
add("deadline", ["6.6"], "CCD is converted to a CO within 45 days after the price is agreed.", v(45, "days"),
    "Within 45 days after the price is agreed, the CCD shall be converted to a CO")
add("approval_authority", ["6.7"], "A CO is effective only when signed by Owner, Architect, and CM.", None,
    "A CO is effective only when signed by Owner, Architect, and CM")
add("approval_authority", ["6.7", "Exhibit D"], "Owner's Representative may approve a CO of up to $250,000.", money(250000),
    "approve a CO of up to $250,000")
add("approval_authority", ["6.7", "Exhibit D"], "COs above $250,000, or related changes totaling more than $250,000, require Board approval.", money(250000),
    "A CO above $250,000, or a series of related changes totaling more than $250,000")
add("notice_window", ["6.8"], "If CM believes an ASI changes cost or time, it gives notice under 6.2(a) before proceeding.", v(7, "days"),
    "it shall give notice under Section 6.2(a) before proceeding")
add("non_authorization", ["6.8"], "Proceeding with an ASI does not waive the right to notice if notice is timely.", None,
    "Proceeding with an ASI does not waive")
add("documentation_requirement", ["6.9"], "CM keeps a CP log numbered in sequence with notice date, submission date, amount, status, and originating document.", None,
    "CM shall keep a log of all CPs, numbered in sequence")
add("deadline", ["6.9"], "CP log is updated weekly and submitted with each pay application.", None,
    "CM shall update the log weekly and submit it with each Application for Payment")

# ---- Article 7
add("documentation_requirement", ["7.1", "Exhibit E 01 31 00"], "RFI must identify drawing sheets and spec sections, state the question, propose an answer, and give a needed-by date.", None,
    "identify the drawing sheets and specification sections involved")
add("process", ["7.2"], "Architect may return an RFI that was answered in the Contract Documents without a full response.", None,
    "Architect may return it without a full response")
add("amount", ["7.2"], "Architect review cost of $350 charged to CM for each such RFI beyond the tenth, deducted from the next pay application.", money(350),
    "each such RFI beyond the tenth shall be charged to CM at $350 per RFI")
add("response_time", ["7.3"], "Architect responds to each RFI within 10 days after receipt.", v(10, "days"),
    "Architect shall respond to each RFI within 10 days after receipt")
add("response_time", ["7.3"], "Critical Path RFIs are answered within 3 business days.", v(3, "business days"),
    "An RFI marked Critical Path shall be answered within 3 business days")
add("notice_window", ["7.3"], "If Architect cannot respond in time, it notifies CM within 5 days and gives a response date.", v(5, "days"),
    "it shall notify CM within 5 days and give the date a response will be provided")
add("non_authorization", ["7.4"], "An RFI response does not change the Contract Sum or Contract Time.", None,
    "An RFI response does not change the Contract Sum or Contract Time")
add("deadline", ["7.5"], "CM sends each RFI response to every affected subcontractor within 2 business days.", v(2, "business days"),
    "CM shall send each RFI response to every affected subcontractor within 2 business days")
add("documentation_requirement", ["7.5"], "CM keeps an RFI log, updated weekly.", None,
    "CM shall keep an RFI log, updated weekly")
add("process", ["7.6"], "If an RFI is unanswered after 10 days, CM may send a written follow-up.", v(10, "days"),
    "If an RFI is unanswered after 10 days, CM may send a written follow-up")
add("notice_window", ["7.6"], "If unanswered after 15 days, CM may give notice of a Potential Change under 6.2(d).", v(15, "days"),
    "If it is unanswered after 15 days, CM may give notice of a Potential Change under Section 6.2(d)")
add("non_authorization", ["7.7", "Exhibit E 01 31 00"], "Statements in meeting minutes are not notice under 6.2 and do not authorize changes unless repeated in a written notice, CO, or CCD.", None,
    "A statement in meeting minutes is not notice under Section 6.2")

# ---- Article 8
add("deadline", ["8.1"], "Submittal schedule due within 30 days after Notice to Proceed.", v(30, "days"),
    "CM shall submit a submittal schedule within 30 days after the Notice to Proceed")
add("response_time", ["8.2"], "Architect reviews each submittal within 14 days after receipt.", v(14, "days"),
    "Architect shall review each submittal within 14 days after receipt")
add("response_time", ["8.2"], "Architect reviews each resubmittal within 10 days.", v(10, "days"),
    "each resubmittal within 10 days")
add("process", ["8.2", "Exhibit E 01 33 00"], "CM reviews and stamps each submittal before sending it to the Architect.", None,
    "CM shall review and stamp each submittal")
add("deadline", ["8.3"], "CM tells affected subcontractors of Approved as Noted / Revise and Resubmit returns within 3 business days.", v(3, "business days"),
    "CM shall tell every affected subcontractor within 3 business days")
add("notice_window", ["8.3"], "If a submittal comment changes cost or time, CM gives notice under 6.2(a).", v(7, "days"),
    "If CM believes a comment changes cost or time, CM shall give notice under Section 6.2(a)")

# ---- Article 9
add("payment_term", ["9.1"], "Applications for Payment are submitted by the 25th of each month.", None,
    "by the 25th of each month")
add("documentation_requirement", ["9.1"], "Pay applications include the change log, SPW percentage, and lien waivers.", None,
    "with the change log, the SPW percentage, and lien waivers")
add("payment_term", ["9.2"], "Owner pays within 30 days after receiving a complete Application.", v(30, "days"),
    "within 30 days after receiving a complete Application")
add("payment_term", ["9.2"], "Overdue undisputed amounts bear interest at 1% per month.", pct(1),
    "Overdue undisputed amounts bear interest at 1% per month")
add("payment_term", ["9.3"], "Owner retains 5% of each progress payment.", pct(5),
    "Owner shall retain 5% of each progress payment")
add("restriction", ["9.4"], "A change may be billed only after a CO is executed or a CCD is issued.", None,
    "CM may bill a change only after a CO is executed or a CCD is issued")
add("payment_term", ["9.4"], "CCD work may be billed as costs are incurred, subject to adjustment.", None,
    "CCD work may be billed as costs are incurred")

# ---- Article 10
add("claim_rule", ["10.1"], "Claim for added cost or time must be made in writing within 21 days after the event.", v(21, "days"),
    "within 21 days after the event giving rise to it")
add("claim_rule", ["10.1"], "Or within 14 days after receiving Owner's response to a disputed CP, whichever applies.", v(14, "days"),
    "or within 14 days after CM receives")
add("waiver_consequence", ["10.1"], "A claim not made in time is waived.", None,
    "A claim not made in time is waived")
add("response_time", ["10.2"], "Owner responds to a claim within 30 days after receiving it.", v(30, "days"),
    "Owner shall respond to a claim within 30 days after receiving it")
add("process", ["10.3"], "Unresolved claims go to mediation, then King County Superior Court.", None,
    "Unresolved claims shall go to mediation", False)
add("restriction", ["10.3"], "CM continues the Work during any dispute.", None,
    "CM shall continue the Work during any dispute", False)

# ---- Article 11
add("audit_rule", ["11.1"], "CM keeps cost records at least 6 years after final payment.", v(6, "years"),
    "at least 6 years after final payment")
add("audit_rule", ["11.2"], "Charges found not allowable under Articles 5 and 6 are credited to Owner within 30 days after the audit report.", v(30, "days"),
    "shall be credited to Owner within 30 days after the audit report")
add("audit_rule", ["11.2"], "Owner may offset the credited amount against money owed to CM.", None,
    "Owner may offset the amount against money owed to CM")

# ---- Articles 12-14 (peripheral except notices)
add("amount", ["12.1"], "Payment and performance bonds each for 100% of the GMP.", pct(100),
    "payment and performance bonds each for 100% of the GMP", False)
add("amount", ["12.1"], "CGL insurance of at least $2,000,000 per occurrence and $4,000,000 aggregate.", money(2000000),
    "at least $2,000,000 per occurrence and $4,000,000 in the aggregate", False)
add("notice_window", ["13.1"], "Termination for cause if a material default is not cured within 7 days after written notice.", v(7, "days"),
    "fails to cure a material default within 7 days after written notice", False)
add("notice_window", ["13.2"], "Termination for convenience on 14 days' written notice.", v(14, "days"),
    "Owner may terminate for convenience on 14 days", False)
add("documentation_requirement", ["14.2"], "Notices must be in writing and sent to the representatives in Exhibit D.", None,
    "Notices shall be in writing and sent to the representatives in Exhibit D")
add("interpretation", ["14.2"], "A notice sent through the Owner's designated platform is received on the next business day.", None,
    "A notice sent through the project management platform designated by Owner is a written notice and is received on the next business day")

# ---- Exhibits
add("equipment_rule", ["Exhibit B"], "SGC-included equipment: field office and trailers, two project pickups, small tools under $1,000, signage, office computers.", None,
    "field office and trailers; two project pickup trucks")
add("equipment_rule", ["Exhibit B"], "Chargeable equipment includes owned equipment at 75% of Blue Book, rented at invoice, operator labor, and fuel at actual cost.", None,
    "operator labor under Section 5.4; fuel at actual cost")
add("equipment_rule", ["Exhibit B"], "Mobilization is chargeable only when the equipment would not otherwise be on site.", None,
    "Mobilization is chargeable only when the equipment would not otherwise be on site")
add("approval_authority", ["Exhibit D"], "The Architect cannot approve cost or time.", None,
    "cannot approve cost or time")
add("response_time", ["Exhibit E 01 26 00"], "Proposal Request: CP within 14 days or an explanation of why more time is needed.", v(14, "days"),
    "or within that time explain why more time is needed")
add("documentation_requirement", ["Exhibit E 01 26 00"], "A revised CP keeps its number with a letter suffix; CPs are numbered CP-0001, CP-0002, and so on.", None,
    "A revised CP keeps its number with a letter suffix")
add("documentation_requirement", ["Exhibit E 01 26 00"], "Every CP attaches the originating RFI/ASI/CCD, subcontractor quotes, equipment logs, and T&M tags.", None,
    "Every CP shall attach the RFI, ASI, or CCD that caused it")
add("documentation_requirement", ["Exhibit E 01 31 00"], "Critical Path RFIs state the activity affected and the date it will be delayed without an answer.", None,
    "shall state the activity affected and the date the activity will be delayed if no answer is received")
add("deadline", ["Exhibit E 01 31 00"], "Coordination meeting minutes are issued within 2 business days.", v(2, "business days"),
    "issue minutes within 2 business days")
add("process", ["Exhibit E 01 31 00"], "CM holds weekly coordination meetings with the Architect and Owner's Representative.", None,
    "CM shall hold weekly coordination meetings", False)
add("deadline", ["Exhibit E 01 33 00"], "Items with lead time over 12 weeks are flagged on the submittal schedule and submitted within 45 days after Notice to Proceed.", v(45, "days"),
    "Items with a lead time over 12 weeks shall be flagged on the submittal schedule and submitted within 45 days after the Notice to Proceed")

PITFALLS = [
    {"id": "P1", "name": "Similar clocks, different triggers",
     "note": "Several rules use the same number of days but start from different events. An extractor must record the trigger, not just the number. The 21-day CM-initiated CP (6.3) versus the 14-day Proposal Request CP (6.3, Exhibit E) is the main trap."},
    {"id": "P2", "name": "Rules split across documents",
     "note": "The CP deadline appears in Article 6 and Exhibit E; Equipment rules appear in 6.5.4 and Exhibit B; approval authority appears in 6.7 and Exhibit D. A match to either location counts."},
    {"id": "P3", "name": "Exceptions to the Fee",
     "note": "The 5% Fee applies to changes (6.5.3) except NSS, SGC adjustments, bond and insurance premiums, B&O taxes, and permit fees. An extractor that reports only the 5% misses the exception. These are the categories closest to the Webster audit findings."},
    {"id": "P4", "name": "Non-rules that look like rules",
     "note": "Meeting minutes are not notice (7.7), an RFI response does not authorize cost (7.4), and silence is not acceptance (6.4). These are negative rules. The extractor should not report them as notice windows or approvals."},
    {"id": "P5", "name": "Precedence",
     "note": "Exhibit E cannot shorten a notice period or lengthen a response time in the Articles (1.2). If an extractor reports a shorter or longer period from Exhibit E, it should flag the conflict."},
    {"id": "P6", "name": "Cross-references",
     "note": "Several rules depend on another section (6.5.5 refers to 5.5; 8.3 and 6.8 refer to 6.2(a); 6.5.6 refers to 5.2). Rules that only cross-reference should still be extracted with the target section."},
    {"id": "P7", "name": "Amounts that are facts, not rules",
     "note": "Exhibit A, B, and C line items are budget amounts, not rules. They are not in the key. Amounts that act as limits or rates (for example $3,185 per day, $350 per RFI, $250,000 approval limit) are in the key."},
]

SCORING = {
    "unit": "One rule per entry. A predicted rule matches a key entry when it cites one of the entry's sections, has the same type group, and carries the same value (numbers and units must match exactly; rules with no value match on section and meaning).",
    "recall": "matched key rules / key rules, reported for core rules and for all rules (claim 1 target: at least 85% of core rules).",
    "precision": "matched predicted rules / predicted rules.",
    "citation_validity": "share of predicted quotes that appear verbatim (after whitespace and punctuation normalization) in the contract text.",
    "type_groups": {
        "notice": ["notice_window"],
        "time": ["deadline", "response_time"],
        "money_rules": ["fee_rate", "fee_exclusion", "markup_limit", "cap", "amount", "pricing_input", "non_chargeable_cost", "equipment_rule", "payment_term"],
        "authority": ["approval_authority", "precedence", "non_authorization", "restriction"],
        "other": ["claim_rule", "waiver_consequence", "audit_rule", "documentation_requirement", "process", "interpretation"],
    },
    "note": "Type labels are a guide. When a predicted rule and a key rule describe the same requirement with a different type label, count it as a match and record the label difference separately.",
}


def normalize(text):
    text = text.replace("**", "").replace("*", "")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text)


def main():
    with open(CONTRACT, encoding="utf-8") as f:
        text = normalize(f.read())

    rules, problems = [], []
    for i, (t, secs, summary, value, anchor, core) in enumerate(R, start=1):
        a = normalize(anchor)
        count = text.count(a)
        if count != 1:
            problems.append((i, count, anchor))
        rules.append({
            "id": f"R{i:03d}",
            "type": t,
            "core": core,
            "sections": secs,
            "summary": summary,
            "value": value,
            "anchor": anchor,
        })

    if problems:
        print("ANCHOR PROBLEMS (rule number, occurrences, anchor):")
        for p in problems:
            print(" ", p)
        sys.exit(1)

    # Groups of rules that share the same number of days (confusable clocks)
    groups = defaultdict(list)
    for r in rules:
        val = r["value"]
        if val and val["unit"] in ("days", "business days"):
            groups[f'{val["number"]} {val["unit"]}'].append(r["id"])
    confusable = {k: ids for k, ids in groups.items() if len(ids) >= 3}

    by_type = defaultdict(int)
    for r in rules:
        by_type[r["type"]] += 1

    key = {
        "meta": {
            "contract_file": "synthetic_contract.md",
            "description": "Hand-checkable answer key for the synthetic GC/CM agreement. Used to score the rules extractor (Demo 1).",
            "status": "DRAFT: a teammate should read the contract and confirm each entry before scoring.",
            "total_rules": len(rules),
            "core_rules": sum(1 for r in rules if r["core"]),
            "peripheral_rules": sum(1 for r in rules if not r["core"]),
            "rules_by_type": dict(sorted(by_type.items())),
            "core_definition": "Core rules govern notice, response times, deadlines, pricing, fees, markups, equipment, change authority, payment, claims, and audit. Peripheral rules cover insurance, bonds, termination, dispute mechanics, and meeting cadence.",
        },
        "rules": rules,
        "confusable_clocks": confusable,
        "pitfalls": PITFALLS,
        "scoring": SCORING,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(key, f, indent=2, ensure_ascii=False)

    print(f"OK: {len(rules)} rules written to {OUT}")
    print("core:", key["meta"]["core_rules"], "peripheral:", key["meta"]["peripheral_rules"])
    print("by type:", dict(sorted(by_type.items())))
    print("confusable clocks:", confusable)


if __name__ == "__main__":
    main()
