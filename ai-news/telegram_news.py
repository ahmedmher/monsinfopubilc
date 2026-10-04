#!/usr/bin/env python3
"""Telegram bot for the AI news.
  python3 telegram_news.py --subs   : handle /start and /stop (runs every ~15 min), welcome new subscribers + send them the latest stories
  python3 telegram_news.py          : broadcast the newest stories to every subscriber (and to TELEGRAM_CHAT_ID if set: a channel or your own chat)
Secrets: TELEGRAM_BOT_TOKEN (required), TELEGRAM_CHAT_ID (optional extra target).
The subscriber list is stored encrypted (telegram-subs.dat) because this repository is public; the token is the key. The token is never printed."""
import base64, datetime, hashlib, hmac, html, json, os, sys, time, urllib.error, urllib.parse, urllib.request
here = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
EXTRA = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
API = os.environ.get("TELEGRAM_API", "https://api.telegram.org")
NEWS_PAGE = os.environ.get("NEWS_PAGE", "https://www.monsinfo.com/p/ai-news.html")
SITE = os.environ.get("SITE_URL", "https://www.monsinfo.com")
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", 3))
MAX_AGE_H = int(os.environ.get("MAX_AGE_HOURS", 12))
AUTH = {"openai": 3, "anthropic": 3, "claude": 2.5, "anthropic-r": 2.5, "deepmind": 3, "googleai": 3, "hf": 2.5, "msai": 2.5, "nvidia": 2.5,
        "mit": 2, "ars": 2, "verge": 2, "techcrunch": 2, "venturebeat": 1.5, "aitnews": 2, "scmp": 1.5, "technode": 1, "pandaily": 1.5}
if not TOKEN:
    print("TELEGRAM_BOT_TOKEN is not set; skipping"); sys.exit(0)
KEY = hashlib.sha256(("subs:" + TOKEN).encode()).digest()

def _ks(nonce, n):
    out, c = b"", 0
    while len(out) < n:
        out += hmac.new(KEY, nonce + c.to_bytes(4, "big"), "sha256").digest(); c += 1
    return out[:n]
def seal(obj):
    data = json.dumps(obj, separators=(",", ":")).encode(); nonce = os.urandom(16)
    ct = bytes(a ^ b for a, b in zip(data, _ks(nonce, len(data))))
    return base64.b64encode(nonce + hmac.new(KEY, nonce + ct, "sha256").digest() + ct).decode()
def unseal(s):
    raw = base64.b64decode(s); nonce, tag, ct = raw[:16], raw[16:48], raw[48:]
    if not hmac.compare_digest(tag, hmac.new(KEY, nonce + ct, "sha256").digest()): raise ValueError("bad subscriber file")
    return json.loads(bytes(a ^ b for a, b in zip(ct, _ks(nonce, len(ct)))))

def tg(method, **p):
    req = urllib.request.Request("%s/bot%s/%s" % (API, TOKEN, method), data=urllib.parse.urlencode(p).encode(), method="POST")
    try:
        return json.loads(urllib.request.urlopen(req, timeout=40).read())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read())
        except Exception: return {"ok": False, "error_code": e.code, "description": str(e.code)}
def tr(text):
    try:
        u = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ar&dt=t&q=" + urllib.parse.quote(text)
        j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read())
        return "".join(x[0] for x in j[0] if x and x[0]).strip() or None
    except Exception:
        return None
