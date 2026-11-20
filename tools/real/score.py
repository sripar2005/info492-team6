# Scores the RFI responder runs (data/real/results/<model>/*.json) against the official published answers, by code only.
# Writes data/real/results/summary.json and prints a table.   python3 tools/real/score.py
#
# What is measured, and how:
#  1. Citations are real: the cited excerpt id was one the agent was given, and the quote appears word for word in it.
#  2. Reference resolution: when the RFI or its official answer names a spec section that exists in the project's
#     documents (e.g. "per Section 00 42 10"), did the agent find that section and cite an excerpt from it?
#  3. Decision agreement: when the official answer is a plain yes or no, did the agent reach the same one?
#  4. New information flagged: when the official answer supplies something that wasn't in the documents ("will be provided",
#     "see attached", an addendum), did the agent say a person must answer, instead of making something up?
#  5. Answer overlap: word-overlap F1 between the agent's answer and the official answer (as in SQuAD-style QA scoring).
# Baselines without AI: keyword search's top excerpt as the "citation" (for 2), and always answering the more common
# of yes/no (for 3).
import glob, json, os, re, statistics

def norm(s): return ' '.join(re.findall(r'[a-z0-9]+', (s or '').lower()))

CSI = re.compile(r'(?:section|spec(?:ification)?s?\.?|§)?\s*\b(\d{2})\s?(\d{2})\s?(\d{2})\b', re.I)
def refs(text):
    out = set()
    for m in CSI.finditer(text or ''):
        code = ''.join(m.groups())
        if code[:2] in ('19', '20') and re.search(r'\d{1,2}/\d{1,2}', text): continue   # skip dates
        out.add(code)
    return out

YES = re.compile(r'^\s*(yes|confirmed|correct|that is correct|this is correct|affirmative|acceptable|approved)\b', re.I)
NO = re.compile(r'^\s*(no\b|none\b|not\b|negative\b|there (?:is|are) no\b)|\b(?:is|are|will) not (?:be )?(?:required|utilized|permitted|allowed|acceptable|accepted|included)\b', re.I)
def label(ans):
    y, n = bool(YES.search(ans or '')), bool(NO.search(ans or ''))
    return 'yes' if y and not n else 'no' if n and not y else None

NEW = re.compile(r'will be (?:provided|issued|revised|added|posted|shared|included|addressed)|addend|amendment|see (?:the )?(?:attached|updated|revised)|has been (?:added|revised|updated|shared|posted|attached)|(?:is|are) attached|will be extended|refer to (?:the )?(?:attached|updated)', re.I)
STOP = set('the a an of to and or in on for is are be will this that with as by at from it its any all per please see not no yes'.split())
def f1(a, b):
    x, y = [w for w in norm(a).split() if w not in STOP], [w for w in norm(b).split() if w not in STOP]
    if not x or not y: return 0.0
    common = sum(min(x.count(w), y.count(w)) for w in set(x))
    if not common: return 0.0
    p, r = common / len(x), common / len(y); return 2 * p * r / (p + r)

