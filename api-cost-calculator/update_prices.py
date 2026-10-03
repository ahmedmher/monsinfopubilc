#!/usr/bin/env python3
"""Build prices.json (USD per 1M tokens) for the curated models in models.json
from the community-maintained LiteLLM price list.
Usage: python3 update_prices.py [local_litellm.json]"""
import json, sys, datetime, urllib.request, os
SRC = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
here = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) > 1:
    src = json.load(open(sys.argv[1]))
else:
    src = json.load(urllib.request.urlopen(SRC, timeout=60))
out, missing = [], []
for key, name, prov in json.load(open(os.path.join(here, "models.json"))):
    v = src.get(key)
    if not v or "input_cost_per_token" not in v:
        missing.append(key); continue
    i = round(v["input_cost_per_token"] * 1e6, 4)
    o = round(v.get("output_cost_per_token", 0) * 1e6, 4)
    c = round((v.get("cache_read_input_token_cost") or v["input_cost_per_token"]) * 1e6, 4)
    x = v.get("max_input_tokens") or v.get("max_tokens") or 0
    out.append({"id": key.replace("/", "-"), "n": name, "p": prov, "i": i, "o": o, "c": c, "x": x})
if missing:
    print("missing:", missing, file=sys.stderr)
path = os.path.join(here, "prices.json")
try:
    old = json.load(open(path))
except Exception:
    old = None
if old and old.get("models") == out:
    print("no price changes"); sys.exit(0)
# detect real price changes versus the previous snapshot and keep the last 60 days of them
today_s = datetime.date.today().isoformat()
changes = []
if old:
    prev = {m["id"]: m for m in old.get("models", [])}
    for m in out:
        o = prev.get(m["id"])
        if not o: continue
        for fld, label in (("i", "input"), ("o", "output")):
            if abs(o[fld] - m[fld]) > 1e-9:
                changes.append({"id": m["id"], "n": m["n"], "p": m["p"], "d": today_s, "f": label, "old": o[fld], "new": m[fld]})
    keep_from = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
    changes = [c for c in old.get("changes", []) if c["d"] >= keep_from] + changes
new = {"updated": today_s, "source": "LiteLLM community price list", "models": out, "changes": changes}
json.dump(new, open(path, "w"), ensure_ascii=False, indent=1)
print("updated", len(out), "models")