def nid(u):  # same hash as the page JavaScript (djb2 over UTF-16 code units)
    h = 5381; b = u.encode("utf-16-le")
    for i in range(0, len(b), 2): h = ((h << 5) + h + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    s = ""
    while True:
        h, r = divmod(h, 36); s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
        if h == 0: return s

news = json.load(open(os.path.join(here, "news.json"), encoding="utf8"))
names = {s["id"]: s["name"] for s in news.get("sources", [])}
langs = {s["id"]: s.get("lang", "en") for s in news.get("sources", [])}
subs_path = os.path.join(here, "telegram-subs.dat"); state_path = os.path.join(here, "telegram-state.json")
try: subs = unseal(open(subs_path).read())
except Exception: subs = {"chats": [], "offset": 0}
try: state = json.load(open(state_path)); first_run = False
except Exception: state = {"sent": []}; first_run = True
sent = set(state["sent"])

def story_text(it):
    en = langs.get(it["s"]) != "ar"
    ar = tr(it["t"]) if en else None
    head = "<b>%s</b>\n<i>%s</i>" % (html.escape(ar), html.escape(it["t"])) if ar else "<b>%s</b>" % html.escape(it["t"])
    d = it.get("d") or ""
    desc = html.escape(d[:220].rsplit(" ", 1)[0] + ("…" if len(d) > 220 else ""))
    link = "%s#/n/%s" % (NEWS_PAGE, nid(it["u"]))
    return "🆕 %s\n\n%s\n\n📰 المصدر: %s\n👉 <a href=\"%s\">اقرأ ملخص الخبر</a>" % (head, desc, html.escape(names.get(it["s"], it["s"])), html.escape(link, quote=True))
def send(chat, text):
    for _ in range(3):
        r = tg("sendMessage", chat_id=chat, text=text, parse_mode="HTML", disable_web_page_preview="true")
        if r.get("ok"): return "ok"
        if r.get("error_code") == 429: time.sleep(int(r.get("parameters", {}).get("retry_after", 3)) + 1); continue
        if r.get("error_code") in (400, 403) and str(chat).lstrip("-").isdigit(): return "gone"   # blocked the bot / chat deleted
        print("send failed:", str(r.get("description"))[:120], file=sys.stderr); return "err"
    return "err"
def age_h(it):
    return (time.time() - datetime.datetime.strptime(it["p"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc).timestamp()) / 3600
def ranked(items, limit_age=None):
    c = [i for i in items if i["s"] in AUTH and (limit_age is None or age_h(i) <= limit_age)]
    c.sort(key=lambda i: -(AUTH[i["s"]] + 0.4 * len([x for x in i.get("c", []) if x != "other"]) + max(0, 1 - age_h(i) / 72)))
    return c

WELCOME = ("أهلا بك في بوت <b>أخبار الذكاء الاصطناعي</b> من مونستر للمعلوميات 👋\n\nسيصلك هنا أهم أخبار الذكاء الاصطناعي تلقائيا مع رابط لقراءة ملخص كل خبر على موقعنا.\n\n"
           "🌐 <a href=\"%s\">الموقع</a>\nلإيقاف الأخبار أرسل /stop، ولإعادة تشغيلها أرسل /start." % SITE)

if "--subs" in sys.argv:
    tg("deleteWebhook")  # getUpdates does not work while a webhook is set
    r = tg("getUpdates", offset=subs.get("offset", 0), timeout=0, allowed_updates=json.dumps(["message"]))
    new_subs = []
    if r.get("ok"):
        for u in r.get("result", []):
            subs["offset"] = max(subs.get("offset", 0), u["update_id"] + 1)
            m = u.get("message") or {}; chat = (m.get("chat") or {}); text = (m.get("text") or "").strip().lower()
            if chat.get("type") != "private" or "id" not in chat: continue
            cid = chat["id"]
            if text.startswith("/stop"):
                if cid in subs["chats"]: subs["chats"].remove(cid); send(cid, "تم إيقاف الأخبار ✅ لإعادة تشغيلها أرسل /start")
            elif text.startswith("/start") or text:   # any message subscribes
                if cid not in subs["chats"]:
                    subs["chats"].append(cid); new_subs.append(cid)
    else:
        print("getUpdates failed:", str(r.get("description"))[:120], file=sys.stderr)
    new_subs = [c for c in new_subs if c in subs["chats"]]   # skip anyone who sent /stop in the same batch
    top = ranked(news["items"], 72)[:MAX_PER_RUN]
    for cid in new_subs:
        send(cid, WELCOME); time.sleep(0.5)
        for it in top: send(cid, story_text(it)); time.sleep(0.6)
    open(subs_path, "w").write(seal(subs))
    print("subscribers:", len(subs["chats"]), "| new this run:", len(new_subs)); sys.exit(0)

# --- broadcast mode ---
fresh = [i for i in ranked([i for i in news["items"] if i["u"] not in sent], MAX_AGE_H)]
pick = fresh[:MAX_PER_RUN]
targets = list(subs["chats"]) + ([EXTRA] if EXTRA and EXTRA not in map(str, subs["chats"]) else [])
if not targets:
    print("no subscribers yet and no TELEGRAM_CHAT_ID; nothing to send"); sys.exit(0)
removed = False
done = 0
for it in pick:
    text = story_text(it); ok = 0
    for chat in list(targets):
        res = send(chat, text)
        if res == "ok": ok += 1
        elif res == "gone" and chat in subs["chats"]: subs["chats"].remove(chat); removed = True
        time.sleep(0.07)
    sent.add(it["u"]); done += 1; print("story sent to %d chats: %s" % (ok, it["t"][:50]))
if first_run: sent.update(i["u"] for i in news["items"])   # never dump the whole archive on the first run
state["sent"] = sorted(sent)[-1500:]
json.dump(state, open(state_path, "w"), separators=(",", ":"))
if removed: open(subs_path, "w").write(seal(subs))   # only rewrite the subscriber file when someone blocked the bot
print("done; stories:", done, "| targets:", len(targets))