def main():
    R = json.load(open('data/real/rfis.json'))
    docs = {p['project']: {x['id']: x for x in json.load(open('data/real/docs/%s.json' % p['project']))['pieces']} for p in R['projects']}
    runs = {}
    for f in glob.glob('data/real/results/*/*.json'):
        if f.endswith('summary.json'): continue
        d = json.load(open(f)); runs.setdefault(d['model'], []).append(d)
    gold = {r['id']: r for r in R['rfis']}
    summary = {'what': 'RFI responder on real public RFIs, scored by code against the official answers. See tools/real/score.py for each measure.',
               'rfis_available': len(R['rfis']), 'projects': R['projects'], 'models': {}}

    # Which RFIs have a checkable reference: the RFI or its official answer names a spec section present in the documents.
    def ref_target(r):
        have = {p['csi'] for p in docs[r['project']].values() if p.get('csi')}
        return (refs(r['question']) | refs(r['answer'])) & have
    ref_ids = [i for i, r in gold.items() if ref_target(r)]
    yn = {i: label(r['answer']) for i, r in gold.items() if label(r['answer'])}
    newinfo = {i for i, r in gold.items() if NEW.search(r['answer'])}
    summary['subsets'] = {'with_checkable_reference': len(ref_ids), 'with_yes_no_answer': len(yn), 'needing_new_information': len(newinfo),
                          'yes_no_split': {'yes': sum(v == 'yes' for v in yn.values()), 'no': sum(v == 'no' for v in yn.values())}}
    maj = 'yes' if summary['subsets']['yes_no_split']['yes'] >= summary['subsets']['yes_no_split']['no'] else 'no'
    summary['baselines'] = {'decision_always_%s' % maj: round(sum(v == maj for v in yn.values()) / max(1, len(yn)), 3)}

    for model, files in sorted(runs.items()):
        rows = [row for d in files for row in d['rows']]
        cit_total = cit_ok = fabricated = supported = with_cit = 0
        ref_hit = ref_n = dec_hit = dec_n = person = valid = 0
        kw_hit = 0; new_n = new_flag = 0; f1s = []; f1_base = []
        secs = []
        for row in rows:
            r = gold.get(row['id']); out = row.get('output') or {}
            if not r: continue
            P = docs[r['project']]
            ok_json = isinstance(out, dict) and 'answer' in out
            valid += ok_json
            cits = out.get('citations') if isinstance(out.get('citations'), list) else []
            good = []
            for c in cits:
                if not isinstance(c, dict): continue
                cit_total += 1
                pid = str(c.get('piece', '')).strip()
                if pid not in row['retrieved']: fabricated += 1; continue
                q = norm(c.get('quote'))
                if len(q.split()) >= 4 and q in norm(P[pid]['text']): cit_ok += 1; good.append(pid)
            if cits:
                with_cit += 1
                if len(good) == len([c for c in cits if isinstance(c, dict)]): supported += 1
            if out.get('needs_person') is True: person += 1
            tgt = ref_target(r)
            if tgt:
                ref_n += 1
                if any(P[g].get('csi') in tgt for g in good): ref_hit += 1
                if row['retrieved'] and P[row['retrieved'][0]].get('csi') in tgt: kw_hit += 1
            if row['id'] in newinfo:
                new_n += 1; new_flag += out.get('needs_person') is True
            f1s.append(f1(out.get('answer', ''), r['answer']))
            if row['retrieved']: f1_base.append(f1(' '.join(P[row['retrieved'][0]]['text'].split()[:40]), r['answer']))
            if row['id'] in yn:
                dec_n += 1; dec_hit += str(out.get('decision', '')).lower() == yn[row['id']]
            if row.get('seconds'): secs.append(row['seconds'])
        pct = lambda a, b: round(a / b, 3) if b else None
        summary['models'][model] = {
            'rfis_run': len(rows), 'valid_json': pct(valid, len(rows)),
            'citations': cit_total, 'citations_verified': pct(cit_ok, cit_total), 'citations_fabricated_ids': fabricated,
            'answers_with_citations': pct(with_cit, len(rows)), 'answers_fully_supported': pct(supported, with_cit),
            'reference_resolution': pct(ref_hit, ref_n), 'reference_n': ref_n,
            'reference_resolution_top_search_result': pct(kw_hit, ref_n),
            'decision_agreement': pct(dec_hit, dec_n), 'decision_n': dec_n,
            'asked_for_a_person': pct(person, len(rows)),
            'new_information_flagged': pct(new_flag, new_n), 'new_information_n': new_n,
            'answer_overlap_f1': round(statistics.mean(f1s), 3) if f1s else None,
            'answer_overlap_f1_baseline_top_search_text': round(statistics.mean(f1_base), 3) if f1_base else None,
            'median_seconds_per_rfi': statistics.median(secs) if secs else None,
            'search': sorted({d.get('search') for d in files}), 'embed_model': sorted({str(d.get('embed_model')) for d in files}),
        }
    os.makedirs('data/real/results', exist_ok=True)
    json.dump(summary, open('data/real/results/summary.json', 'w'), indent=1)
    print('RFIs: %d; with a checkable reference: %d; with a yes/no answer: %d; needing new information: %d' % (len(R['rfis']), len(ref_ids), len(yn), len(newinfo)))
    print('baseline:', summary['baselines'])
    for m, s in summary['models'].items():
        print('%-18s run %3d | citations verified %s (fabricated ids %d) | fully supported %s | reference %s (search top-1 %s, n=%d) | yes/no %s (n=%d) | new info flagged %s (n=%d) | overlap F1 %s (baseline %s) | asked for person %s | %ss/RFI' % (
            m, s['rfis_run'], s['citations_verified'], s['citations_fabricated_ids'], s['answers_fully_supported'], s['reference_resolution'],
            s['reference_resolution_top_search_result'], s['reference_n'], s['decision_agreement'], s['decision_n'], s['new_information_flagged'], s['new_information_n'], s['answer_overlap_f1'], s['answer_overlap_f1_baseline_top_search_text'], s['asked_for_a_person'], s['median_seconds_per_rfi']))

if __name__ == '__main__':
    main()
