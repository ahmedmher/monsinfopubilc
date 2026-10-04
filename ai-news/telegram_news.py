#!/usr/bin/env python3
"""Post the newest AI news to a Telegram channel, each with a link to the story page on the blog.
Secrets (GitHub Actions): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (default @code_hup). The bot must be an admin of the channel.
State: telegram-state.json (URLs already sent). Never prints the token."""
import json, os, re, sys, html, time, urllib.parse, urllib.request
here = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("8974402385:AAHehqjmtJoMCG85S6OA14kwJeJ3W1Mo6CM", "").strip()
CHAT = os.environ.get("@Ai_news_updatebot", "").strip() or "@code_hup"
API = os.environ.get("TELEGRAM_API", "https://api.telegram.org")
NEWS_PAGE = os.environ.get("NEWS_PAGE", "https://www.monsinfo.com/p/ai-news.html")
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", 3))
MAX_AGE_H = int(os.environ.get("MAX_AGE_HOURS", 12))
AUTH = {"openai": 3, "anthropic": 3, "claude": 2.5, "anthropic-r": 2.5, "deepmind": 3, "googleai": 3, "hf": 2.5, "msai": 2.5, "nvidia": 2.5,
        "mit": 2, "ars": 2, "verge": 2, "techcrunch": 2, "venturebeat": 1.5, "aitnews": 2, "scmp": 1.5, "technode": 1, "pandaily": 1.5}
if not TOKEN:
    print("TELEGRAM_BOT_TOKEN is not set; skipping"); sys.exit(0)

def nid(u):  # same hash as the page's JavaScript (djb2 over UTF-16 code units)
    h = 5381
    b = u.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h = ((h << 5) + h + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    s = ""
    while True:
        h, r = divmod(h, 36); s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
        if h == 0: return s

def tr(text):  # best-effort Arabic title (unofficial endpoint); falls back to None
    try:
        u = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ar&dt=t&q=" + urllib.parse.quote(text)
        j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read())
        s = "".join(x[0] for x in j[0] if x and x[0]).strip()
        return s or None
    except Exception:
        return None

def tg(method, **p):
    req = urllib.request.Request("%s/bot%s/%s" % (API, TOKEN, method), data=urllib.parse.urlencode(p).encode(), method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

news = json.load(open(os.path.join(here, "news.json"), encoding="utf8"))
names = {s["id"]: s["name"] for s in news.get("sources", [])}
langs = {s["id"]: s.get("lang", "en") for s in news.get("sources", [])}
sp = os.path.join(here, "telegram-state.json")
try: state = json.load(open(sp)); first_run = False
except Exception: state = {"sent": []}; first_run = True
sent = set(state["sent"])
now = time.time()
def age_h(it):
    import datetime
    return (now - datetime.datetime.strptime(it["p"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc).timestamp()) / 3600
fresh = [i for i in news["items"] if i["u"] not in sent and age_h(i) <= MAX_AGE_H and i["s"] in AUTH]
fresh.sort(key=lambda i: -(AUTH[i["s"]] + 0.4 * len([c for c in i.get("c", []) if c != "other"]) + max(0, 1 - age_h(i) / MAX_AGE_H)))
pick = fresh[:MAX_PER_RUN]
for it in pick:
    en = langs.get(it["s"]) != "ar"
    title = html.escape(it["t"]); ar = tr(it["t"]) if en else None
    head = "<b>%s</b>\n<i>%s</i>" % (html.escape(ar), title) if ar else "<b>%s</b>" % title
    desc = html.escape((it.get("d") or "")[:220].rsplit(" ", 1)[0] + ("…" if len(it.get("d") or "") > 220 else "")) if it.get("d") else ""
    link = "%s#/n/%s" % (NEWS_PAGE, nid(it["u"]))
    text = "🆕 %s\n\n%s\n\n📰 المصدر: %s\n👉 <a href=\"%s\">اقرأ ملخص الخبر</a>" % (head, desc, html.escape(names.get(it["s"], it["s"])), html.escape(link, quote=True))
    try:
        r = tg("sendMessage", chat_id=CHAT, text=text, parse_mode="HTML", disable_web_page_preview="true")
        if not r.get("ok"): raise RuntimeError(r.get("description"))
        sent.add(it["u"]); print("sent:", it["t"][:60])
        time.sleep(1.5)
    except Exception as e:
        print("send failed:", str(e).replace(TOKEN, "***")[:160], file=sys.stderr); break
# remember everything currently in the archive on the first run so old news is never dumped into the channel
if first_run: sent.update(i["u"] for i in news["items"])
state["sent"] = sorted(sent)[-1500:]
json.dump(state, open(sp, "w"), separators=(",", ":"))
print("done; sent this run:", len(pick))
