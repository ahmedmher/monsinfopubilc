#!/usr/bin/env python3
"""Fetch AI news from RSS/Atom feeds (feeds.json) and write news.json. No paid services.
Each item gets: d = short card summary, x = longer excerpt (RSS content, or the article's own
meta description + first paragraphs when the feed is too short). Items are archived 30 days.
Env: FEEDS_FILE, DAYS (30), MAX_ITEMS (500), PAGE_FETCH (max article pages fetched per run, 40)."""
import json, os, re, sys, html, datetime, email.utils, urllib.request
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
here = os.path.dirname(os.path.abspath(__file__))
DAYS = int(os.environ.get("DAYS", 30)); MAX_ITEMS = int(os.environ.get("MAX_ITEMS", 500))
PAGE_FETCH = int(os.environ.get("PAGE_FETCH", 40)); X_MAX = 1300; X_MIN = 450
now = datetime.datetime.now(datetime.timezone.utc)
KW = re.compile(r"\b(ai|a\.i\.|artificial intelligence|llm|gpt|chatgpt|claude|gemini|openai|anthropic|machine learning|deep learning|neural|agentic|agents?|copilot|diffusion|generative|genai|nvidia nim|inference)\b|ذكاء|نموذج", re.I)
BOILER = re.compile(r"cookie|subscribe|newsletter|sign up|all rights reserved|privacy policy|follow us|advertisement|read more|click here|اشترك|جميع الحقوق", re.I)

def local(tag): return tag.rsplit("}", 1)[-1]
def child(e, *names):
    for c in e:
        if local(c.tag) in names: return c
    return None
def text_of(e): return "".join(e.itertext()).strip() if e is not None else ""
def cut(s, n):
    if len(s) <= n: return s
    s = s[:n]
    k = max(s.rfind(". "), s.rfind("؟ "), s.rfind("! "), s.rfind("? "))
    return (s[:k + 1] if k > n * 0.6 else s.rsplit(" ", 1)[0].rstrip(".,;:- ") + "…")
def clean(s, n=240):
    s = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(s or "")))
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(The post .* appeared first on .*|Continue reading.*|Read more.*|\[…\]|\[\.\.\.\])\s*$", "", s, flags=re.I).strip()
    if len(s) > n:
        s = s[:n].rsplit(" ", 1)[0].rstrip(".,;:- ") + "…"
    return s
def paras_from_html(raw):
    raw = html.unescape(raw or "")
    raw = re.sub(r"(?i)</p>|<br\s*/?>|</li>|</h\d>", "\n", raw)
    raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    out = []
    for ln in raw.split("\n"):
        ln = re.sub(r"\s+", " ", ln).strip()
        if len(ln) >= 40 and not BOILER.search(ln) and not re.match(r"(The post .* appeared first on)", ln, re.I): out.append(ln)
    return out
def join_x(paras):
    return cut("\n".join(paras), X_MAX)
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

UA = {"User-Agent": "Mozilla/5.0 (ai-news-board; +https://github.com)"}
def fetch(url, accept="application/rss+xml, application/atom+xml, application/xml, text/xml, */*", limit=None, timeout=30):
    req = urllib.request.Request(url, headers=dict(UA, Accept=accept))
    r = urllib.request.urlopen(req, timeout=timeout)
    return r.read(limit) if limit else r.read()

class Page(HTMLParser):
    """Collect <p> texts (preferring those inside <article>/<main>) and the meta description."""
    def __init__(self):
        super().__init__(); self.meta = ""; self.art = []; self.all = []; self.depth = 0; self.p = None; self.skip = 0
    def handle_starttag(self, t, a):
        a = dict(a)
        if t in ("article", "main"): self.depth += 1
        if t in ("script", "style", "nav", "footer", "aside", "form", "noscript"): self.skip += 1
        if t == "p" and not self.skip: self.p = []
        if t == "meta" and (a.get("property") in ("og:description",) or a.get("name") in ("description", "twitter:description")) and not self.meta:
            self.meta = a.get("content") or ""
    def handle_endtag(self, t):
        if t in ("article", "main") and self.depth: self.depth -= 1
        if t in ("script", "style", "nav", "footer", "aside", "form", "noscript") and self.skip: self.skip -= 1
        if t == "p" and self.p is not None:
            s = re.sub(r"\s+", " ", "".join(self.p)).strip(); self.p = None
            if len(s) >= 70 and not BOILER.search(s):
                self.all.append(s)
                if self.depth: self.art.append(s)
    def handle_data(self, d):
        if self.p is not None: self.p.append(d)

def page_excerpt(url):
    body = fetch(url, accept="text/html,*/*", limit=700000, timeout=15).decode("utf8", "replace")
    p = Page(); p.feed(body)
    paras = p.art if len(p.art) >= 2 else p.all
    out, seen = [], set()
    meta = re.sub(r"\s+", " ", html.unescape(p.meta or "")).strip()
    if len(meta) >= 60: out.append(meta); seen.add(meta[:50])
    for s in paras:
        if s[:50] in seen: continue
        seen.add(s[:50]); out.append(s)
        if sum(len(x) for x in out) >= X_MAX: break
    return out

CATS = json.load(open(os.path.join(here, "categories.json"), encoding="utf8"))
for _c in CATS: _c["rx"] = re.compile(_c["re"], re.I)

def categorize(it):
    """Up to 3 category ids per item: title hits count double, only the first 300 chars of the summary are used."""
    title, desc = it["t"], (it.get("d") or "")[:300]
    scored = []
    for c in CATS:
        sc = (2 * len(c["rx"].findall(title)) + min(len(c["rx"].findall(desc)), 2)) * c.get("w", 1)
        if sc >= 1.4: scored.append((sc, c["id"]))
    scored.sort(key=lambda x: -x[0])
    return [i for _, i in scored[:3]]

