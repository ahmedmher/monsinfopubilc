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
TR_STATS = {"gtx": 0, "chrome": 0, "mymemory": 0, "lingva": 0, "fail": 0}
TRB = os.environ.get("TRANSLATE_BASE", "https://translate.googleapis.com")
def _get(url, timeout=12):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}), timeout=timeout).read()
def _providers(q):
    qq = urllib.parse.quote(q)
    yield "gtx", lambda: "".join(x[0] for x in json.loads(_get(TRB + "/translate_a/single?client=gtx&sl=en&tl=ar&dt=t&q=" + qq))[0] if x and x[0])
    yield "chrome", lambda: (lambda j: j[0] if isinstance(j[0], str) else j[0][0])(json.loads(_get("https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=en&tl=ar&q=" + qq)))
    yield "mymemory", lambda: (lambda j: j["responseData"]["translatedText"] if int(j.get("responseStatus", 0)) == 200 else (_ for _ in ()).throw(ValueError("mm")))(json.loads(_get("https://api.mymemory.translated.net/get?q=%s&langpair=en|ar" % qq)))
    for inst in ("https://lingva.ml", "https://lingva.garudalinux.org"):
        yield "lingva", (lambda inst=inst: json.loads(_get("%s/api/v1/en/ar/%s" % (inst, qq)))["translation"])
def tr(text, limit=450):
    """Arabic translation of a short English text; tries several free providers, returns None if all fail."""
    text = (text or "").strip()
    if not text: return None
    parts, cur = [], ""
    for seg in text.replace("\n", " ").split(". "):
        if len(cur) + len(seg) + 2 > limit and cur: parts.append(cur); cur = seg
        else: cur = (cur + ". " + seg) if cur else seg
    if cur: parts.append(cur)
    out = []
    for part in parts:
        got = None
        for name, fn in _providers(part[:limit]):
            try:
                r = (fn() or "").strip()
                if r and r != part: TR_STATS[name] += 1; got = r; break
            except Exception:
                continue
        if not got: TR_STATS["fail"] += 1; return None
        out.append(got)
    return " ".join(out)
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
    ar_t = tr(it["t"]) if en else None
    d = (it.get("d") or "")
    d = d[:260].rsplit(" ", 1)[0] + ("…" if len(d) > 260 else "") if d else ""
    ar_d = tr(d) if (en and d) else None
    head = "<b>%s</b>\n<i>%s</i>" % (html.escape(ar_t), html.escape(it["t"])) if ar_t else "<b>%s</b>" % html.escape(it["t"])
    body = html.escape(ar_d or d)
    link = "%s#/n/%s%s" % (NEWS_PAGE, nid(it["u"]), "/ar" if en else "")
    label = "اقرأ ملخص الخبر مع الترجمة" if en else "اقرأ ملخص الخبر"
    return "🆕 %s\n\n%s\n\n📰 المصدر: %s\n👉 <a href=\"%s\">%s</a>" % (head, body, html.escape(names.get(it["s"], it["s"])), html.escape(link, quote=True), label)
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


# ---------- new long YouTube videos -> subscribers (shorts are skipped) ----------
import re as _re
import xml.etree.ElementTree as _ET
YT = os.environ.get("YT_BASE", "https://www.youtube.com")
videos_path = os.path.join(here, "telegram-videos.json")
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
def is_short(vid):
    """/shorts/<id> answers 200 for Shorts and redirects to /watch for normal videos."""
    try:
        op = urllib.request.build_opener(_NoRedirect)
        r = op.open(urllib.request.Request("%s/shorts/%s" % (YT, vid), headers={"User-Agent": "Mozilla/5.0"}), timeout=15)
        return r.status == 200
    except urllib.error.HTTPError as e:
        return False if e.code in (301, 302, 303, 307, 308) else False
    except Exception:
        return False
def watch_videos(targets):
    try: cfg = json.load(open(os.path.join(here, "own.json"), encoding="utf8"))
    except Exception: return 0
    try: vs = json.load(open(videos_path)); first = False
    except Exception: vs = {"sent": [], "ids": {}}; first = True
    chans = list(cfg.get("youtube_channels", []))
    for h in cfg.get("youtube_handles", []):
        cid = vs["ids"].get(h)
        if not cid:
            try:
                page = _get("%s/%s" % (YT, h.lstrip("/")), 20).decode("utf8", "replace")
                m = _re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', page) or _re.search(r'channel_id=(UC[\w-]{22})', page)
                cid = m.group(1) if m else None
            except Exception as e:
                print("channel lookup failed:", h, str(e)[:80], file=sys.stderr)
            if cid: vs["ids"][h] = cid
        if cid: chans.append(cid)
    sent_v = set(vs["sent"]); n = 0
    for cid in dict.fromkeys(chans):
        try: root = _ET.fromstring(_get("%s/feeds/videos.xml?channel_id=%s" % (YT, cid), 20))
        except Exception as e:
            print("feed failed:", cid, str(e)[:80], file=sys.stderr); continue
        ns = {"a": "http://www.w3.org/2005/Atom", "y": "http://www.youtube.com/xml/schemas/2015"}
        author = (root.findtext("a:author/a:name", namespaces=ns) or "").strip()
        entries = []
        for e in root.findall("a:entry", ns):
            vid = e.findtext("y:videoId", namespaces=ns); title = (e.findtext("a:title", namespaces=ns) or "").strip()
            pub = e.findtext("a:published", namespaces=ns) or ""
            if vid and title: entries.append((pub, vid, title))
        for pub, vid, title in sorted(entries):
            if vid in sent_v: continue
            sent_v.add(vid)
            if first: continue                       # first run: remember the existing videos, do not announce them
            if is_short(vid): continue               # only long videos
            text = "🎬 <b>فيديو جديد على قناة %s</b>\n\n%s\n\n▶️ <a href=\"https://www.youtube.com/watch?v=%s\">شاهد الفيديو الآن</a>" % (html.escape(author or "يوتيوب"), html.escape(title), vid)
            for chat in targets:
                send(chat, text); time.sleep(0.07)
            n += 1; print("video announced:", title[:50])
    vs["sent"] = sorted(sent_v)[-600:]
    json.dump(vs, open(videos_path, "w"), separators=(",", ":"))
    return n

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
    nv = watch_videos(list(subs["chats"]) + ([EXTRA] if EXTRA else []))
    print("videos announced:", nv)
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
state["last"] = {"at": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "translate": TR_STATS}
json.dump(state, open(state_path, "w"), separators=(",", ":"))
if removed: open(subs_path, "w").write(seal(subs))   # only rewrite the subscriber file when someone blocked the bot
print("done; stories:", done, "| targets:", len(targets))
