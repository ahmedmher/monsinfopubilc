#!/usr/bin/env python3
"""Search-interest data, no API keys:
- trends.json: YouTube and Google autocomplete suggestions (ordered by popularity), aggregated over AI seed terms,
  with rank change versus the previous snapshot.
- wiki.json: daily Wikipedia page views (official Wikimedia API) for AI topics = public interest rate.
Env: SUGGEST_URL, WIKI_URL (testing overrides)."""
import json, os, re, sys, time, datetime, urllib.parse, urllib.request
here = os.path.dirname(os.path.abspath(__file__))
SUGGEST = os.environ.get("SUGGEST_URL", "https://suggestqueries.google.com/complete/search")
WIKI = os.environ.get("WIKI_URL", "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article")
UA = {"User-Agent": "monsinfo-trends/1.0 (https://www.monsinfo.com; ahmedmaher449@gmail.com)"}
SEEDS = ["ai tools", "ai video", "chatgpt", "claude", "gemini", "deepseek", "seedance", "midjourney", "sora", "kling", "ai agents", "mcp", "cursor ai", "nano banana",
         "ذكاء اصطناعي", "الذكاء الاصطناعي", "كلود", "شات جي بي تي", "جيميني", "برومبت", "فيديو بالذكاء الاصطناعي", "الربح من الذكاء الاصطناعي"]
REL = re.compile(r"\bai\b|gpt|claude|gemini|deepseek|seedance|midjourney|sora|kling|mcp|cursor|banana|agent|prompt|llm|openai|copilot|runway|veo|ذكاء|كلود|جي بي تي|جيميني|برومبت|شات|نانو", re.I)
WIKIS = [("ChatGPT", "en", "ChatGPT"), ("Claude", "en", "Claude_(language_model)"), ("Gemini", "en", "Gemini_(language_model)"), ("DeepSeek", "en", "DeepSeek"),
         ("Midjourney", "en", "Midjourney"), ("Sora", "en", "Sora_(text-to-video_model)"), ("OpenAI", "en", "OpenAI"), ("Anthropic", "en", "Anthropic"),
         ("Llama", "en", "Llama_(language_model)"), ("نماذج اللغة LLM", "en", "Large_language_model"), ("الذكاء الاصطناعي (إنجليزي)", "en", "Artificial_intelligence"),
         ("الذكاء الاصطناعي (عربي)", "ar", "الذكاء_الاصطناعي")]
now = datetime.datetime.now(datetime.timezone.utc)

def get(url, timeout=25):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read().decode("utf8", "replace")

def suggest(q, yt):
    p = {"client": "firefox", "hl": "ar", "q": q}
    if yt: p["ds"] = "yt"
    data = json.loads(get("%s?%s" % (SUGGEST, urllib.parse.urlencode(p))))
    return [s for s in data[1] if s.strip().lower() != q.lower() and REL.search(s)][:10]

try: old = json.load(open(os.path.join(here, "trends.json"), encoding="utf8"))
except Exception: old = {}

def aggregate(key, yt):
    score, disp = {}, {}
    for q in SEEDS:
        try:
            for i, s in enumerate(suggest(q, yt)):
                k = s.lower(); disp.setdefault(k, s); score[k] = score.get(k, 0) + 1.0 / (i + 1)
        except Exception as e:
            print("failed:", key, q, e, file=sys.stderr)
        time.sleep(0.6)
    ranked = sorted(score, key=lambda k: -score[k])[:25]
    prev = {x["q"].lower(): i for i, x in enumerate(old.get(key, []))}
    out = []
    for i, k in enumerate(ranked):
        out.append({"q": disp[k], "s": round(score[k], 2), "d": (prev[k] - i) if k in prev else None})  # d>0 up, None = new
    return out

yt = aggregate("yt", True); g = aggregate("g", False)
if yt or g:
    json.dump({"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "yt": yt or old.get("yt", []), "g": g or old.get("g", [])},
              open(os.path.join(here, "trends.json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
    print("trends:", len(yt), "youtube,", len(g), "google")
else:
    print("no suggestions fetched; keeping previous", file=sys.stderr)

end = (now - datetime.timedelta(days=1)).date(); start = end - datetime.timedelta(days=29)
topics = []
for name, lang, title in WIKIS:
    try:
        u = "%s/%s.wikipedia/all-access/user/%s/daily/%s/%s" % (WIKI, lang, urllib.parse.quote(title, safe="()_"), start.strftime("%Y%m%d00"), end.strftime("%Y%m%d00"))
        items = json.loads(get(u)).get("items", [])
        by = {it["timestamp"][:8]: it["views"] for it in items}
        days = [(start + datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(30)]
        topics.append({"n": name, "l": lang, "d": [by.get(d, 0) for d in days]})
    except Exception as e:
        print("wiki failed:", name, e, file=sys.stderr)
    time.sleep(0.3)
if topics:
    json.dump({"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "start": start.isoformat(), "topics": topics}, open(os.path.join(here, "wiki.json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
    print("wiki:", len(topics), "topics")
