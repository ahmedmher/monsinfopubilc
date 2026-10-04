#!/usr/bin/env python3
"""Builds media.json: the curated image/video/voice tools in media-catalog.json, priced from the LiteLLM community list
(API prices per image / second of video / 1000 characters of speech), plus models the list knows that the catalog does not.
Usage: python3 update_media.py [local_litellm.json]"""
import json, os, re, statistics, sys, datetime, urllib.request
here = os.path.dirname(os.path.abspath(__file__))
SRC = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
src = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else json.load(urllib.request.urlopen(SRC, timeout=60))
src.pop("sample_spec", None)
FIELD = {"img": ("output_cost_per_image", ), "sec": ("output_cost_per_second", "output_cost_per_video_per_second"), "kchar": ("input_cost_per_character", )}
MODE = {"img": "image_generation", "sec": "video_generation", "kchar": "audio_speech"}
NOISE = r"\d+-x-\d+|steps|/high/|/low/|/medium/|batch|azure|bedrock|^aws|^us\.|^eu\.|amazon|titan|nova|^ai21|^aiml/|^together|^replicate|^lambda"
SCALE = {"img": 1, "sec": 1, "kchar": 1000}
LEVEL = {"img": (0.03, 0.1), "sec": (0.12, 0.35), "kchar": (0.05, 0.25)}   # upper bounds of "economy" and "mid" in USD
def price(entry):
    for f in FIELD[entry["k"]]:
        v = src_v.get(f)
        if v: return v * SCALE[entry["k"]]
    return None
cat = json.load(open(os.path.join(here, "media-catalog.json"), encoding="utf8")); used = set(); tools = []
for e in cat:
    e = dict(e)
    if e.get("rx"):
        vals = []
        for key, src_v in src.items():
            if src_v.get("mode") != MODE[e["k"]] or re.search(NOISE, key) or not re.search(e["rx"], key, re.I): continue
            p = price(e)
            if p and p > 0: vals.append(round(p, 4)); used.add(key)
        if vals:
            e["pr"] = {"k": e["k"], "min": min(vals), "max": max(vals), "med": round(statistics.median(vals), 4), "n": len(vals)}
            if not e.get("o"):
                lo, mid = LEVEL[e["k"]]; m = e["pr"]["med"]; e["c"] = 1 if m < lo else 2 if m < mid else 3
    e.pop("rx", None); tools.append(e)
# models the price list knows but the catalog does not (recent additions), cheapest representative per base name
disc = {}
for key, v in src.items():
    k = next((kk for kk, m in MODE.items() if v.get("mode") == m), None)
    if not k or key in used or re.search(NOISE, key) or "-preview-" in key or key.startswith("runwayml/"): continue
    if not (key.startswith(("fal_ai/", "gemini/", "openai/", "runwayml/", "minimax/", "vertex_ai/", "recraft/", "stability/", "black_forest_labs/", "xai/", "bytedance/", "elevenlabs/", "luma/")) or "/" not in key): continue
    src_v = v; p = None
    for f in FIELD[k]:
        if v.get(f): p = v[f] * SCALE[k]; break
    if not p: continue
    base = re.sub(r"^(fal_ai/|gemini/|vertex_ai/|openai/|fal-ai/)+", "", key).split("/")
    name = "/".join(base[:2]) if len(base) > 1 else base[0]
    if re.search(r"preview|-exp|^gemini-2\.0|^stability\.|:\d$|\d{4}-\d{2}-\d{2}|chirp|trellis|virtual-try|^stable-diffusion|stability/sd3(-|$)", name): continue
    if name not in disc or p < disc[name]["p"]: disc[name] = {"n": name, "k": k, "p": round(p, 4), "src": key.split("/")[0]}
discovered = sorted(disc.values(), key=lambda d: d["n"])[:20]
out = {"updated": datetime.date.today().isoformat(), "source": "LiteLLM community price list", "tools": tools, "discovered": discovered}
path = os.path.join(here, "media.json")
try:
    old = json.load(open(path))
    if old.get("tools") == tools and old.get("discovered") == discovered: print("no media changes"); sys.exit(0)
except Exception: pass
json.dump(out, open(path, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("tools:", len(tools), "| priced:", sum(1 for t in tools if t.get("pr")), "| discovered:", len(discovered))
