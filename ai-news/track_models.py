#!/usr/bin/env python3
"""Track named AI models from rumour to release using news.json.
Persistent state in model-tracker.json: first/last rumour date, release date, evidence links.
A model is a brand + version found in headlines (e.g. "Kimi K3.1", "GPT-6.1", "DeepSeek V4.1 Flash").
Rumour = headline with signal words (leak/reportedly/expected/soon/to launch...). Release = launch/release/announce words."""
import json, os, re, datetime
here = os.path.dirname(os.path.abspath(__file__))
BRANDS = r"GPT|ChatGPT|Claude|Gemini|Gemma|Grok|Llama|Qwen|Kimi|DeepSeek|Mistral|Magistral|Codestral|GLM|MiniMax|Sora|Veo|Seedance|Kling|Nano Banana|Midjourney|Flux|Hailuo|Wan|Hunyuan|Ernie|Doubao|Phi|Nova|Command|Opus|Sonnet|Haiku|Imagen|Gen|Pika|Luma"
NAME = re.compile(r"\b(" + BRANDS + r")\b[\s\-]*(Opus|Sonnet|Haiku|Code|Max)?[\s\-]*([KkVv]?\d+(?:\.\d+)*[a-z]?)\b(?:[\s\-]+(Pro|Flash|Mini|Nano|Ultra|Lite|Sol|Luna|Terra|Astra|Argon|Turbo|Plus|Preview|Thinking|Code|Max|Instruct|Reasoner|Omni|Image|Video))?", re.I)
UP = re.compile(r"rumou?r|leak|reportedly|expected|upcoming|coming soon|\bsoon\b|teas(e|es|er|ing)|spotted|in testing|\btesting|next[- ]gen|to (launch|release|unveil|debut|drop)|plans? to (launch|release)|could (launch|arrive|debut)|set to|will (launch|release|arrive|debut)|imminent|\bpreview|surfaces?|planned|identifier", re.I)
REL = re.compile(r"launch|releas|introduc|unveil|announc|debut|rolls? out|now available|available now|open-?sources?", re.I)
PROPER = {"gpt": "GPT", "chatgpt": "ChatGPT", "deepseek": "DeepSeek", "minimax": "MiniMax", "glm": "GLM", "nano banana": "Nano Banana"}

def norm(m):
    brand, sub, ver, suf = m.group(1), m.group(2), m.group(3), m.group(4)
    b = PROPER.get(brand.lower(), brand.title())
    v = ver.upper() if re.match(r"[kKvV]", ver) else ver
    parts = [b] + ([sub.title()] if sub else []) + [("-" if b == "GPT" else "") + v] + ([suf.title()] if suf else [])
    name = " ".join(parts).replace("GPT -", "GPT-")
    return name, re.sub(r"[\s\-]+", "", name.lower())

def dt(s): return datetime.datetime.strptime(s[:10], "%Y-%m-%d").date()

news = json.load(open(os.path.join(here, "news.json"), encoding="utf8"))
path = os.path.join(here, "model-tracker.json")
try: db = {m["k"]: m for m in json.load(open(path, encoding="utf8")).get("models", [])}
except Exception: db = {}

for it in news["items"]:
    t = it["t"]; txt = t + " " + (it.get("d") or "")[:160]
    if not (UP.search(txt) or REL.search(t)): continue
    kind = "up" if UP.search(txt) else "rel"
    seen = set()
    for m in NAME.finditer(t):
        name, key = norm(m)
        if key in seen: continue
        seen.add(key)
        r = db.setdefault(key, {"k": key, "n": name, "first": None, "last": None, "rel": None, "ups": [], "relItem": None, "src": []})
        ev = {"t": t[:140], "u": it["u"], "p": it["p"][:10], "s": it["s"]}
        if it["s"] not in r["src"]: r["src"].append(it["s"])
        if kind == "up":
            if not any(x["u"] == it["u"] for x in r["ups"]): r["ups"].append(ev)
            r["first"] = min(filter(None, [r["first"], ev["p"]])); r["last"] = max(filter(None, [r["last"], ev["p"]]))
        else:
            if r["rel"] is None or ev["p"] < r["rel"]:
                r["rel"] = ev["p"]; r["relItem"] = ev
for r in db.values():
    r["ups"] = sorted(r["ups"], key=lambda x: x["p"], reverse=True)[:4]
    r["src"] = r["src"][:8]
    # a release dated clearly before the first rumour is not "the" release of that rumour
    if r["rel"] and r["first"] and r["rel"] < (dt(r["first"]) - datetime.timedelta(days=2)).isoformat():
        r["early"] = True
    else: r.pop("early", None)
# a rumour about "GPT-6.1" is considered released when a variant such as "GPT-6.1 Sol" is released
for r in db.values():
    if r["rel"]: continue
    for o in db.values():
        if o["k"] != r["k"] and o["k"].startswith(r["k"]) and o["rel"] and (not r["first"] or o["rel"] >= (dt(r["first"]) - datetime.timedelta(days=2)).isoformat()):
            r["rel"], r["relItem"], r["via"] = o["rel"], o["relItem"], o["n"]; break
today = datetime.date.today()
keep = []
for r in db.values():
    last = r["rel"] or r["last"]
    if last and (today - dt(last)).days > 120: continue   # forget very old entries
    keep.append(r)
keep.sort(key=lambda r: (r["rel"] is not None, -(dt(r["last"] or r["rel"]).toordinal())))
json.dump({"updated": news["updated"], "models": keep}, open(path, "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
print("tracked", len(keep), "models;", sum(1 for r in keep if r["rel"]), "released")
