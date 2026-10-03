#!/usr/bin/env python3
"""Collect what people search for on YouTube (autocomplete suggestions, ordered by popularity)
for AI-related seed terms -> trends/trends.json. No API key. Env: SUGGEST_URL (testing override)."""
import json, os, sys, time, datetime, urllib.parse, urllib.request
here = os.path.dirname(os.path.abspath(__file__))
URL = os.environ.get("SUGGEST_URL", "https://suggestqueries.google.com/complete/search")
SEEDS = ["ai", "chatgpt", "claude", "gemini", "deepseek", "seedance", "midjourney", "sora", "kling", "ai agents", "mcp", "cursor ai", "nano banana",
         "ذكاء اصطناعي", "الذكاء الاصطناعي", "كلود", "شات جي بي تي", "جيميني", "برومبت", "فيديو بالذكاء الاصطناعي", "الربح من الذكاء الاصطناعي"]
out = []
for q in SEEDS:
    try:
        u = "%s?%s" % (URL, urllib.parse.urlencode({"client": "firefox", "ds": "yt", "hl": "ar", "q": q}))
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf8", "replace"))
        sug = [s for s in data[1] if s.strip().lower() != q.lower()][:10]
        if sug: out.append({"q": q, "s": sug})
    except Exception as e:
        print("failed:", q, e, file=sys.stderr)
    time.sleep(0.7)
if not out:
    print("nothing fetched; keeping previous", file=sys.stderr); sys.exit(0)
json.dump({"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "seeds": out}, open(os.path.join(here, "trends.json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
print("wrote", len(out), "seeds")
