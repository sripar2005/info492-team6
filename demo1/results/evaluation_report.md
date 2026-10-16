# Rules extractor evaluation

Model: `claude-sonnet-5-5`

**Claim 1 target:** at least 85.0% of core rules captured. **Result: 94.4% (117 of 124). Target met.**

| Measure | Result |
| --- | --- |
| Recall, core rules | 94.4% (117/124) |
| Recall, all rules | 94.7% (125/132) |
| Precision (extracted rules supported by the key) | 79.1% |
| Citation validity (quotes found verbatim) | 100.0% |
| Right text, wrong value | 3 |
| Type label agreement among found rules | 85.6% |
| Rules extracted | 158 |

## Recall on the contract's built-in traps

| Pitfall | Recall |
| --- | --- |
| fee_exclusions (pitfall P3) | 100.0% |
| negative_rules (pitfall P4) | 100.0% |
| confusable_clocks (pitfall P1) | 92.9% |

## Recall by rule type

| Type | Found | Total | Recall |
| --- | --- | --- | --- |
| amount | 6 | 8 | 75.0% |
| approval_authority | 5 | 5 | 100.0% |
| audit_rule | 3 | 3 | 100.0% |
| cap | 2 | 3 | 66.7% |
| claim_rule | 3 | 3 | 100.0% |
| deadline | 14 | 14 | 100.0% |
| documentation_requirement | 16 | 16 | 100.0% |
| equipment_rule | 7 | 8 | 87.5% |
| fee_exclusion | 5 | 5 | 100.0% |
| fee_rate | 3 | 3 | 100.0% |
| interpretation | 3 | 3 | 100.0% |
| markup_limit | 2 | 2 | 100.0% |
| non_authorization | 5 | 5 | 100.0% |
| non_chargeable_cost | 4 | 5 | 80.0% |
| notice_window | 9 | 11 | 81.8% |
| payment_term | 5 | 5 | 100.0% |
| precedence | 1 | 1 | 100.0% |
| pricing_input | 3 | 3 | 100.0% |
| process | 6 | 6 | 100.0% |
| response_time | 8 | 8 | 100.0% |
| restriction | 13 | 13 | 100.0% |
| waiver_consequence | 2 | 2 | 100.0% |

## Missed rules (4)

- R021 (amount, core, 5.2): Specified General Conditions amount.
- R024 (amount, core, 5.3): Negotiated Support Services amount.
- R029 (non_chargeable_cost, core, 5.5): Supervisory/management positions in Exhibit C, field office, and project vehicles are covered by Fee/SGC.
- R122 (equipment_rule, core, Exhibit B): SGC-included equipment: field office and trailers, two project pickups, small tools under $1,000, signage, office computers.

## Right text, wrong value (3)

- R012: GMP is $26,240,507; CM pays any cost that would exceed it unless a CO adjusts the GMP. | extracted value(s): None | key value: {'number': 26240507, 'unit': 'USD'}
- R078: If CM believes an ASI changes cost or time, it gives notice under 6.2(a) before proceeding. | extracted value(s): None | key value: {'number': 7, 'unit': 'days'}
- R099: If a submittal comment changes cost or time, CM gives notice under 6.2(a). | extracted value(s): None | key value: {'number': 7, 'unit': 'days'}

## Quotes not found in the contract (0)

None.

## Extracted rules not supported by the key (review: could be real rules the key missed, or errors) (33)

- E001 (precedence, 1.2): If Contract Documents conflict, they control in order: executed Modifications; Articles 1-14; Exhibits A-D; Exhibit E; Drawings and other Specifications.
- E006 (restriction, 2.2): CM is not responsible for errors in the Contract Documents unless it knowingly failed to report them.
- E010 (deadline, 3.1): CM must begin the Work on the date stated in the Notice to Proceed issued by Owner.
- E015 (restriction, 3.4): Extension is available only for delays outside CM's control shown on the critical path.
- E017 (cap, 4.1): The Guaranteed Maximum Price is $26,240,507, covering Cost of the Work, Fee, SGC, NSS, and CM Contingency.
- E018 (restriction, 4.1): CM must pay any cost that would cause the GMP to be exceeded unless a CO has adjusted the GMP.
- E027 (restriction, 5.2): SGC may be increased only by CO for an extension of Contract Time.
- E042 (process, 6.1): Changes are made only by Change Order, Construction Change Directive, or Architect's Supplemental Instruction.
- E059 (pricing_input, 6.5.1, 5.4, 6.5.4): Direct costs are labor with the fixed burden in Section 5.4, materials at actual cost net of discounts, equipment under 6.5.4, and subcontract costs.
- E075 (approval_authority, 6.5.7): T&M tags must be signed by CM's superintendent and Owner's Representative.
- E084 (restriction, 6.8): Architect's ASIs may not change cost or time.
- E085 (notice_window, 6.8, 6.2(a)): If CM believes an ASI will change cost or time, it must give notice under 6.2(a) before proceeding.
- E089 (process, 7.1): CM must submit RFIs on the form in Exhibit E.
- E091 (process, 7.2): CM must review the Contract Documents before submitting an RFI.
- E098 (process, 7.4, 6.2, 6.3): If CM believes an RFI response changes cost or time, it must follow Sections 6.2 and 6.3.
- E109 (process, 8.3, 6.2(a)): If CM believes a submittal comment changes cost or time, CM must give notice under Section 6.2(a).
- E117 (payment_term, 9.5): Final payment is due after Final Completion, receipt of all closeout documents, and lapse of statutory lien periods.
- E125 (audit_rule, 11.2): Owner or its auditor may audit CM's records at any time during the record retention period.
- E132 (payment_term, 13.2): On termination for convenience, Owner pays CM for Work performed and reasonable demobilization costs.
- E135 (waiver_consequence, 14.3): Owner's payment or failure to object does not waive any right under the Agreement.
- E136 (equipment_rule, Exhibit B): Field office and trailers, two pickup trucks, hand/power tools under $1,000 per item, temporary signage, and office computers and printers are included in SGC and never chargeable to a CP.
- E137 (equipment_rule, Exhibit B): CM-owned equipment used on changed Work is chargeable at 75% of the current Blue Book rate.
- E138 (equipment_rule, Exhibit B): Rented equipment is chargeable at invoice.
- E141 (fee_exclusion, Exhibit C): Negotiated Support Services carry no Fee.
- E142 (approval_authority, Exhibit D): Owner's Representative approves COs up to $250,000, issues CCDs, and receives notices.
- E143 (approval_authority, Exhibit D): Owner's Board of Directors approves COs above $250,000.
- E145 (approval_authority, Exhibit D): CM Project Manager submits notices, CPs, and RFIs and signs COs for CM.
- E146 (approval_authority, Exhibit D): CM Superintendent signs T&M tags and sends RFI responses to subcontractors.
- E150 (process, Exhibit E 01 26 00, 6.9): The CP log is submitted with each Application for Payment, as required by Section 6.9.
- E151 (documentation_requirement, Exhibit E 01 31 00): Each RFI must include unique number, date, sheet and spec references, question, CM's proposed answer, and needed-by date.
- E155 (non_authorization, Exhibit E 01 31 00, 7.7): Meeting minutes are not notices, consistent with Section 7.7.
- E156 (process, Exhibit E 01 33 00): Each submittal uses its specification section number and a sequence number.
- E158 (process, Exhibit E 01 33 00): CM must stamp each submittal before sending it to Architect, confirming compliance and coordination check.
