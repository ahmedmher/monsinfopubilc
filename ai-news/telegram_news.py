#!/usr/bin/env python3
"""AI-news Telegram bot (Arabic only).

  python3 telegram_news.py --subs [--duration 780]
      Long-polls Telegram: /start, /topics (pick categories), /daily, /live, /status, /stop and the inline buttons.
      Also announces new long YouTube videos. Writes telegram-subs.dat (encrypted) and telegram-videos.json.
  python3 telegram_news.py
      Hourly job after the news fetch: (1) model alerts when a rumoured model is released, (2) top stories every 6 hours
      to subscribers in "live" mode (filtered by their topics), (3) one morning digest for "daily" subscribers.

Secrets: TELEGRAM_BOT_TOKEN (required), TELEGRAM_CHAT_ID (optional extra target, e.g. a channel; gets everything).
The subscriber list is encrypted because the repository is public; the token is the key and is never printed."""
import base64, datetime, hashlib, hmac, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
here = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
EXTRA = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
_adm = [a.strip().lstrip("@") for a in (os.environ.get("TELEGRAM_ADMIN_ID", "") + "," + os.environ.get("TELEGRAM_CHAT_ID", "")).split(",") if a.strip()]
ADMIN = [a for a in _adm if a.isdigit()]                       # numeric chat ids
ADMIN_NAMES = [a.lower() for a in _adm if not a.lstrip("-").isdigit()]   # Telegram usernames
API = os.environ.get("TELEGRAM_API", "https://api.telegram.org")
NEWS_PAGE = os.environ.get("NEWS_PAGE", "https://www.monsinfo.com/p/ai-news.html")
SITE = os.environ.get("SITE_URL", "https://www.monsinfo.com")
YT = os.environ.get("YT_BASE", "https://www.youtube.com")
TRB = os.environ.get("TRANSLATE_BASE", "https://translate.googleapis.com")
LIVE_COUNT = int(os.environ.get("LIVE_COUNT", 10)); LIVE_AGE_H = int(os.environ.get("LIVE_AGE_HOURS", 12))   # batch mode: max stories in one message, max story age
BATCH_H = float(os.environ.get("BATCH_HOURS", 3)); INSTANT_MIN = float(os.environ.get("INSTANT_MIN_AUTH", 2))   # hours between batches; minimum source authority
SUM_CHARS = int(os.environ.get("SUMMARY_CHARS", 200))   # length of each news summary in the batch/digest messages (about 2-3 phone lines)
PROMO_FROM = int(os.environ.get("PROMO_FROM_HOUR", 18))   # the daily promo links ride the first message sent after this local hour
DEFAULT_PROMO = [["لشراء حسابات مواقع AI بسعر مخفض", "https://www.gamsgo.com/partner/phsyg"], ["أقوى موقع ذكاء اصطناعي مع خصم 50%", "https://higgsfield.ai/?fpr=register"], ["احصل على حساب بنكي أمريكي وبطاقة للدفع والتسوق", "https://www.kcard.site/"]]
GATE = os.environ.get("BOT_GATE", "@code_hup")   # users must be members of this channel (set to off to disable)
DIGEST_HOURS = os.environ.get("DIGEST_HOURS", "9,21"); DIGEST_COUNT = int(os.environ.get("DIGEST_COUNT", 5)); TZ = os.environ.get("BOT_TZ", "Africa/Cairo")   # digests at these local hours
POLL_T = int(os.environ.get("POLL_TIMEOUT", 25))
AUTH = {"openai": 3, "anthropic": 3, "claude": 2.5, "anthropic-r": 2.5, "deepmind": 3, "googleai": 3, "hf": 2.5, "msai": 2.5, "nvidia": 2.5,
        "mit": 2, "ars": 2, "verge": 2, "techcrunch": 2, "venturebeat": 1.5, "aitnews": 2, "scmp": 1.5, "technode": 1, "pandaily": 1.5}
if not TOKEN:
    print("TELEGRAM_BOT_TOKEN is not set; skipping"); sys.exit(0)
KEY = hashlib.sha256(("subs:" + TOKEN).encode()).digest()
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
def ar_date(iso): d = datetime.date.fromisoformat(iso[:10]); return "%d %s" % (d.day, MONTHS[d.month - 1])
def ar_days(n): return "اليوم نفسه" if n == 0 else "يوم واحد" if n == 1 else "يومين" if n == 2 else ("%d أيام" % n if n <= 10 else "%d يوما" % n)

# ---------------- crypto for the subscriber file ----------------
def _ks(nonce, n):
    out, c = b"", 0
    while len(out) < n: out += hmac.new(KEY, nonce + c.to_bytes(4, "big"), "sha256").digest(); c += 1
    return out[:n]
def seal(obj):
    data = json.dumps(obj, separators=(",", ":")).encode(); nonce = os.urandom(16)
    ct = bytes(a ^ b for a, b in zip(data, _ks(nonce, len(data))))
    return base64.b64encode(nonce + hmac.new(KEY, nonce + ct, "sha256").digest() + ct).decode()
def unseal(s):
    raw = base64.b64decode(s); nonce, tag, ct = raw[:16], raw[16:48], raw[48:]
    if not hmac.compare_digest(tag, hmac.new(KEY, nonce + ct, "sha256").digest()): raise ValueError("bad subscriber file")
    return json.loads(bytes(a ^ b for a, b in zip(ct, _ks(nonce, len(ct)))))

# ---------------- telegram + translation ----------------
def tg(method, **p):
    p = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in p.items()}
    req = urllib.request.Request("%s/bot%s/%s" % (API, TOKEN, method), data=urllib.parse.urlencode(p).encode(), method="POST")
    try: return json.loads(urllib.request.urlopen(req, timeout=POLL_T + 20).read())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read())
        except Exception: return {"ok": False, "error_code": e.code, "description": str(e.code)}
    except Exception as e:
        return {"ok": False, "description": str(e).replace(TOKEN, "***")[:100]}
TR_STATS = {"gtx": 0, "chrome": 0, "mymemory": 0, "lingva": 0, "fail": 0}
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
            except Exception: continue
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
def send(chat, text, markup=None):
    for _ in range(3):
        kw = dict(chat_id=chat, text=text, parse_mode="HTML", disable_web_page_preview="true")
        if markup: kw["reply_markup"] = markup
        r = tg("sendMessage", **kw)
        if r.get("ok"): return "ok"
        if r.get("error_code") == 429: time.sleep(int(r.get("parameters", {}).get("retry_after", 3)) + 1); continue
        if r.get("error_code") in (400, 403) and str(chat).lstrip("-").isdigit(): return "gone"
        print("send failed:", str(r.get("description"))[:100], file=sys.stderr); return "err"
    return "err"

# ---------------- data ----------------
def load_json(p, d):
    try: return json.load(open(os.path.join(here, p), encoding="utf8"))
    except Exception: return d
news = load_json("news.json", {"items": [], "sources": [], "cats": []})
tracker = load_json("model-tracker.json", {"models": []})
names = {s["id"]: s["name"] for s in news.get("sources", [])}
langs = {s["id"]: s.get("lang", "en") for s in news.get("sources", [])}
CATS = [c for c in news.get("cats", []) if c["id"] != "other"]
CATL = {c["id"]: c["l"] for c in CATS}
GROUPS = list(dict.fromkeys(c["g"] for c in CATS))
subs_path = os.path.join(here, "telegram-subs.dat"); state_path = os.path.join(here, "telegram-state.json"); videos_path = os.path.join(here, "telegram-videos.json")
try: subs = unseal(open(subs_path).read())
except Exception: subs = {"offset": 0, "users": {}}
if "chats" in subs:   # migrate the first version of the file
    subs["users"] = subs.get("users", {}); [subs["users"].setdefault(str(c), {"mode": "live", "topics": []}) for c in subs.pop("chats")]
subs.setdefault("users", {}); subs.setdefault("offset", 0)
CFG_KEYS = {  # key: (global name, converter, Arabic label)
    "live_count": ("LIVE_COUNT", int, "أقصى عدد أخبار في رسالة الأخبار الجديدة"), "batch_hours": ("BATCH_H", float, "الفاصل بالساعات بين رسائل الأخبار الجديدة (3 = كل 3 ساعات)"), "promo_from": ("PROMO_FROM", int, "الروابط الإعلانية تُرفق بأول رسالة بعد هذه الساعة المحلية (18 = 6 مساء)"),
    "instant_min": ("INSTANT_MIN", float, "أقل وزن لمصدر الخبر (2 = المصادر الكبرى فقط، 1 = الكل)"), "live_age": ("LIVE_AGE_H", int, "أقصى عمر للخبر المرسل بالساعات"),
    "gate": ("GATE", str, "القناة التي يجب الاشتراك فيها قبل استخدام البوت (اكتب off لإيقاف الشرط)"), "digest_hours": ("DIGEST_HOURS", str, "ساعات الملخص اليومي بتوقيتك مفصولة بفاصلة، مثل 9,21"), "tz": ("TZ", str, "المنطقة الزمنية، مثل Africa/Cairo"),
    "digest_count": ("DIGEST_COUNT", int, "عدد أخبار كل ملخص"), "sumchars": ("SUM_CHARS", int, "طول ملخص كل خبر بالحروف (200 = سطران أو ثلاثة، 0 = عنوان فقط)"), "ref_hold": ("REF_HOLD", lambda h: int(float(h) * 3600), "ساعات بقاء المدعو لاحتساب النقطة"),
    "ref_cap": ("REF_DAILY_CAP", int, "أقصى نقاط إحالة يوميا للشخص")}
