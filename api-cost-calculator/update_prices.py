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
new = {"updated": datetime.date.today().isoformat(), "source": "LiteLLM community price list", "models": out}
path = os.path.join(here, "prices.json")
try:
    old = json.load(open(path))
except Exception:
    old = None
if old and old.get("models") == out:
    print("no price changes"); sys.exit(0)
json.dump(new, open(path, "w"), ensure_ascii=False, indent=1)
print("updated", len(out), "models")
