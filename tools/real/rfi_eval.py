# RFI responder on real public RFIs: finds the governing section in the project's own documents, drafts a response,
# and cites word-for-word quotes. Scored by code against the official published answers (tools/real/score.py).
# Free local models through Ollama; no API key.
#   python3 tools/real/rfi_eval.py --model qwen3.5:9b --project maine-2995-capitol-garage
import argparse, json, math, os, re, time, urllib.request, hashlib

OLLAMA = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
EMBED = os.environ.get('EMBED_MODEL', 'qwen3-embedding:0.6b')
K = 6

def words(s): return re.findall(r'[a-z0-9]+', s.lower())

# ---------- search: keyword (BM25) plus an embedding model, fused by rank ----------
class BM25:
    def __init__(self, docs, k1=1.4, b=0.75):
        self.toks = [words(d) for d in docs]; self.N = len(docs); self.avg = sum(map(len, self.toks)) / max(1, self.N)
        self.df = {}
        for t in self.toks:
            for w in set(t): self.df[w] = self.df.get(w, 0) + 1
        self.k1, self.b = k1, b
    def scores(self, q):
        qs, out = words(q), []
        for t in self.toks:
            tf, s = {}, 0.0
            for w in t: tf[w] = tf.get(w, 0) + 1
            for w in qs:
                if w in tf:
                    idf = math.log(1 + (self.N - self.df[w] + .5) / (self.df[w] + .5))
                    s += idf * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * len(t) / self.avg))
            out.append(s)
        return out

def post(path, body, timeout=1800):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())

def embed(texts):
    out = []
    for i in range(0, len(texts), 32):
        out += post('/api/embed', {'model': EMBED, 'input': texts[i:i + 32]})['embeddings']
    return out

def cos(a, b):
    na = math.sqrt(sum(x * x for x in a)) or 1; nb = math.sqrt(sum(x * x for x in b)) or 1
    return sum(x * y for x, y in zip(a, b)) / na / nb

def rank(scores): return [i for i, _ in sorted(enumerate(scores), key=lambda x: -x[1])]

class Search:
    def __init__(self, pieces, use_embed=True):
        self.p = pieces
        self.bm = BM25(['%s %s %s' % (x['section'], x['title'], x['text']) for x in pieces])
        self.vec = None
        if use_embed:
            try: self.vec = embed(['%s %s\n%s' % (x['section'], x['title'], x['text'][:1500]) for x in pieces])
            except Exception as e: print('embedding model unavailable, keyword search only:', e)
    def top(self, q, k=K, mode='hybrid'):
        rb = rank(self.bm.scores(q))
        if mode == 'bm25' or not self.vec: return rb[:k]
        qv = embed([q])[0]; re_ = rank([cos(qv, v) for v in self.vec])
        if mode == 'embed': return re_[:k]
        fused = {}
        for r in (rb, re_):
            for pos, i in enumerate(r[:60]): fused[i] = fused.get(i, 0) + 1 / (60 + pos)
        return [i for i, _ in sorted(fused.items(), key=lambda x: -x[1])][:k]

# ---------- the agent ----------
SYSTEM = """You answer contractors' requests for information (RFIs) on a public construction project, for the owner and design team.
Use ONLY the document excerpts provided. Each excerpt has an id.
Return JSON only, with these keys:
  "decision": "yes" if the answer to the question is yes/confirmed, "no" if it is no/not required/not allowed, otherwise "other".
  "answer": a short, direct response (1-3 sentences) as the owner or design team would write it.
  "citations": a list of {"piece": "<excerpt id>", "quote": "<4 to 30 words copied exactly from that excerpt>"} that support the answer. Empty if nothing in the excerpts applies.
  "needs_person": true if the excerpts don't settle it and the architect, engineer or owner must decide or supply new information.
  "route": "architect/engineer" for design and technical questions, "owner" for contract, bidding, schedule and commercial questions.
Never cite an id that was not provided. Never invent section numbers."""

def prompt(r, pieces):
    ex = '\n\n'.join('[id: %s] %s, %s %s\n%s' % (p['id'], p['doc'], p['section'], p['title'], p['text'][:1400]) for p in pieces)
    return 'Project: %s\n\nRFI: %s\n\nDocument excerpts:\n%s' % (r['project_name'], r['question'], ex)

def ask(model, user):
    body = {'model': model, 'stream': False, 'format': 'json', 'think': False,
            'options': {'temperature': 0, 'seed': 7, 'num_ctx': 8192, 'num_predict': 700},
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]}
    res, err = None, None
    for attempt in range(3):   # a server error on one RFI is retried, then logged; it never ends the run
        try: res = post('/api/chat', body); break
        except Exception as e:
            err = e; body.pop('think', None); time.sleep(5 * (attempt + 1))
    if res is None: return {'error': 'model call failed: %s' % str(err)[:200]}, {}
    txt = res.get('message', {}).get('content', '')
    try: out = json.loads(txt)
    except Exception:
        m = re.search(r'\{.*\}', txt, re.S); out = json.loads(m.group(0)) if m else {'error': 'no JSON', 'raw': txt[:400]}
    return out, res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--project'); ap.add_argument('--limit', type=int)
    ap.add_argument('--search', default='hybrid', choices=['hybrid', 'bm25', 'embed'])
    a = ap.parse_args()
    R = json.load(open('data/real/rfis.json'))
    projects = [p for p in R['projects'] if not a.project or p['project'] == a.project]
    outdir = 'data/real/results/%s' % re.sub(r'[^A-Za-z0-9._-]', '_', a.model); os.makedirs(outdir, exist_ok=True)
    for P in projects:
        D = json.load(open('data/real/docs/%s.json' % P['project']))
        S = Search(D['pieces'], a.search != 'bm25')
        rows = [r for r in R['rfis'] if r['project'] == P['project']][:a.limit]
        # Search everything first, then unload the search model, so it never shares memory with the answering model.
        tops = {r['id']: S.top(r['question'], mode=a.search) for r in rows}
        if S.vec:
            try: post('/api/embed', {'model': EMBED, 'input': 'x', 'keep_alive': 0})
            except Exception: pass
        out, path = [], '%s/%s.json' % (outdir, P['project'])
        meta = {'model': a.model, 'project': P['project'], 'search': a.search, 'embed_model': EMBED if S.vec else None, 'k': K, 'system_prompt': SYSTEM}
        for r in rows:
            r = dict(r, project_name=D['name'])
            got = [D['pieces'][i] for i in tops[r['id']]]
            u = prompt(r, got); t0 = time.time()
            ans, raw = ask(a.model, u)
            out.append({'id': r['id'], 'question': r['question'], 'official_answer': r['answer'], 'discipline': r.get('discipline'),
                        'retrieved': [p['id'] for p in got], 'prompt_sha': hashlib.sha256(u.encode()).hexdigest()[:12],
                        'output': ans, 'seconds': round(time.time() - t0, 1), 'eval_count': raw.get('eval_count'), 'prompt_eval_count': raw.get('prompt_eval_count')})
            print('%s %s %.0fs %s' % (a.model, r['id'], time.time() - t0, json.dumps(ans)[:140]), flush=True)
            # Saved after every RFI, so a machine that shuts down keeps what it finished.
            json.dump(dict(meta, ran=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), complete=len(out) == len(rows), rows=out), open(path, 'w'), indent=1)

if __name__ == '__main__':
    main()
