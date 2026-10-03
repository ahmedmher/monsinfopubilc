#!/usr/bin/env python3
"""Fetch AI news from RSS/Atom feeds (feeds.json) and write news.json. No paid services.
Env: FEEDS_FILE (override feeds list), DAYS (default 7), MAX_ITEMS (default 150)."""
import json, os, re, sys, html, datetime, email.utils, urllib.request
import xml.etree.ElementTree as ET
here = os.path.dirname(os.path.abspath(__file__))
DAYS = int(os.environ.get("DAYS", 30)); MAX_ITEMS = int(os.environ.get("MAX_ITEMS", 500))  # 30-day archive so shared links keep working
now = datetime.datetime.now(datetime.timezone.utc)
KW = re.compile(r"\b(ai|a\.i\.|artificial intelligence|llm|gpt|chatgpt|claude|gemini|openai|anthropic|machine learning|deep learning|neural|agentic|agents?|copilot|diffusion|generative|genai|nvidia nim|inference)\b|ذكاء|نموذج", re.I)

def local(tag): return tag.rsplit("}", 1)[-1]
def child(e, *names):
    for c in e:
        if local(c.tag) in names: return c
    return None
def text_of(e): return "".join(e.itertext()).strip() if e is not None else ""
def clean(s, n=240):
    s = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(s or "")))
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(The post .* appeared first on .*|Continue reading.*|Read more.*|\[…\]|\[\.\.\.\])\s*$", "", s, flags=re.I).strip()
    if len(s) > n:
        s = s[:n].rsplit(" ", 1)[0].rstrip(".,;:- ") + "…"
    return s
def parse_date(s):
    s = (s or "").strip()
    if not s: return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=datetime.timezone.utc)
    return d
def image_of(e, desc_html):
    for c in e.iter():
        n = local(c.tag)
        if n in ("thumbnail", "content") and c.get("url") and (c.get("medium") in (None, "image") or (c.get("type") or "").startswith("image")):
            return c.get("url")
        if n == "enclosure" and (c.get("type") or "").startswith("image") and c.get("url"): return c.get("url")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', html.unescape(desc_html or ""))
    return m.group(1) if m else ""

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ai-news-board; +https://github.com)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    return urllib.request.urlopen(req, timeout=30).read()

feeds = json.load(open(os.environ.get("FEEDS_FILE") or os.path.join(here, "feeds.json")))
items, srcs = [], []
for f in feeds:
    try:
        root = ET.fromstring(fetch(f["url"]))
    except Exception as e:
        print("feed failed:", f["id"], e, file=sys.stderr); continue
    entries = [e for e in root.iter() if local(e.tag) in ("item", "entry")]
    n = 0
    for e in entries:
        title = clean(text_of(child(e, "title")), 160)
        lk = child(e, "link")
        link = (lk.get("href") if lk is not None and lk.get("href") else text_of(lk)) if lk is not None else ""
        if lk is not None and local(lk.tag) == "link" and not link:
            for c in e:
                if local(c.tag) == "link" and c.get("rel") in (None, "alternate") and c.get("href"): link = c.get("href"); break
        raw = text_of(child(e, "description", "summary")) or text_of(child(e, "encoded", "content"))
        full = raw
        d = parse_date(text_of(child(e, "pubDate", "published", "updated", "date")))
        if not title or not link or not d: continue
        if (now - d).days >= DAYS or d > now + datetime.timedelta(hours=2): continue
        desc = clean(raw)
        if f.get("filter") and not KW.search(title + " " + desc): continue
        items.append({"t": title, "d": desc, "x": clean(raw, 700), "u": link, "p": d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "s": f["id"], "i": image_of(e, raw)})
        n += 1
    if n: srcs.append({"id": f["id"], "name": f["name"], "lang": f["lang"]})
    print(f["id"], n)
try:  # keep the archive: merge previous items that are still inside the window
    prev = json.load(open(os.path.join(here, "news.json"), encoding="utf8")).get("items", [])
    have = {i["u"] for i in items}
    for it in prev:
        d = parse_date(it["p"].replace("Z", ":00+00:00") if it["p"].endswith("Z") and len(it["p"]) == 17 else it["p"])
        if it["u"] not in have and d and (now - d).days < DAYS: items.append(it)
except Exception: pass
seen, out = set(), []
for it in sorted(items, key=lambda x: x["p"], reverse=True):
    k = re.sub(r"\W+", "", it["t"].lower())[:60]
    if it["u"] in seen or k in seen: continue
    seen.add(it["u"]); seen.add(k); out.append(it)
out = out[:MAX_ITEMS]
used = {i["s"] for i in out}
srcs = [{"id": f["id"], "name": f["name"], "lang": f["lang"]} for f in feeds if f["id"] in used]
if not out:
    print("no items fetched; keeping previous news.json", file=sys.stderr); sys.exit(0)
json.dump({"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "sources": srcs, "items": out}, open(os.path.join(here, "news.json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
print("wrote", len(out), "items")
