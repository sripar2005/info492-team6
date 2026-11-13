#!/usr/bin/env python3
"""Merge sharded local-model runs (parallel GitHub jobs) into results/local/<model>/runs.json.
Usage: python merge_runs.py <shard folder> <model slug>"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
shard_dir = Path(sys.argv[1])
slug = sys.argv[2]  # e.g. llama3.1-8b
order = [c["id"] for c in json.loads((ROOT / "data" / "cases.json").read_text())["cases"]]
results, meta = {}, None
files = sorted((f for f in shard_dir.rglob("*.json") if f.name.startswith(slug + "__")), key=lambda f: str(f))
for f in files:
    d = json.loads(f.read_text())
    meta = meta or d["meta"]
    for r in d["results"]:
        results[r["id"]] = r
missing = [i for i in order if i not in results]
if missing:
    sys.exit(f"Missing CPs: {missing}")
ordered = [results[i] for i in order]
meta.update({"cases": len(ordered), "agent_calls": sum(sum(1 for e in r["trail"] if not e.get("skipped")) for r in ordered),
             "input_tokens": sum(r["usage"]["input_tokens"] for r in ordered),
             "output_tokens": sum(r["usage"]["output_tokens"] for r in ordered), "shards": len(files)})
out = ROOT / "results" / "local" / slug / "runs.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"meta": meta, "results": ordered}, indent=1, ensure_ascii=False))
print(f"Merged {len(ordered)} CPs into {out}")