prev_items = {}
try:
    for it in json.load(open(os.path.join(here, "news.json"), encoding="utf8")).get("items", []): prev_items[it["u"]] = it
except Exception: pass

feeds = json.load(open(os.environ.get("FEEDS_FILE") or os.path.join(here, "feeds.json")))
items = []
for f in feeds:
    try:
        root = ET.fromstring(fetch(f["url"]))
    except Exception as e:
        print("feed failed:", f["id"], e, file=sys.stderr); continue
    n = 0
    for e in [e for e in root.iter() if local(e.tag) in ("item", "entry")]:
        title = clean(text_of(child(e, "title")), 160)
        lk = child(e, "link")
        link = (lk.get("href") if lk is not None and lk.get("href") else text_of(lk)) if lk is not None else ""
        if lk is not None and not link:
            for c in e:
                if local(c.tag) == "link" and c.get("rel") in (None, "alternate") and c.get("href"): link = c.get("href"); break
        raw = text_of(child(e, "description", "summary"))
        full = text_of(child(e, "encoded", "content")) or raw
        d = parse_date(text_of(child(e, "pubDate", "published", "updated", "date")))
        if not title or not link or not d: continue
        if (now - d).days >= DAYS or d > now + datetime.timedelta(hours=2): continue
        desc = clean(raw or full)
        if f.get("filter") and not KW.search(title + " " + desc): continue
        it = {"t": title, "d": desc, "u": link, "p": d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "s": f["id"], "i": image_of(e, full)}
        old = prev_items.get(link)
        if old and len(old.get("x", "")) >= X_MIN: it["x"] = old["x"]
        else: it["x"] = join_x(paras_from_html(full)) or desc
        items.append(it); n += 1
    print(f["id"], n)

# enrich short excerpts from the article page itself (newest first, capped per run)
fetched = 0
for it in sorted(items, key=lambda x: x["p"], reverse=True):
    if fetched >= PAGE_FETCH: break
    if len(it.get("x", "")) >= X_MIN: continue
    fetched += 1
    try:
        ps = page_excerpt(it["u"])
        if ps:
            x = join_x(ps)
            if len(x) > len(it.get("x", "")): it["x"] = x
    except Exception as e:
        print("page failed:", it["u"][:70], e, file=sys.stderr)
print("pages fetched:", fetched)

have = {i["u"] for i in items}
for old in prev_items.values():
    d = parse_date(old["p"].replace("Z", ":00+00:00")) if len(old["p"]) == 17 else parse_date(old["p"])
    if old["u"] not in have and d and (now - d).days < DAYS: items.append(old)
seen, out = set(), []
for it in sorted(items, key=lambda x: x["p"], reverse=True):
    k = re.sub(r"\W+", "", it["t"].lower())[:60]
    if it["u"] in seen or k in seen: continue
    seen.add(it["u"]); seen.add(k); out.append(it)
out = out[:MAX_ITEMS]
for it in out: it["c"] = categorize(it) or ["other"]
if not out:
    print("no items fetched; keeping previous news.json", file=sys.stderr); sys.exit(0)
used = {i["s"] for i in out}
srcs = [{"id": f["id"], "name": f["name"], "lang": f["lang"]} for f in feeds if f["id"] in used]
# our own content (blog posts + YouTube videos) so the page can link related news to it
own = []
try:
    cfg = json.load(open(os.path.join(here, "own.json"), encoding="utf8"))
except Exception:
    cfg = {}
if cfg.get("blog"):
    try:
        j = json.loads(fetch(cfg["blog"].rstrip("/") + "/feeds/posts/summary?alt=json&max-results=150", accept="application/json"))
        for e in j.get("feed", {}).get("entry", []):
            u = next((l["href"] for l in e.get("link", []) if l.get("rel") == "alternate"), "")
            if u: own.append({"k": "p", "t": e["title"]["$t"][:140], "u": u, "c": [c["term"] for c in e.get("category", [])][:4]})
    except Exception as e:
        print("blog feed failed:", e, file=sys.stderr)
for ch in cfg.get("youtube_channels", []):
    try:
        root = ET.fromstring(fetch("https://www.youtube.com/feeds/videos.xml?channel_id=" + ch))
        for e in [e for e in root.iter() if local(e.tag) == "entry"]:
            vid = text_of(child(e, "videoId")); ttl = text_of(child(e, "title"))
            if vid and ttl: own.append({"k": "v", "t": ttl[:140], "u": "https://www.youtube.com/watch?v=" + vid})
    except Exception as e:
        print("youtube feed failed:", ch, e, file=sys.stderr)
if not own:  # keep the previous list when both fetches fail
    try: own = json.load(open(os.path.join(here, "news.json"), encoding="utf8")).get("own", [])
    except Exception: own = []
print("own items:", len(own))
new_doc = ({"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "sources": srcs, "items": out, "own": own, "cats": [{"id": c["id"], "l": c["l"], "g": c["g"]} for c in CATS] + [{"id": "other", "l": "أخبار عامة", "g": "أخرى"}]})
# Keep the repository history small: write only when something other than the timestamp changed, or when the file is 3+ hours old.
path_news = os.path.join(here, "news.json")
try:
    prev = json.load(open(path_news, encoding="utf8"))
    same = all(prev.get(k) == new_doc.get(k) for k in ("sources", "items", "own", "cats"))
    age_h = (now - datetime.datetime.strptime(prev["updated"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc)).total_seconds() / 3600
except Exception: same, age_h = False, 99
if same and age_h < 3: print("news unchanged; keeping the previous file")
else: json.dump(new_doc, open(path_news, "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
print("wrote", len(out), "items")
