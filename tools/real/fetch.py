# Downloads every public record in data/real/sources.json into the repo and writes data/real/manifest.json
# (source link, download time, size, SHA-256), so anyone can confirm the files are the same public documents.
# Runs on GitHub's machines (.github/workflows/real-fetch.yml). python3 tools/real/fetch.py
import json, hashlib, os, time, urllib.request
S = json.load(open('data/real/sources.json'))['sources']
man = []
for s in S:
    os.makedirs(os.path.dirname(s['file']), exist_ok=True)
    rec = dict(s)
    try:
        if not os.path.exists(s['file']):
            req = urllib.request.Request(s['url'], headers={'User-Agent': 'Mozilla/5.0 (research; UW INFO 492 Team 6)'})
            with urllib.request.urlopen(req, timeout=120) as r, open(s['file'], 'wb') as f: f.write(r.read())
            time.sleep(1)
        b = open(s['file'], 'rb').read()
        if not b.startswith(b'%PDF'): raise ValueError('not a PDF (got %r)' % b[:20])
        rec.update(ok=True, bytes=len(b), sha256=hashlib.sha256(b).hexdigest(), downloaded=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    except Exception as e:
        if os.path.exists(s['file']) and not open(s['file'], 'rb').read(4) == b'%PDF': os.remove(s['file'])
        rec.update(ok=False, error=str(e)[:200])
    man.append(rec); print(('ok  ' if rec['ok'] else 'FAIL'), s['project'], os.path.basename(s['file']), rec.get('bytes', rec.get('error')))
json.dump({'downloaded_by': 'tools/real/fetch.py', 'files': man}, open('data/real/manifest.json', 'w'), indent=1)
print('%d of %d downloaded' % (sum(m['ok'] for m in man), len(man)))