def apply_cfg():
    for k, v in subs.get("cfg", {}).items():
        if k in CFG_KEYS:
            try: globals()[CFG_KEYS[k][0]] = CFG_KEYS[k][1](v)
            except Exception: pass
def save_subs(): open(subs_path, "w").write(seal(subs))
def hist(key):
    h = subs.setdefault("hist", {}); d = h.setdefault(time.strftime("%Y-%m-%d", time.gmtime()), {"new": 0, "stop": 0}); d[key] += 1
    for k in sorted(h)[:-90]: del h[k]
def user(cid):
    k = str(cid)
    if k not in subs["users"]: subs["users"][k] = {"mode": "live", "topics": [], "j": time.strftime("%Y-%m-%d", time.gmtime()), "jt": int(time.time())}; hist("new")
    return subs["users"][k]

def age_h(it):
    return (time.time() - datetime.datetime.strptime(it["p"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc).timestamp()) / 3600
def ranked(items, limit_age, topics=None):
    c = [i for i in items if i["s"] in AUTH and age_h(i) <= limit_age and (not topics or set(topics) & set(i.get("c", [])))]
    c.sort(key=lambda i: -(AUTH[i["s"]] + 0.4 * len([x for x in i.get("c", []) if x != "other"]) + max(0, 1 - age_h(i) / max(limit_age, 1))))
    return c
trcache = {}   # url -> {"t": arabic title, "d": arabic summary}; persisted in telegram-state.json
def arabic(it):
    """Arabic title/summary of a story, or None when it cannot be translated (we never send English)."""
    if it["u"] in trcache: return trcache[it["u"]]
    if langs.get(it["s"]) == "ar":
        r = {"t": it["t"], "d": (it.get("d") or "")[:260]}
    else:
        t = tr(it["t"]);
        if not t: return None
        d = (it.get("d") or ""); d = d[:260].rsplit(" ", 1)[0] + ("…" if len(d) > 260 else "") if d else ""
        r = {"t": t, "d": (tr(d) if d else "") or ""}
    trcache[it["u"]] = r; return r
def _cut(t, n):
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= n: return t
    c = t[:n]; k = max(c.rfind(". "), c.rfind("، "), c.rfind("؛ "))
    if k > n * 0.55: return c[:k + 1].rstrip("،؛ ")
    return c.rsplit(" ", 1)[0].rstrip("،؛ .") + "…"
def arsum(it):
    """Arabic summary of about SUM_CHARS characters (2-3 phone lines), from the longer excerpt when the feed has one."""
    if SUM_CHARS <= 0: return ""
    a = arabic(it)
    if not a: return ""
    if "s" in a: return _cut(a["s"], SUM_CHARS)
    src = re.sub(r"\s+", " ", (it.get("x") or it.get("d") or "")).strip()
    out = ""
    for sent in re.split(r"(?<=[.!?؟]) ", src):
        if len(out) + len(sent) > 420 and out: break
        out += (" " if out else "") + sent
    out = out[:520]
    if langs.get(it["s"]) != "ar" and out:
        out = tr(out) or ""
    a["s"] = out or a.get("d", ""); trcache[it["u"]] = a
    return _cut(a["s"], SUM_CHARS)
def item_block(n, it):
    a = arabic(it)
    if not a: return None
    sm = arsum(it)
    if sm and a["t"][:25] in sm[:40]: sm = ""
    return "%d. <b>%s</b>%s\n<a href=\"%s\">اقرأ الملخص الكامل</a>" % (n, html.escape(a["t"]), ("\n" + html.escape(sm)) if sm else "", html.escape(link(it), quote=True))
def pack(header, blocks, limit=None):
    """Split into as few Telegram messages (max 4096 chars) as possible; the header goes on the first one."""
    limit = limit or (4000 - len(promo_html()))   # leave room for the promo links that may ride the last message
    msgs, cur = [], header
    for b in blocks:
        if len(cur) + len(b) + 2 > limit and cur != header and cur.strip():
            msgs.append(cur); cur = ""
        cur += ("\n\n" if cur else "") + b
    if cur.strip(): msgs.append(cur)
    return msgs
def link(it): return "%s%sutm_source=telegram&utm_medium=bot&utm_campaign=news#/n/%s%s" % (NEWS_PAGE, "&" if "?" in NEWS_PAGE else "?", nid(it["u"]), "" if langs.get(it["s"]) == "ar" else "/ar")
def story_text(it):
    a = arabic(it)
    if not a: return None
    lab = "اقرأ ملخص الخبر" if langs.get(it["s"]) == "ar" else "اقرأ ملخص الخبر مع الترجمة"
    return "🆕 <b>%s</b>\n\n%s\n\n📰 المصدر: %s\n👉 <a href=\"%s\">%s</a>" % (html.escape(a["t"]), html.escape(a["d"]), html.escape(names.get(it["s"], it["s"])), html.escape(link(it), quote=True), lab)

# ---------------- interactive settings (inline keyboard) ----------------
def kb_main(u):
    mode = u.get("mode", "live"); n = len(u.get("topics", []))
    rows = [[{"text": ("✅ " if mode == "live" else "") + "📰 الأخبار الجديدة كل 3 ساعات", "callback_data": "m:live"}],
            [{"text": ("✅ " if mode == "daily" else "") + "☀️🌙 ملخص مرتين يوميا (9 ص و9 م)", "callback_data": "m:daily"}],
            [{"text": "📂 " + g, "callback_data": "g:%d" % i} for i, g in enumerate(GROUPS[:1])]]
    rows = rows[:2] + [[{"text": "📂 " + g, "callback_data": "g:%d" % i}] for i, g in enumerate(GROUPS)]
    rows.append([{"text": "🌐 كل المواضيع" + (" ✅" if not n else ""), "callback_data": "all"}, {"text": "تم ✔️", "callback_data": "done"}])
    return {"inline_keyboard": rows}
def kb_group(u, gi):
    sel = set(u.get("topics", [])); cs = [c for c in CATS if c["g"] == GROUPS[gi]]
    rows = []
    for i in range(0, len(cs), 2):
        rows.append([{"text": ("✅ " if c["id"] in sel else "⬜ ") + c["l"], "callback_data": "t:%s:%d" % (c["id"], gi)} for c in cs[i:i + 2]])
    rows.append([{"text": "↩️ رجوع", "callback_data": "back"}, {"text": "تم ✔️", "callback_data": "done"}])
    return {"inline_keyboard": rows}
def settings_text(u):
    n = len(u.get("topics", []))
    return ("⚙️ <b>إعدادات الأخبار</b>\n\nنمط الإرسال: <b>%s</b>\nالمواضيع: <b>%s</b>\n\nاختر نمط الإرسال، ثم المجموعات لتحديد المواضيع التي تهمك. إن لم تختر شيئا تصلك كل المواضيع."
            % ("الأخبار الجديدة كل 3 ساعات في رسالة واحدة" if u.get("mode", "live") == "live" else "ملخص مرتين يوميا (9 صباحا و9 مساء)", ("%d موضوعا" % n) if n else "كل المواضيع"))
WELCOME = ("أهلا بك في بوت <b>أخبار الذكاء الاصطناعي</b> من مونستر للمعلوميات 👋\n\nسيصلك بالعربية أهم الأخبار مع رابط لقراءة ملخص كل خبر على موقعنا، وتنبيه فوري عندما يصدر نموذج كان مرتقبا، وفيديوهات القناة الجديدة.\n\n"
           "⚙️ /topics اختيار المواضيع ونمط الإرسال\n☀️ /daily ملخص مرتين يوميا (9 ص و9 م) بدل الرسائل المتفرقة\n📰 /live الأخبار الجديدة كل 3 ساعات في رسالة واحدة\n📋 /status حالتك\n🎁 /invite ادعُ أصدقاءك واربح جوائز\n⛔ /stop إيقاف\n\n🌐 <a href=\"%s\">الموقع</a>" % SITE)
def status_text(cid):
    u = user(cid); n = len(u.get("topics", []))
    names_ = "، ".join(CATL.get(t, t) for t in u.get("topics", [])[:12]) if n else "كل المواضيع"
    return "📋 <b>حالتك</b>\nالنمط: %s\nالمواضيع: %s\n\n⚙️ /topics للتعديل" % ("الأخبار الجديدة كل 3 ساعات في رسالة واحدة" if u["mode"] == "live" else "ملخص مرتين يوميا (9 صباحا و9 مساء)", html.escape(names_))
def stats_text():
    us = subs["users"].values(); n = len(subs["users"]); today = time.strftime("%Y-%m-%d", time.gmtime()); h = subs.get("hist", {})
    def days(k, nd): return sum(h.get((datetime.date.today() - datetime.timedelta(days=i)).isoformat(), {}).get(k, 0) for i in range(nd))
    live = sum(1 for u in us if u.get("mode", "live") == "live"); daily = n - live; withtopics = sum(1 for u in us if u.get("topics"))
    cnt = {}
    for u in us:
        for t in u.get("topics", []): cnt[t] = cnt.get(t, 0) + 1
    top = "، ".join("%s (%d)" % (CATL.get(t, t), c) for t, c in sorted(cnt.items(), key=lambda x: -x[1])[:8]) or "لا يوجد بعد"
    last = (load_json("telegram-state.json", {}) or {}).get("last", {})
    gate_note = ("\n\n⚠️ شرط القناة غير مفعّل لأن البوت لا يستطيع قراءة الأعضاء: %s\nأضِف البوت <b>مشرفا</b> في القناة %s" % (subs["gate_err"], GATE)) if (gate_on() and subs.get("gate_err")) else (("\n\n🔒 شرط القناة %s مفعّل. خارج القناة الآن: %d" % (GATE, sum(1 for x in subs["users"].values() if x.get("nm")))) if gate_on() else "")
    return ("📊 <b>إحصائيات البوت</b>\n\n👥 المشتركون الآن: <b>%d</b>\n📰 نمط كل 3 ساعات: %d\n☀️ ملخص مرتين يوميا: %d\n⚙️ اختاروا مواضيع محددة: %d\n\n"
            "➕ انضمام: اليوم %d | 7 أيام %d | 30 يوما %d\n➖ إيقاف: اليوم %d | 7 أيام %d | 30 يوما %d\n\n🔥 أكثر المواضيع: %s\n\n📨 آخر إرسال: %s (وصلت %s رسالة مباشرة، %s ملخص يومي)"
            % (n, live, daily, withtopics, days("new", 1), days("new", 7), days("new", 30), days("stop", 1), days("stop", 7), days("stop", 30), html.escape(top),
               last.get("at", "لم يحدث بعد"), (last.get("sent") or {}).get("live", 0), (last.get("sent") or {}).get("digest", 0)) + gate_note)
def edit(chat, mid, text, markup):
    tg("editMessageText", chat_id=chat, message_id=mid, text=text, parse_mode="HTML", reply_markup=markup)
# ---------------- channel membership gate ----------------
_mem = {}
def gate_on(): return bool(GATE) and GATE.lower() not in ("off", "none", "0")
def gate_url(): return "https://t.me/" + GATE.lstrip("@")
def is_member(uid, fresh=False):
    """True when the user is in the required channel. Fails open (True) when the bot cannot read members, so a missing admin right never locks everyone out."""
    if not gate_on(): return True
    c = _mem.get(uid)
    if c and not fresh and time.time() - c[0] < 600: return c[1]
    r = tg("getChatMember", chat_id=GATE, user_id=uid)
    if not r.get("ok"):
        subs["gate_err"] = str(r.get("description", "error"))[:90]; return True
    subs.pop("gate_err", None)
    res = r["result"]; ok = res.get("status") in ("member", "administrator", "creator") or (res.get("status") == "restricted" and res.get("is_member"))
    _mem[uid] = (time.time(), bool(ok)); return bool(ok)
def gate_kb(): return {"inline_keyboard": [[{"text": "📢 انضم إلى القناة", "url": gate_url()}], [{"text": "✅ انضممت، تحقق", "callback_data": "chk"}]]}
GATE_TEXT = "🔒 <b>يجب أن تكون عضوا في قناتنا</b> لاستخدام البوت.\n\n1) اضغط «انضم إلى القناة» وانضم.\n2) ارجع هنا واضغط «انضممت، تحقق».\n\n%s"
def gate_block(cid, payload=""):
    if str(cid) in subs["users"]: subs["users"][str(cid)]["nm"] = 1
    if payload: subs.setdefault("pref", {})[str(cid)] = payload
    send(cid, GATE_TEXT % gate_url(), gate_kb())
def welcome_new(cid):
    send(cid, subs.get("welcome") or WELCOME, MENU_KB)
    for it in ranked(news["items"], 72, None)[:LIVE_COUNT]:
        t = story_text(it)
        if t: send(cid, t); time.sleep(0.6)
def recheck_members(limit=150):
    """Every few hours: users who left the channel are paused and told how to come back; returning users are re-enabled."""
    ids = list(subs["users"]); i0 = subs.get("gate_i", 0) % max(1, len(ids)); batch = (ids[i0:] + ids[:i0])[:limit]; subs["gate_i"] = i0 + limit
    for c in batch:
        u = subs["users"].get(c)
        if not u: continue
        if not is_member(int(c), fresh=True):
            if not u.get("nm"): u["nm"] = 1; send(int(c), "⚠️ لاحظنا أنك غادرت قناتنا، فتوقفت الأخبار عنك.\n\nانضم من جديد ثم اضغط «تحقق» لتعود.\n" + gate_url(), gate_kb())
        elif u.get("nm"): u.pop("nm")
        time.sleep(0.05)
def handle_callback(cb):
    if cb.get("data", "").startswith("ad:"): return admin_cb(cb)
    cid = cb["message"]["chat"]["id"]; mid = cb["message"]["message_id"]; d = cb.get("data", "")
    adm = is_admin({"chat": cb["message"]["chat"], "from": cb.get("from")})
    if d == "chk":
        if is_member(cid, fresh=True):
            tg("answerCallbackQuery", callback_query_id=cb["id"], text="تم التحقق ✅ أهلا بك")
            pl = subs.get("pref", {}).pop(str(cid), "")
            for c in handle_message({"chat": {"id": cid, "type": "private"}, "from": cb.get("from"), "text": ("/start " + pl).strip()}): welcome_new(c)
        else: tg("answerCallbackQuery", callback_query_id=cb["id"], text="لم تنضم إلى القناة بعد. انضم أولا ثم اضغط تحقق.", show_alert="true")
        return
    if not adm and not is_member(cid): tg("answerCallbackQuery", callback_query_id=cb["id"]); return gate_block(cid)
    u = user(cid)
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    if d.startswith("m:"): u["mode"] = d[2:] if d[2:] in ("live", "daily") else "live"; edit(cid, mid, settings_text(u), kb_main(u))
    elif d == "all": u["topics"] = []; edit(cid, mid, settings_text(u), kb_main(u))
    elif d == "back": edit(cid, mid, settings_text(u), kb_main(u))
    elif d.startswith("rw:"): send(cid, redeem(cid, d[3:])); edit(cid, mid, rewards_text(user(cid)), rewards_kb(user(cid)))
    elif d == "done": edit(cid, mid, "تم حفظ إعداداتك ✅\n\n" + status_text(cid).split("\n\n")[0], {"inline_keyboard": []})
    elif d.startswith("g:"):
        gi = int(d[2:]); edit(cid, mid, "📂 <b>%s</b>\nاضغط على الموضوع لتفعيله أو إلغائه:" % html.escape(GROUPS[gi]), kb_group(u, gi))
    elif d.startswith("t:"):
        _, tid, gi = d.split(":"); t = set(u.get("topics", []))
        (t.discard if tid in t else t.add)(tid); u["topics"] = sorted(t)
        edit(cid, mid, "📂 <b>%s</b>\nاضغط على الموضوع لتفعيله أو إلغائه:" % html.escape(GROUPS[int(gi)]), kb_group(u, int(gi)))
CMD = {"/topics": "topics", "/مواضيع": "topics", "مواضيع": "topics", "/settings": "topics", "/daily": "daily", "/ملخص": "daily", "ملخص": "daily",
       "/live": "live", "/مباشر": "live", "/status": "status", "/الحالة": "status", "/stop": "stop", "/ايقاف": "stop", "/إيقاف": "stop", "/help": "help", "/start": "start", "/stats": "stats", "/broadcast": "broadcast", "/invite": "invite", "/دعوة": "invite", "/points": "invite", "/نقاطي": "invite", "/rewards": "rewards", "/جوائز": "rewards", "/send": "send", "/requests": "requests", "/نشر": "broadcast", "/اذاعة": "broadcast", "/إحصائيات": "stats", "/احصائيات": "stats", "/myid": "myid"}
ADMIN_ONLY = {"/admin", "/pause", "/resume", "/top", "/user", "/addpoints", "/ban", "/unban", "/setconfig", "/setwelcome", "/resetwelcome", "/addreward", "/setcost", "/setstock", "/delreward", "/preview", "/cancel", "/msg", "/addpromo", "/delpromo", "/promooff", "/promoon", "/resetpromo"}
def is_admin(m):
    return str((m.get("chat") or {}).get("id")) in ADMIN or str((m.get("from") or {}).get("username", "")).lower() in ADMIN_NAMES
def push(chats, text=None, photo=None, copy_from=None, plain=False):
    """Send one message to many chats; returns (ok_count, removed_count). Chats that blocked the bot are dropped."""
    ok = gone = 0
    for c in chats:
        if copy_from: r = tg("copyMessage", chat_id=c, from_chat_id=copy_from[0], message_id=copy_from[1])
        elif photo: r = tg("sendPhoto", chat_id=c, photo=photo, caption=text or "", **({} if plain else {"parse_mode": "HTML"}))
        else: r = tg("sendMessage", chat_id=c, text=text, disable_web_page_preview="false", **({} if plain else {"parse_mode": "HTML"}))
        if not r.get("ok") and not plain and "parse" in str(r.get("description", "")).lower() and not copy_from:
            r = tg("sendMessage", chat_id=c, text=text, disable_web_page_preview="false") if not photo else tg("sendPhoto", chat_id=c, photo=photo, caption=text or "")
        if r.get("ok"): ok += 1
        elif r.get("error_code") in (400, 403) and str(c).lstrip("-").isdigit() and str(c) in subs["users"]: subs["users"].pop(str(c), None); gone += 1
        time.sleep(0.06)
    return ok, gone
BROADCAST_HELP = "لإرسال رسالة لكل المشتركين:\n• اكتب <code>/broadcast نص الرسالة</code> (يدعم الروابط)\n• أو أرسل صورة وفي وصفها <code>/broadcast النص</code>\n• أو اعمل «رد» على أي رسالة (نص، صورة، فيديو، ملف) واكتب <code>/broadcast</code> فتُنسخ كما هي"
# ---------------- persistent button menu (shown under the chat box, so users need not type commands) ----------------
BTN = {"⚙️ المواضيع": "topics", "🎁 ادعُ واربح": "invite", "🏆 الجوائز": "rewards", "📋 حالتي": "status", "☀️🌙 ملخص مرتين": "daily", "📰 كل 3 ساعات": "live", "⚡ فوري": "live", "☀️ ملخص يومي": "daily", "🕒 كل 6 ساعات": "live", "❓ مساعدة": "help", "⛔ إيقاف": "stop"}
MENU_KB = {"keyboard": [[{"text": "⚙️ المواضيع"}, {"text": "🎁 ادعُ واربح"}], [{"text": "🏆 الجوائز"}, {"text": "📋 حالتي"}], [{"text": "☀️🌙 ملخص مرتين"}, {"text": "📰 كل 3 ساعات"}], [{"text": "❓ مساعدة"}, {"text": "⛔ إيقاف"}]],
           "resize_keyboard": True, "is_persistent": True, "input_field_placeholder": "اختر من القائمة 👇"}
# ---------------- referrals: invite friends, earn points, redeem rewards ----------------
REF_HOLD = int(os.environ.get("REF_HOLD_HOURS", 24)) * 3600     # an invited friend counts after staying subscribed this long
REF_DAILY_CAP = int(os.environ.get("REF_DAILY_CAP", 15))        # max points one person can earn per day
BOT_USER = os.environ.get("BOT_USERNAME", "")
def rewards(): return subs["rw"] if "rw" in subs else load_json("rewards.json", [])
def ref_code(cid): return base64.b32encode(hmac.new(KEY, b"ref:" + str(cid).encode(), "sha256").digest())[:8].decode().lower()
def seen_id(cid): return hmac.new(KEY, b"seen:" + str(cid).encode(), "sha256").hexdigest()[:12]
def find_ref(code):
    for c in subs["users"]:
        if ref_code(c) == code: return c
def ref_link(cid): return "https://t.me/%s?start=ref_%s" % (BOT_USER, ref_code(cid)) if BOT_USER else ""
def pending_refs(cid): return sum(1 for u in subs["users"].values() if u.get("ref") == str(cid) and not u.get("rv"))
def invite_text(cid):
    u = user(cid); rs = rewards(); pts = u.get("pts", 0)
    nxt = min((r["cost"] for r in rs if r["cost"] > pts), default=None)
    return ("🎁 <b>ادعُ أصدقاءك واربح</b>\n\nشارك رابطك الخاص مع أصدقائك المهتمين بالذكاء الاصطناعي. تحصل على <b>نقطة</b> عن كل صديق ينضم عبر رابطك ويبقى مشتركا %d ساعة، وتستبدل نقاطك بجوائز.\n\n"
            "🔗 رابطك:\n%s\n\n⭐ نقاطك: <b>%d</b>\n⏳ قيد التأكيد: %d\n%s\n\n🎁 /rewards لعرض الجوائز واستبدال النقاط") % (
            REF_HOLD // 3600, ref_link(cid) or "(سيظهر الرابط بعد قليل)", pts, pending_refs(cid), ("🎯 تبقى %d نقطة للجائزة التالية" % (nxt - pts)) if nxt else "")
def rewards_kb(u):
    rows = []
    for r in rewards():
        left = None if r.get("stock") is None else r["stock"] - subs.get("used", {}).get(r["id"], 0)
        if left is not None and left <= 0: continue
        ok = u.get("pts", 0) >= r["cost"]
        rows.append([{"text": ("✅ " if ok else "🔒 ") + "%s — %d نقطة" % (r["name"], r["cost"]), "callback_data": "rw:" + r["id"]}])
    return {"inline_keyboard": rows}
def rewards_text(u):
    rs = [r for r in rewards() if r.get("stock") is None or r["stock"] - subs.get("used", {}).get(r["id"], 0) > 0]
    if not rs: return "لا توجد جوائز متاحة حاليا. تابعنا، ستضاف جوائز جديدة قريبا."
    return "🎁 <b>الجوائز المتاحة</b>\n\nنقاطك: <b>%d</b>\nاضغط على الجائزة لطلبها (يراجع المالك الطلب ثم يرسل لك التفاصيل هنا).\n\n%s" % (u.get("pts", 0), "\n".join("• %s — %d نقطة%s" % (r["name"], r["cost"], ("\n  " + r["desc"]) if r.get("desc") else "") for r in rs))
def admin_chat(): return subs.get("admin_cid")
def deliver_kb(cid): return {"inline_keyboard": [[{"text": "✉️ تسليم (أكتب الرابط)", "callback_data": "ad:dl:%s" % cid}, {"text": "❌ رفض وإرجاع النقاط", "callback_data": "ad:rj:%s" % cid}]]}
def finish_request(cid, st):
    for x in subs.get("red", []):
        if x.get("c") == str(cid) and x.get("st") == "pending": x["st"] = st; return x
def reject(cid):
    x = finish_request(cid, "rejected")
    if not x: return "لا يوجد طلب معلق لهذا المستخدم."
    if str(cid) in subs["users"]: subs["users"][str(cid)]["pts"] = subs["users"][str(cid)].get("pts", 0) + x.get("cost", 0)
    subs.setdefault("used", {})[x["id"]] = max(0, subs.get("used", {}).get(x["id"], 1) - 1)
    send(int(cid), "تعذر تنفيذ طلبك لجائزة «%s» حاليا، وأُعيدت نقاطك إلى رصيدك." % x["n"])
    return "تم الرفض وأُعيدت %d نقطة للمستخدم %s." % (x.get("cost", 0), cid)
def redeem(cid, rid):
    u = user(cid); r = next((x for x in rewards() if x["id"] == rid), None)
    if not r: return "هذه الجائزة غير متاحة."
    used = subs.setdefault("used", {})
    if r.get("stock") is not None and used.get(rid, 0) >= r["stock"]: return "نفدت هذه الجائزة."
    if u.get("pts", 0) < r["cost"]: return "نقاطك لا تكفي: تحتاج %d وعندك %d." % (r["cost"], u.get("pts", 0))
    u["pts"] -= r["cost"]; used[rid] = used.get(rid, 0) + 1
    subs.setdefault("red", []).append({"c": str(cid), "id": rid, "n": r["name"], "cost": r["cost"], "t": int(time.time()), "st": "pending"})
    ac = admin_chat()
    if ac: send(ac, "🔔 <b>طلب استبدال جديد</b>\nالجائزة: %s\nالمستخدم: <code>%s</code>\n\nاضغط «تسليم» ثم اكتب الرابط أو الرسالة وسأرسلها له." % (html.escape(r["name"]), cid), deliver_kb(cid))
    return "تم تسجيل طلبك لجائزة «%s» ✅\nخصمنا %d نقطة، وسيراجع المالك الطلب ويرسل لك التفاصيل هنا في المحادثة." % (r["name"], r["cost"])
def confirm_refs():
    now = time.time(); today = time.strftime("%Y-%m-%d", time.gmtime())
    for c, u in list(subs["users"].items()):
        rf = u.get("ref")
        if not rf or u.get("rv") or now - u.get("jt", now) < REF_HOLD or rf not in subs["users"]: continue
        ru = subs["users"][rf]; day = ru.setdefault("pd", {})
        if day.get(today, 0) >= REF_DAILY_CAP: continue
        u["rv"] = 1; day[today] = day.get(today, 0) + 1; ru["pts"] = ru.get("pts", 0) + 1
        for k in sorted(day)[:-7]: del day[k]
        send(int(rf), "🎉 انضم صديق عبر رابطك وبقي مشتركا، وأُضيفت لك <b>نقطة</b>! رصيدك: <b>%d</b>\n🎁 /rewards" % ru["pts"])
def requests_text():
    pend = [x for x in subs.get("red", []) if x.get("st") == "pending"]
    if not pend: return "لا توجد طلبات معلقة."
    return "🔔 <b>الطلبات المعلقة (%d)</b>\n\n" % len(pend) + "\n".join("• %s — <code>%s</code>" % (html.escape(x["n"]), x["c"]) for x in pend[:30]) + "\n\nاضغط «تسليم» تحت الطلب، ثم اكتب الرابط."
def requests_send(cid):
    pend = [x for x in subs.get("red", []) if x.get("st") == "pending"]
    send(cid, requests_text())
    for x in pend[:10]: send(cid, "• %s — <code>%s</code>" % (html.escape(x["n"]), x["c"]), deliver_kb(x["c"]))
# ---------------- owner panel: manage the bot from Telegram ----------------
def _cfgv(): return {"live_count": LIVE_COUNT, "batch_hours": BATCH_H, "promo_from": PROMO_FROM, "instant_min": INSTANT_MIN, "live_age": LIVE_AGE_H, "gate": GATE, "digest_hours": DIGEST_HOURS, "tz": TZ, "digest_count": DIGEST_COUNT, "sumchars": SUM_CHARS, "ref_hold": REF_HOLD // 3600, "ref_cap": REF_DAILY_CAP}
def _rewards_view():
    rows = "\n".join("• <code>%s</code> — %s — %d نقطة — متاح: %s" % (r["id"], html.escape(r["name"]), r["cost"], "بلا حد" if r.get("stock") is None else r["stock"] - subs.get("used", {}).get(r["id"], 0)) for r in rewards()) or "لا توجد جوائز بعد"
    return ("🎁 <b>إدارة الجوائز</b>\n\nالجوائز الحالية:\n" + rows + "\n\n<b>إضافة جائزة أو تعديلها كاملة:</b>\n<code>/addreward المعرف|الاسم|النقاط|العدد|الوصف</code>\n"
            "• المعرف: كلمة إنجليزية قصيرة بلا مسافات، مثل <code>gpro</code>\n• العدد: رقم، أو <code>-</code> إن كانت بلا حد\n"
            "مثال: <code>/addreward gpro|اشتراك Google AI Pro|25|3|رابط تفعيل لمدة 18 شهرا</code>\n(إن كان المعرف موجودا فستُستبدل الجائزة)\n\n"
            "<b>تعديل جزء واحد:</b>\n<code>/setcost gpro 30</code> يغيّر عدد النقاط المطلوبة\n<code>/setstock gpro 5</code> يغيّر العدد المتاح (<code>-</code> = بلا حد)\n<code>/delreward gpro</code> يحذف الجائزة\n\n"
            "💡 لا يتأثر المشتركون الذين استبدلوا بالفعل. التسليم من قسم «📬 الطلبات».")
ADMIN_SECTIONS = {
 "rq": ("📬 الطلبات", lambda: requests_text() + "\n\n<b>كيف تسلّم جائزة؟</b>\n1) أرسل /requests فتظهر لك الطلبات كل طلب برسالة مستقلة.\n2) اضغط «✉️ تسليم» تحت الطلب.\n3) اكتب رسالة واحدة فيها الرابط أو التفاصيل، فتصل للمستخدم فورا ويُعلَّم الطلب «منتهيا».\nأو اضغط «❌ رفض» فتُرجع نقاطه ويُبلَّغ.\n\nاختصارات: <code>/msg المعرف</code> لمراسلة أي مشترك، و<code>/cancel</code> لإلغاء رسالة بدأتها، و<code>/send المعرف النص</code> لإرسال بسطر واحد."),
 "st": ("📊 الإحصائيات", lambda: stats_text() + "\n\n<b>أوامر:</b>\n<code>/stats</code> هذه الأرقام\n<code>/top</code> أكثر المدعوين نقاطا\n<code>/user المعرف</code> بيانات مشترك (النمط، المواضيع، النقاط، من دعاه)"),
 "bc": ("📢 الإرسال للجميع", lambda: "📢 <b>الإرسال لكل المشتركين</b>\n\n• نص: <code>/broadcast نص الرسالة</code>\n• صورة: أرسل صورة وفي وصفها <code>/broadcast النص</code>\n• فيديو أو ملف أو صوت: اعمل «رد» على الرسالة واكتب <code>/broadcast</code> فتُنسخ كما هي\n\nيقبل النص الخط العريض <code>&lt;b&gt;نص&lt;/b&gt;</code> والروابط. يرد البوت بعدد من وصلتهم.\n\n<code>/preview</code> يرسل لك خبرا كما يراه المشترك."),
 "rw": ("🎁 الجوائز", _rewards_view),
 "us": ("👥 المستخدمون", lambda: "👥 <b>إدارة المستخدمين</b>\n\n<code>/user المعرف</code> بيانات مشترك، وتحتها زر «✉️ مراسلته»\n<code>/msg المعرف</code> ثم اكتب الرسالة: ترسل رسالة لمشترك واحد\n<code>/addpoints المعرف 5</code> يضيف 5 نقاط، و<code>/addpoints المعرف -5</code> يخصم\n<code>/ban المعرف</code> يحذف المشترك ويمنعه من الاشتراك مجددا\n<code>/unban المعرف</code> يرفع الحظر\n<code>/top</code> أكثر المدعوين\n\nكيف أعرف المعرف؟ يظهر في إشعارات الطلبات وفي /top. المحظورون الآن: %d" % len(subs.get("ban", []))),
 "cf": ("⚙️ الإعدادات", lambda: "⚙️ <b>الإعدادات الحالية</b>\n\n" + "\n".join("• <code>%s</code> = <b>%s</b>\n   %s" % (k, subs.get("cfg", {}).get(k, _cfgv()[k]), v[2]) for k, v in CFG_KEYS.items()) + "\n\n<b>التغيير:</b> <code>/setconfig المفتاح القيمة</code>\nمثال: <code>/setconfig batch_hours 4</code> (رسالة الأخبار كل 4 ساعات)\nمثال: <code>/setconfig digest_hours 8,20</code> (الملخصان 8 ص و8 م)\nللرجوع للأصل: <code>/setconfig المفتاح reset</code>\n\n💡 التغيير يسري على الدورة التالية."),
 "ms": ("📝 رسالة الترحيب", lambda: "📝 <b>رسالة الترحيب</b>\n\nتصل لكل مشترك جديد وعند /help.\n\n<code>/setwelcome النص</code> يغيّرها (تقبل HTML مثل &lt;b&gt;عريض&lt;/b&gt; والروابط)\n<code>/resetwelcome</code> يعيد الرسالة الأصلية\n\n⚠️ اكتب الرسالة كاملة في أمر واحد. تظهر تحتها قائمة الأزرار تلقائيا."),
 "pm": ("📣 الروابط الإعلانية", lambda: "📣 <b>الروابط الإعلانية</b> (%s)\n\nتُرفق مرة واحدة يوميا لكل مشترك بعد الأخبار، مفصولة عنها وبدون أي نص آخر:\n\n%s\n\n<code>/addpromo النص|الرابط</code> إضافة رابط\n<code>/delpromo رقم</code> حذف الرابط بهذا الرقم\n<code>/promooff</code> إيقاف الروابط\n<code>/promoon</code> تشغيلها\n<code>/resetpromo</code> الرجوع للروابط الأصلية\n\n⏰ تُرفق بالملخص المسائي، وبأول رسالة أخبار بعد الساعة %d محليا (تغيير: <code>/setconfig promo_from 18</code>)" % ("متوقفة ⏸" if subs.get("promo_off") else "تعمل ▶️", "\n".join("%d. %s\n    %s" % (i + 1, html.escape(t), html.escape(u)) for i, (t, u) in enumerate(subs.get("promo", DEFAULT_PROMO))) or "لا توجد روابط", PROMO_FROM)),
 "pa": ("⏸ إيقاف/استئناف", lambda: "⏯ <b>الإرسال التلقائي: %s</b>\n\n<code>/pause</code> يوقف الأخبار الفورية والملخصات والتنبيهات والفيديوهات لكل المشتركين مؤقتا\n<code>/resume</code> يعيدها\n\nلا يؤثر على الأوامر والجوائز والإحالات والإرسال اليدوي." % ("متوقف ⏸" if subs.get("paused") else "يعمل ▶️")),
 "gd": ("📖 الدليل الكامل", lambda: "📖 <b>دليل المالك</b>\n\n<b>يوميا:</b>\n• /stats لمعرفة العدد والانضمام\n• /requests لتسليم الجوائز\n\n<b>عند إعلان أو خبر خاص:</b> /broadcast\n\n<b>لتغيير شكل البوت:</b> /setwelcome ، /setconfig ، /addreward\n\n<b>عند مشكلة:</b> /pause لإيقاف الإرسال ثم /resume\n\n<b>المشتركون يرون:</b> القائمة الأزرار + /invite + /rewards\n\n<b>ملاحظات مهمة:</b>\n• الأوامر لا تعمل إلا من حسابك أنت\n• التغييرات تُحفظ مشفرة وتسري خلال دقائق\n• الأخبار الفورية تُفحص كل 15 دقيقة تقريبا\n• الملخصان بتوقيت %s الساعة %s\n• الجوائز تُسلَّم بموافقتك، لا تلقائيا" % (TZ, DIGEST_HOURS))}
def admin_kb():
    keys = list(ADMIN_SECTIONS); rows = [[{"text": ADMIN_SECTIONS[k][0], "callback_data": "ad:" + k} for k in keys[i:i + 2]] for i in range(0, len(keys), 2)]
    return {"inline_keyboard": rows}
ADMIN_HOME = "🛠 <b>لوحة المالك</b>\nاختر القسم الذي تريد إدارته:"
def admin_cb(cb):
    cid = cb["message"]["chat"]["id"]; mid = cb["message"]["message_id"]; d = cb.get("data", "")
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    if not is_admin({"chat": cb["message"]["chat"], "from": cb.get("from")}): return
    k = d[3:]
    if k.startswith(("dl:", "msg:")):
        target = k.split(":", 1)[1]; subs["await"] = {"cid": target}
        send(cid, "✍️ اكتب الآن الرسالة أو الرابط الذي تريد إرساله إلى <code>%s</code> (نص عادي، ويقبل الروابط). للإلغاء اكتب /cancel" % target); return
    if k.startswith("rj:"): send(cid, reject(k[3:])); return
    if k in ADMIN_SECTIONS: edit(cid, mid, ADMIN_SECTIONS[k][1](), {"inline_keyboard": [[{"text": "↩️ رجوع للوحة", "callback_data": "ad:home"}]]})
    else: edit(cid, mid, ADMIN_HOME, admin_kb())
def top_text():
    t = sorted(((u.get("pts", 0), c) for c, u in subs["users"].items() if u.get("pts", 0) > 0), reverse=True)[:10]
    return "🏆 <b>أكثر المدعوين</b>\n\n" + ("\n".join("%d. <code>%s</code> — %d نقطة" % (i + 1, c, p) for i, (p, c) in enumerate(t)) or "لا يوجد بعد")
def user_text(cid):
    u = subs["users"].get(str(cid))
    if not u: return "لا يوجد مشترك بهذا المعرف."
    inv = sum(1 for x in subs["users"].values() if x.get("ref") == str(cid))
    return "👤 <b>مشترك</b> <code>%s</code>\nالنمط: %s\nالمواضيع: %s\nانضم: %s\nالنقاط: %d (مدعوون: %d، قيد التأكيد: %d)\nجاء عبر إحالة: %s" % (cid, u.get("mode", "live"), ("، ".join(CATL.get(t, t) for t in u.get("topics", [])) or "الكل"), u.get("j", "قبل التتبع"), u.get("pts", 0), inv, pending_refs(cid), "نعم" if u.get("ref") else "لا")
def admin_command(cid, text, m):
    """Owner-only commands. Returns True when the text was an owner command."""
    parts = text.split(None, 2); c = parts[0].split("@")[0].lower(); a = parts[1:] if len(parts) > 1 else []
    if c == "/admin": send(cid, ADMIN_HOME, admin_kb()); return True
    if c == "/pause": subs["paused"] = True; send(cid, "⏸ أُوقف الإرسال التلقائي. /resume لإعادته."); return True
    if c == "/resume": subs.pop("paused", None); send(cid, "▶️ استؤنف الإرسال التلقائي."); return True
    if c == "/top": send(cid, top_text()); return True
    if c == "/user":
        if not a: send(cid, "الصيغة: /user المعرف")
        else: send(cid, user_text(a[0]), {"inline_keyboard": [[{"text": "✉️ مراسلته", "callback_data": "ad:msg:%s" % a[0]}]]} if a[0] in subs["users"] else None)
        return True
    if c == "/msg":
        if not a or not a[0].lstrip("-").isdigit(): send(cid, "الصيغة: <code>/msg المعرف</code> ثم اكتب الرسالة في الخطوة التالية"); return True
        subs["await"] = {"cid": a[0]}; send(cid, "✍️ اكتب الآن الرسالة أو الرابط لإرساله إلى <code>%s</code>. للإلغاء: /cancel" % a[0]); return True
    if c == "/addpoints":
        if len(a) < 2 or str(a[0]) not in subs["users"] or not a[1].lstrip("-").isdigit(): send(cid, "الصيغة: /addpoints المعرف عدد"); return True
        u = subs["users"][a[0]]; u["pts"] = max(0, u.get("pts", 0) + int(a[1])); send(cid, "تم. رصيده الآن %d." % u["pts"]); return True
    if c in ("/ban", "/unban"):
        if not a or not a[0].lstrip("-").isdigit(): send(cid, "الصيغة: %s المعرف" % c); return True
        b = subs.setdefault("ban", [])
        if c == "/ban":
            if a[0] not in b: b.append(a[0])
            subs["users"].pop(a[0], None); send(cid, "تم حظر %s وحذفه من القائمة." % a[0])
        else:
            if a[0] in b: b.remove(a[0])
            send(cid, "رُفع الحظر عن %s." % a[0])
        return True
    if c == "/setconfig":
        if len(a) < 2 or a[0] not in CFG_KEYS: send(cid, "المفاتيح: " + "، ".join("<code>%s</code>" % k for k in CFG_KEYS) + "\nالصيغة: <code>/setconfig المفتاح القيمة</code>"); return True
        cf = subs.setdefault("cfg", {})
        if a[1].lower() == "reset": cf.pop(a[0], None); send(cid, "تمت إعادة %s للافتراضي بعد إعادة تشغيل الدورة." % a[0]); return True
        try: CFG_KEYS[a[0]][1](a[1])
        except Exception: send(cid, "قيمة غير صالحة."); return True
        cf[a[0]] = a[1]; apply_cfg(); send(cid, "تم: %s = %s ✅" % (a[0], a[1])); return True
    if c == "/setwelcome":
        body = text.split(None, 1)[1].strip() if len(text.split(None, 1)) > 1 else ""
        if not body: send(cid, "الصيغة: /setwelcome النص"); return True
        subs["welcome"] = body; send(cid, "تم حفظ رسالة الترحيب ✅ جرّبها بـ /help"); return True
    if c == "/addpromo":
        f = [x.strip() for x in (text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else "").split("|")]
        if len(f) != 2 or not f[1].startswith("http"): send(cid, "الصيغة: <code>/addpromo النص|https://الرابط</code>"); return True
        subs.setdefault("promo", [list(x) for x in DEFAULT_PROMO]).append(f); send(cid, "أُضيف الرابط ✅ (%d روابط الآن)" % len(subs["promo"])); return True
    if c == "/delpromo":
        pl = subs.setdefault("promo", [list(x) for x in DEFAULT_PROMO])
        if not a or not a[0].isdigit() or not (1 <= int(a[0]) <= len(pl)): send(cid, "الصيغة: <code>/delpromo رقم</code> (الأرقام في قسم الروابط الإعلانية)"); return True
        pl.pop(int(a[0]) - 1); send(cid, "حُذف ✅ (%d روابط الآن)" % len(pl)); return True
    if c == "/promooff": subs["promo_off"] = True; send(cid, "أُوقفت الروابط الإعلانية."); return True
    if c == "/promoon": subs.pop("promo_off", None); send(cid, "عادت الروابط الإعلانية."); return True
    if c == "/resetpromo": subs.pop("promo", None); send(cid, "رجعت الروابط الأصلية ✅"); return True
    if c == "/resetwelcome": subs.pop("welcome", None); send(cid, "رجعت رسالة الترحيب للأصلية ✅"); return True
    if c in ("/addreward", "/setcost", "/setstock", "/delreward"):
        if "rw" not in subs: subs["rw"] = rewards()
        rw = subs["rw"]; arg = text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else ""
        if c == "/addreward":
            f = [x.strip() for x in arg.split("|")]
            if len(f) < 3 or not f[2].isdigit(): send(cid, "الصيغة: <code>/addreward المعرف|الاسم|النقاط|العدد|الوصف</code>"); return True
            rw[:] = [r for r in rw if r["id"] != f[0]] + [{"id": f[0], "name": f[1], "cost": int(f[2]), "stock": (int(f[3]) if len(f) > 3 and f[3].isdigit() else None), "desc": f[4] if len(f) > 4 else ""}]
            send(cid, "تمت إضافة/تحديث الجائزة ✅"); return True
        r = next((x for x in rw if a and x["id"] == a[0]), None)
        if not r: send(cid, "لا توجد جائزة بهذا المعرف. المعرفات في لوحة الجوائز: /admin"); return True
        if c == "/delreward": rw.remove(r); send(cid, "حُذفت الجائزة ✅"); return True
        if len(a) < 2 or not (a[1].isdigit() or (c == "/setstock" and a[1] == "-")): send(cid, "الصيغة: %s المعرف رقم" % c); return True
        if c == "/setcost": r["cost"] = int(a[1])
        else: r["stock"] = None if a[1] == "-" else int(a[1])
        send(cid, "تم ✅"); return True
    if c == "/preview":
        it = (ranked(news["items"], 72, None) or [None])[0]; t = story_text(it) if it else None
        send(cid, t or "تعذر إنشاء معاينة الآن (قد تكون الترجمة غير متاحة)."); return True
    return False
def handle_message(m):
    chat = m.get("chat") or {}
    if chat.get("type") != "private" or "id" not in chat: return []
    cid = chat["id"]; text = (m.get("text") or m.get("caption") or "").strip(); cmd = BTN.get(text) or CMD.get(text.split("@")[0].split()[0].lower() if text else "", None)
    new = []
    if cmd != "myid" and not is_admin(m) and not is_member(cid):
        pl = text.split()[1] if cmd == "start" and len(text.split()) > 1 else ""
        gate_block(cid, pl); return new
    if str(cid) in subs["users"] and subs["users"][str(cid)].get("nm"): subs["users"][str(cid)].pop("nm")
    if cmd == "myid": send(cid, "معرف محادثتك: <code>%s</code>\nضعه في سر GitHub باسم TELEGRAM_ADMIN_ID لتفعيل أمر /stats لك." % cid); return new
    if cmd == "broadcast":
        if not is_admin(m): send(cid, "هذا الأمر لمالك البوت فقط."); return new
        body = text.split(None, 1)[1].strip() if len(text.split(None, 1)) > 1 else ""
        rp = m.get("reply_to_message"); chats = targets_all()
        if rp: ok, gone = push(chats, copy_from=(rp["chat"]["id"], rp["message_id"]))
        elif m.get("photo") and (body or True): ok, gone = push(chats, text=body, photo=m["photo"][-1]["file_id"])
        elif body: ok, gone = push(chats, text=body)
        else: send(cid, BROADCAST_HELP); return new
        send(cid, "تم الإرسال إلى %d من %d ✅%s" % (ok, len(chats), (" (حُذف %d لأنهم حظروا البوت)" % gone) if gone else "")); return new
    if cmd == "stats":
        send(cid, stats_text() if (str(cid) in ADMIN or str((m.get("from") or {}).get("username", "")).lower() in ADMIN_NAMES) else "هذا الأمر لمالك البوت فقط."); return new
    if cmd == "stop":
        if str(cid) in subs["users"]: subs["users"].pop(str(cid)); hist("stop"); send(cid, "تم إيقاف الأخبار ✅ لإعادة تشغيلها أرسل /start", {"remove_keyboard": True})
        return new
    if is_admin(m):
        subs["admin_cid"] = cid
        aw = subs.get("await")
        if aw and text and text != "/cancel" and not text.startswith("/") and text not in BTN:
            r = send(int(aw["cid"]), text); subs.pop("await", None)
            if r == "ok": finish_request(aw["cid"], "done")
            send(cid, "تم إرسال رسالتك إلى %s ✅" % aw["cid"] if r == "ok" else "تعذر الإرسال (قد يكون المستخدم حظر البوت)."); return new
        if text.split()[:1] == ["/cancel"]: subs.pop("await", None); send(cid, "أُلغي الإرسال."); return new
        if text.startswith("/") and admin_command(cid, text, m): return new
    elif text.startswith("/") and text.split()[0].split("@")[0].lower() in ADMIN_ONLY: send(cid, "هذا الأمر لمالك البوت فقط."); return new
    if str(cid) in subs.get("ban", []): return new
    if cmd == "send":
        if not is_admin(m): send(cid, "هذا الأمر لمالك البوت فقط."); return new
        parts = text.split(None, 2)
        if len(parts) < 3 or not parts[1].lstrip("-").isdigit(): send(cid, "الصيغة: <code>/send المعرف النص أو الرابط</code>"); return new
        r = send(int(parts[1]), parts[2])
        if r == "ok":
            for x in subs.get("red", []):
                if x.get("c") == parts[1] and x.get("st") == "pending": x["st"] = "done"; break
        send(cid, "تم الإرسال ✅" if r == "ok" else "تعذر الإرسال (قد يكون المستخدم حظر البوت)."); return new
    if cmd == "requests":
        (requests_send(cid) if is_admin(m) else send(cid, "هذا الأمر لمالك البوت فقط.")); return new
    if str(cid) not in subs["users"]:
        first = seen_id(cid) not in subs.setdefault("seen", [])
        u0 = user(cid); new.append(cid)
        if first:
            subs["seen"].append(seen_id(cid)); subs["seen"] = subs["seen"][-20000:]
            parts = text.split()
            if cmd == "start" and len(parts) > 1 and parts[1].startswith("ref_"):
                rf = find_ref(parts[1][4:])
                if rf and rf != str(cid):
                    u0["ref"] = rf
                    send(int(rf), "👋 انضم شخص جديد عبر رابطك. ستُحتسب لك النقطة إذا بقي مشتركا %d ساعة." % (REF_HOLD // 3600))
    if cmd == "invite": send(cid, invite_text(cid))
    elif cmd == "rewards": send(cid, rewards_text(user(cid)), rewards_kb(user(cid)))
    elif cmd == "topics": send(cid, settings_text(user(cid)), kb_main(user(cid)))
    elif cmd == "daily": user(cid)["mode"] = "daily"; send(cid, "تم ✅ سيصلك ملخص بأهم %d أخبار الساعة 9 صباحا وملخص آخر الساعة 9 مساء (بتوقيت %s)." % (DIGEST_COUNT, "القاهرة" if TZ == "Africa/Cairo" else TZ))
    elif cmd == "live": user(cid)["mode"] = "live"; send(cid, "تم ✅ ستصلك الأخبار الجديدة مجمّعة في رسالة واحدة كل %g ساعات تقريبا." % BATCH_H)
    elif cmd == "status": send(cid, status_text(cid))
    elif cmd == "help": send(cid, subs.get("welcome") or WELCOME, MENU_KB)
    elif cmd == "start" and cid not in new: send(cid, "أهلا بعودتك 👋 القائمة جاهزة أسفل الشاشة. اختر ما تريد 👇", MENU_KB)
    return new

# ---------------- YouTube: new long videos ----------------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
def is_short(vid):
    try:
        r = urllib.request.build_opener(_NoRedirect).open(urllib.request.Request("%s/shorts/%s" % (YT, vid), headers={"User-Agent": "Mozilla/5.0"}), timeout=15)
        return r.status == 200
    except Exception: return False
def watch_videos(targets):
    cfg = load_json("own.json", {})
    try: vs = json.load(open(videos_path)); first = False
    except Exception: vs = {"sent": [], "ids": {}}; first = True
    chans = list(cfg.get("youtube_channels", []))
    for h in cfg.get("youtube_handles", []):
        cid = vs["ids"].get(h)
        if not cid:
            try:
                page = _get("%s/%s" % (YT, h.lstrip("/")), 20).decode("utf8", "replace")
                mm = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', page) or re.search(r'channel_id=(UC[\w-]{22})', page)
                cid = mm.group(1) if mm else None
            except Exception as e: print("channel lookup failed:", h, str(e)[:80], file=sys.stderr)
            if cid: vs["ids"][h] = cid
        if cid: chans.append(cid)
    sent_v = set(vs["sent"]); n = 0
    ns = {"a": "http://www.w3.org/2005/Atom", "y": "http://www.youtube.com/xml/schemas/2015"}
    for cid in dict.fromkeys(chans):
        try: root = ET.fromstring(_get("%s/feeds/videos.xml?channel_id=%s" % (YT, cid), 20))
        except Exception as e: print("feed failed:", cid, str(e)[:80], file=sys.stderr); continue
        author = (root.findtext("a:author/a:name", namespaces=ns) or "").strip(); ents = []
        for e in root.findall("a:entry", ns):
            vid = e.findtext("y:videoId", namespaces=ns); title = (e.findtext("a:title", namespaces=ns) or "").strip()
            if vid and title: ents.append((e.findtext("a:published", namespaces=ns) or "", vid, title))
        for pub, vid, title in sorted(ents):
            if vid in sent_v: continue
            sent_v.add(vid)
            if first or is_short(vid): continue
            text = "🎬 <b>فيديو جديد على قناة %s</b>\n\n%s\n\n▶️ <a href=\"https://www.youtube.com/watch?v=%s\">شاهد الفيديو الآن</a>" % (html.escape(author or "يوتيوب"), html.escape(title), vid)
            for chat in targets: send(chat, text); time.sleep(0.07)
            n += 1; print("video announced:", title[:50])
    vs["sent"] = sorted(sent_v)[-600:]
    json.dump(vs, open(videos_path, "w"), separators=(",", ":")); return n

def promo_html():
    """Three embedded links, separated from the news, no other text. Edited from Telegram with /promo."""
    if subs.get("promo_off"): return ""
    items = subs.get("promo", DEFAULT_PROMO)
    return ("\n\n┄┄┄┄┄┄┄┄┄┄┄┄\n" + "\n".join('🔗 <a href="%s">%s</a>' % (html.escape(u, quote=True), html.escape(t)) for t, u in items)) if items else ""
def kick_news():
    """GitHub's own cron is unreliable, so the always-running bot job starts the news job (fetch + instant stories + digests)."""
    tok = os.environ.get("GH_TOKEN"); repo = os.environ.get("GITHUB_REPOSITORY")
    if not (tok and repo): return
    req = urllib.request.Request("https://api.github.com/repos/%s/actions/workflows/update-ai-news.yml/dispatches" % repo, data=json.dumps({"ref": os.environ.get("GITHUB_REF_NAME", "main")}).encode(),
                                 headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"}, method="POST")
    try: urllib.request.urlopen(req, timeout=20); print("news job started")
    except Exception as e: print("could not start news job:", str(e).replace(tok, "***")[:80], file=sys.stderr)
def targets_all():
    return [int(c) for c, u in subs["users"].items() if not u.get("nm")] + ([EXTRA] if EXTRA else [])

# ================= mode 1: interactive subscribers job =================
if "--subs" in sys.argv:
    dur = int(sys.argv[sys.argv.index("--duration") + 1]) if "--duration" in sys.argv else 0
    deadline = time.time() + dur; last_vid = 0
    state = load_json("telegram-state.json", {})
    for g in state.get("gone", []): subs["users"].pop(str(g), None)
    tg("deleteWebhook")
    apply_cfg()
    if dur: kick_news()
    if admin_chat():
        tg("setMyCommands", scope={"type": "chat", "chat_id": admin_chat()}, commands=[{"command": "admin", "description": "لوحة المالك"}, {"command": "stats", "description": "إحصائيات البوت"}, {"command": "broadcast", "description": "إرسال للجميع"},
            {"command": "requests", "description": "طلبات الجوائز"}, {"command": "preview", "description": "معاينة خبر"}, {"command": "pause", "description": "إيقاف الإرسال"}, {"command": "resume", "description": "استئناف الإرسال"}, {"command": "top", "description": "أكثر المدعوين"},
            {"command": "start", "description": "القائمة"}, {"command": "invite", "description": "الدعوة والنقاط"}, {"command": "rewards", "description": "الجوائز"}, {"command": "help", "description": "المساعدة"}])
    if not BOT_USER: BOT_USER = (tg("getMe").get("result") or {}).get("username", "")
    tg("setMyCommands", commands=[{"command": "start", "description": "الاشتراك في أخبار الذكاء الاصطناعي"}, {"command": "topics", "description": "اختيار المواضيع ونمط الإرسال"},
        {"command": "daily", "description": "ملخص مرتين يوميا 9 ص و9 م"}, {"command": "live", "description": "الأخبار الجديدة كل 3 ساعات"}, {"command": "status", "description": "حالتي"}, {"command": "invite", "description": "ادعُ أصدقاءك واربح نقاطا"}, {"command": "rewards", "description": "الجوائز واستبدال النقاط"}, {"command": "help", "description": "المساعدة وقائمة الأزرار"}, {"command": "stop", "description": "إيقاف الأخبار"}])
    welcomed = 0
    while True:
        r = tg("getUpdates", offset=subs["offset"], timeout=(POLL_T if dur else 0), allowed_updates=["message", "callback_query"])
        if not r.get("ok"): print("getUpdates failed:", str(r.get("description"))[:100], file=sys.stderr)
        for u in (r.get("result") or []) if r.get("ok") else []:
            subs["offset"] = max(subs["offset"], u["update_id"] + 1)
            try:
                if "callback_query" in u: handle_callback(u["callback_query"])
                elif "message" in u:
                    for cid in handle_message(u["message"]): welcome_new(cid); welcomed += 1
            except Exception as e: print("update failed:", str(e).replace(TOKEN, "***")[:120], file=sys.stderr)
        if time.time() - last_vid > 300:
            if not subs.get("paused"): watch_videos(targets_all())
            confirm_refs(); last_vid = time.time()
        if gate_on() and time.time() - subs.get("gate_t", 0) > 10800: subs["gate_t"] = int(time.time()); recheck_members()
        if time.time() >= deadline: break
        if not dur: break
    save_subs()
    print("subscribers:", len(subs["users"]), "| welcomed this run:", welcomed); sys.exit(0)

# ================= mode 2: hourly broadcast job =================
apply_cfg()
try: state = json.load(open(state_path)); first_run = False
except Exception: state = {"sent": []}; first_run = True
sent = set(state["sent"]); trcache.update(state.get("tr", {})); gone = set(state.get("gone", []))
now = time.time(); stats = {"alerts": 0, "live": 0, "digest": 0}
users = {c: u for c, u in subs["users"].items() if int(c) not in gone and not u.get("nm")}
if subs.get("paused"): print("paused by owner; nothing sent"); sys.exit(0)
if not users and not EXTRA:
    print("no subscribers yet and no TELEGRAM_CHAT_ID; nothing to send"); sys.exit(0)
def deliver(chat, text, markup=None):
    res = send(chat, text, markup); time.sleep(0.07)
    if res == "gone": gone.add(int(chat)) if str(chat).lstrip("-").isdigit() else None
    return res == "ok"

# (1) model alerts: rumour -> release
alerted = set(state.get("alerted", []))
for m in tracker.get("models", []):
    if not (m.get("rel") and m.get("first") and not m.get("early") and m["rel"] >= m["first"]): continue
    if m["k"] in alerted: continue
    alerted.add(m["k"])
    if first_run or "alerted" not in state: continue          # first run: only remember
    gap = (datetime.date.fromisoformat(m["rel"]) - datetime.date.fromisoformat(m["first"])).days
    ri = m.get("relItem") or {}
    text = "🚨 <b>صدر %s</b>\n\nكان نموذجا مرتقبا: أول تسريب في %s، وصدر في %s (%s بعد التسريب).%s" % (
        html.escape(m["n"]), ar_date(m["first"]), ar_date(m["rel"]), ar_days(gap) if gap else "في اليوم نفسه",
        ("\n\n👉 <a href=\"%s%sutm_source=telegram&amp;utm_medium=bot&amp;utm_campaign=alert#/n/%s/ar\">اقرأ خبر الإصدار</a>" % (NEWS_PAGE, "&amp;" if "?" in NEWS_PAGE else "?", nid(ri["u"]))) if ri.get("u") else "")
    for c in list(users) + ([EXTRA] if EXTRA else []):
        if deliver(c, text): stats["alerts"] += 1
state["alerted"] = sorted(alerted)

# local time for the daily cap and the digests
try:
    import zoneinfo; local = datetime.datetime.now(zoneinfo.ZoneInfo(TZ))
except Exception:
    local = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
ldate = local.strftime("%Y-%m-%d")
dn = state.setdefault("dn", {})
# (2) batch: all new important stories since the last batch, in ONE message every ~3 hours (topics respected)
prd = state.setdefault("promo", {})   # user -> local date the daily promo links were last attached
def with_promo(c, text, evening):
    """Attach the promo links once per day, to the evening digest or the first batch after PROMO_FROM."""
    if evening and prd.get(str(c)) != ldate and promo_html(): prd[str(c)] = ldate; return text + promo_html()
    return text
last_batch = state.get("last_batch", 0)
if not first_run and now - last_batch >= BATCH_H * 3600 * 0.9:
    fresh = ranked([i for i in news["items"] if i["u"] not in sent and AUTH.get(i["s"], 0) >= INSTANT_MIN], LIVE_AGE_H)
    used = set()
    def batch_msgs(items):
        blocks = [x for x in (item_block(n_, it) for n_, it in enumerate(items, 1)) if x]
        return pack("📰 <b>آخر أخبار الذكاء الاصطناعي</b>", blocks)
    def send_all(c, msgs, evening):
        for i, m_ in enumerate(msgs):
            last = i == len(msgs) - 1
            ok = deliver(c, with_promo(c, m_, evening) if last else m_)
            if not ok: return False
        return True
    for c, u in users.items():
        if u.get("mode", "live") != "live": continue
        mine = ranked(fresh, LIVE_AGE_H, u.get("topics"))[:LIVE_COUNT]
        msgs = batch_msgs(mine)
        if not msgs: continue
        if send_all(c, msgs, local.hour >= PROMO_FROM): used.update(it["u"] for it in mine); stats["live"] += 1
    if EXTRA:
        msgs = batch_msgs(fresh[:LIVE_COUNT])
        if msgs and send_all(EXTRA, msgs, False): used.update(it["u"] for it in fresh[:LIVE_COUNT])
    sent.update(used); state["last_batch"] = now
elif "last_batch" not in state: state["last_batch"] = now
for k in [k for k, v in dn.items() if v["d"] != ldate and k not in users]: del dn[k]
for k in [k for k, v in prd.items() if v != ldate]: del prd[k]

# (3) digest for "daily" users at the configured local hours (default 9 am and 9 pm), catching up to 2 hours late
done = state.setdefault("digests", [])
try: hours = sorted({int(x) for x in str(DIGEST_HOURS).replace(" ", "").split(",") if x != ""})
except Exception: hours = [9, 21]
for h in hours:
    key = "%s@%02d" % (ldate, h)
    if first_run or key in done or not (h <= local.hour < h + 3): continue
    done.append(key)
    for c, u in {c: u for c, u in users.items() if u.get("mode") == "daily"}.items():
        top = ranked(news["items"], 14, u.get("topics"))[:DIGEST_COUNT]
        blocks = [x for x in (item_block(n_, it) for n_, it in enumerate(top, 1)) if x]
        msgs = pack("%s <b>ملخص أخبار الذكاء الاصطناعي</b> — %s" % ("☀️ صباح الخير" if h < 15 else "🌙 مساء الخير", ar_date(ldate)), blocks)
        if msgs:
            ok = True
            for i, m_ in enumerate(msgs):
                ok = deliver(c, with_promo(c, m_, h >= 15) if i == len(msgs) - 1 else m_)
                if not ok: break
            if ok: stats["digest"] += 1
state["digests"] = done[-12:]

if first_run: sent.update(i["u"] for i in news["items"])
state["sent"] = sorted(sent)[-1500:]; state["gone"] = sorted(gone)[-200:]
state["tr"] = dict(list(trcache.items())[-300:])
state["last"] = {"at": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "translate": TR_STATS, "sent": stats, "users": len(users)}
json.dump(state, open(state_path, "w"), ensure_ascii=False, separators=(",", ":"))
print("done:", stats, "| users:", len(users))
