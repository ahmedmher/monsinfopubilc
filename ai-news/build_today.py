#!/usr/bin/env python3
"""Builds today.json (for the homepage widget) and static SEO pages in docs/ (GitHub Pages):
docs/index.html (today in AI), docs/models/<id>.html (price, history, related news), sitemap.xml, robots.txt."""
import datetime, html, json, os, re, time, urllib.parse, urllib.request
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda p, d=None: (lambda f: json.load(f))(open(os.path.join(root, p), encoding="utf8")) if os.path.exists(os.path.join(root, p)) else d
BLOG = "https://www.monsinfo.com"; NEWS = BLOG + "/p/ai-news.html"; PRICES = BLOG + "/p/api-prices.html"
BASE = os.environ.get("PAGES_BASE", "https://ahmedmher.github.io/monsinfopubilc")
news = J("ai-news/news.json"); items = news["items"]; names = {s["id"]: s["name"] for s in news["sources"]}; langs = {s["id"]: s.get("lang", "en") for s in news["sources"]}
trk = J("ai-news/model-tracker.json", {"models": []})["models"]; prices = J("api-cost-calculator/prices.json")["models"]; hist = J("api-cost-calculator/price-history.json", {})
state = J("ai-news/telegram-state.json", {}); cache_path = os.path.join(root, "ai-news/ar-cache.json"); cache = J("ai-news/ar-cache.json", {})
AUTH = {"openai": 3, "anthropic": 3, "claude": 2.5, "anthropic-r": 2.5, "deepmind": 3, "googleai": 3, "hf": 2.5, "msai": 2.5, "nvidia": 2.5, "mit": 2, "ars": 2, "verge": 2, "techcrunch": 2, "venturebeat": 1.5, "aitnews": 2, "scmp": 1.5, "technode": 1, "pandaily": 1.5}
def nid(u):
    h = 5381; b = u.encode("utf-16-le")
    for i in range(0, len(b), 2): h = ((h << 5) + h + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    s = ""
    while True:
        h, r = divmod(h, 36); s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
        if h == 0: return s
def link(it): return "%s#/n/%s%s" % (NEWS, nid(it["u"]), "" if langs.get(it["s"]) == "ar" else "/ar")
def age_h(it): return (time.time() - datetime.datetime.strptime(it["p"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc).timestamp()) / 3600
def ar_title(it):
    if langs.get(it["s"]) == "ar": return it["t"]
    u = it["u"]
    if u in cache: return cache[u]
    r = (state.get("tr") or {}).get(u)
    if r and r.get("t"): cache[u] = r["t"]; return r["t"]
    try:
        q = urllib.parse.quote(it["t"][:300])
        j = json.loads(urllib.request.urlopen(urllib.request.Request("https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=en&tl=ar&q=" + q, headers={"User-Agent": "Mozilla/5.0"}), timeout=12).read())
        t = j[0] if isinstance(j[0], str) else j[0][0]
        if t and t != it["t"]: cache[u] = t; return t
    except Exception: pass
    return None
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
def ar_date(iso): d = datetime.date.fromisoformat(iso[:10]); return "%d %s %d" % (d.day, MONTHS[d.month - 1], d.year)
today_iso = time.strftime("%Y-%m-%d", time.gmtime())

# ---- top 3 stories (last 24h, authority + category breadth + freshness) ----
def score(i): return AUTH.get(i["s"], 0) + 0.4 * len([x for x in i.get("c", []) if x != "other"]) + max(0, 1 - age_h(i) / 24)
top = sorted([i for i in items if i["s"] in AUTH and age_h(i) <= 30], key=lambda i: -score(i))[:6]
stories = []
for it in top:
    t = ar_title(it) or it["t"]
    if t: stories.append({"t": t, "u": link(it), "s": names.get(it["s"], it["s"]), "p": it["p"], "en": it["t"], "su": it["u"]})
    if len(stories) == 3: break

# ---- biggest price change between the two latest snapshots that differ ----
pn = {m["id"]: m for m in prices}; change = None; days = sorted(hist)
for a, b in zip(reversed(days[:-1]), reversed(days[1:])):
    best = None
    for k, v in hist[b].items():
        o = hist[a].get(k)
        if not o or k not in pn: continue
        for idx, lab in ((0, "الإدخال"), (1, "الإخراج")):
            if o[idx] and v[idx] != o[idx]:
                pc = (v[idx] - o[idx]) / o[idx] * 100
                if not best or abs(pc) > abs(best["pct"]): best = {"id": k, "n": pn[k]["n"], "kind": lab, "old": o[idx], "new": v[idx], "pct": round(pc, 1), "date": b}
    if best: change = best; break
cheap = sorted(prices, key=lambda m: m["i"] + m["o"])[0] if prices else None

# ---- most talked-about model family (mentions in last 72h) ----
FAM = {"Claude": r"claude|anthropic|opus|sonnet|haiku|fable", "GPT / ChatGPT": r"gpt|chatgpt|openai|codex", "Gemini": r"gemini|gemma", "DeepSeek": r"deepseek", "Kimi": r"kimi|moonshot", "Qwen": r"qwen|alibaba", "Grok": r"grok|xai", "Llama": r"llama", "Mistral": r"mistral", "Seedance": r"seedance", "Sora": r"\bsora\b", "Midjourney": r"midjourney"}
cnt = {}
for it in items:
    if age_h(it) > 72: continue
    tx = (it["t"] + " " + (it.get("d") or "")).lower()
    for f, rx in FAM.items():
        if re.search(rx, tx): cnt.setdefault(f, []).append(it)
hot = None
if cnt:
    f = max(cnt, key=lambda k: len(cnt[k])); lst = sorted(cnt[f], key=lambda i: i["p"], reverse=True)
    hot = {"n": f, "c": len(lst), "u": link(lst[0]), "t": ar_title(lst[0]) or lst[0]["t"]}

# ---- latest rumour (not yet released) ----
ru = sorted([m for m in trk if not m.get("rel") and m.get("first")], key=lambda m: m["last"] or "", reverse=True)
rumor = None
if ru:
    m = ru[0]; up = m["ups"][-1] if m["ups"] else {}
    rumor = {"n": m["n"], "first": m["first"], "u": up.get("u", ""), "t": up.get("t", ""), "s": names.get(up.get("s"), up.get("s", ""))}
rel = sorted([m for m in trk if m.get("rel")], key=lambda m: m["rel"], reverse=True)
released = {"n": rel[0]["n"], "rel": rel[0]["rel"], "first": rel[0].get("first")} if rel else None

today = {"updated": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "stories": stories, "price": change, "cheap": {"n": cheap["n"], "i": cheap["i"], "o": cheap["o"]} if cheap else None, "hot": hot, "rumor": rumor, "released": released}
json.dump(today, open(os.path.join(root, "ai-news/today.json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
json.dump(dict(list(cache.items())[-500:]), open(cache_path, "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))

# ---------------- static pages (docs/) ----------------
E = html.escape
CSS = "body{margin:0;background:#f6f4fc;color:#1b1740;font-family:'IBM Plex Sans Arabic',Tahoma,Arial,sans-serif;line-height:1.9}main{max-width:820px;margin:0 auto;padding:24px 16px}h1{font-size:28px;line-height:1.5}h2{font-size:21px;margin-top:30px}.c{background:#fff;border:1px solid #e6e1f5;border-radius:16px;padding:16px 20px;margin:12px 0}a{color:#6d28d9}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #e6e1f5;padding:6px 8px;text-align:right}.m{color:#65618a;font-size:14px}nav a{margin-left:14px}footer{color:#65618a;font-size:13px;margin-top:34px}"
def page(path, title, desc, body, schema=None):
    url = BASE + "/" + path.replace("index.html", "")
    ld = '<script type="application/ld+json">%s</script>' % json.dumps(schema, ensure_ascii=False) if schema else ""
    out = '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title><meta name="description" content="%s"><link rel="canonical" href="%s"><meta property="og:title" content="%s"><meta property="og:description" content="%s"><meta property="og:locale" content="ar_AR">%s<style>%s</style></head><body><main><nav><a href="%s/">الرئيسية</a><a href="%s">أخبار الذكاء الاصطناعي</a><a href="%s">أسعار النماذج</a></nav>%s<footer>مونستر للمعلوميات — <a href="%s">monsinfo.com</a>. البيانات تتحدث تلقائيا من مصادر عامة، وقد تحتوي الترجمة الآلية على أخطاء.</footer></main></body></html>' % (E(title), E(desc, True), url, E(title), E(desc, True), ld, CSS, BASE, NEWS, PRICES, body, BLOG)
    p = os.path.join(root, "docs", path); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf8").write(out)
    return url
urls = []
b = "<h1>أخبار الذكاء الاصطناعي اليوم — %s</h1>" % ar_date(today_iso)
b += "<h2>أهم الأخبار</h2>" + "".join('<div class="c"><a href="%s"><b>%s</b></a><div class="m">%s · %s</div></div>' % (E(s["u"]), E(s["t"]), E(s["s"]), ar_date(s["p"])) for s in stories)
if change: b += '<h2>أكبر تغيير في الأسعار</h2><div class="c"><a href="models/%s.html"><b>%s</b></a>: سعر %s (لكل مليون رمز) %s من $%s إلى $%s (%+.1f%%) بتاريخ %s.</div>' % (change["id"], E(change["n"]), change["kind"], "ارتفع" if change["pct"] > 0 else "انخفض", change["old"], change["new"], change["pct"], ar_date(change["date"]))
if hot: b += '<h2>الأكثر تداولا</h2><div class="c"><b>%s</b> — ذُكر في %d خبرا خلال 3 أيام. آخرها: <a href="%s">%s</a></div>' % (E(hot["n"]), hot["c"], E(hot["u"]), E(hot["t"]))
if rumor: b += '<h2>آخر تسريب</h2><div class="c"><b>%s</b> — أول ظهور %s. <a href="%s">%s</a> (%s)</div>' % (E(rumor["n"]), ar_date(rumor["first"]), E(rumor["u"]), E(rumor["t"]), E(rumor["s"]))
b += '<h2>نماذج وأسعارها</h2><div class="c">' + " · ".join('<a href="models/%s.html">%s</a>' % (m["id"], E(m["n"])) for m in prices) + "</div>"
urls.append(page("index.html", "أخبار الذكاء الاصطناعي اليوم وأسعار النماذج | مونستر للمعلوميات", "ملخص يومي بالعربية: أهم أخبار الذكاء الاصطناعي، أكبر تغيير في أسعار النماذج، الأكثر تداولا وآخر التسريبات.", b,
    {"@context": "https://schema.org", "@type": "CollectionPage", "name": "أخبار الذكاء الاصطناعي اليوم", "inLanguage": "ar", "dateModified": today["updated"]}))
FAMOF = lambda n: next((f for f, rx in FAM.items() if re.search(rx, n.lower())), None)
for m in prices:
    hr = [(d, hist[d][m["id"]]) for d in sorted(hist) if m["id"] in hist[d]]
    rows = "".join("<tr><td>%s</td><td>$%s</td><td>$%s</td></tr>" % (d, v[0], v[1]) for d, v in hr[-30:][::-1])
    fam = FAMOF(m["n"]); rn = sorted([i for i in cnt.get(fam, [])], key=lambda i: i["p"], reverse=True)[:5] if fam else []
    nb = "".join('<div class="c"><a href="%s">%s</a><div class="m">%s</div></div>' % (E(link(i)), E(ar_title(i) or i["t"]), E(names.get(i["s"], i["s"]))) for i in rn)
    cw = "%s رمز" % format(m["x"], ",") if m.get("x") else "—"
    body = "<h1>سعر %s وتفاصيله</h1><div class=\"c\"><b>الشركة:</b> %s<br><b>سعر الإدخال:</b> $%s لكل مليون رمز<br><b>سعر الإخراج:</b> $%s لكل مليون رمز<br><b>التخزين المؤقت:</b> $%s<br><b>نافذة السياق:</b> %s</div>" % (E(m["n"]), E(m["p"]), m["i"], m["o"], m.get("c", "—"), cw)
    body += '<p><a href="%s">احسب تكلفة استخدامك بالحاسبة التفاعلية</a></p>' % PRICES
    body += "<h2>تاريخ السعر</h2><table><tr><th>التاريخ</th><th>الإدخال</th><th>الإخراج</th></tr>%s</table>" % rows
    if nb: body += "<h2>آخر أخبار %s</h2>%s" % (E(fam), nb)
    urls.append(page("models/%s.html" % m["id"], "سعر %s ومواصفاته بالعربية | مونستر للمعلوميات" % m["n"], "سعر %s من %s: الإدخال $%s والإخراج $%s لكل مليون رمز، مع تاريخ التغير وآخر الأخبار." % (m["n"], m["p"], m["i"], m["o"]), body,
        {"@context": "https://schema.org", "@type": "Product", "name": m["n"], "brand": {"@type": "Brand", "name": m["p"]}, "offers": {"@type": "Offer", "price": m["i"], "priceCurrency": "USD"}}))
open(os.path.join(root, "docs/sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % "".join("<url><loc>%s</loc><lastmod>%s</lastmod></url>" % (u, today_iso) for u in urls))
open(os.path.join(root, "docs/robots.txt"), "w").write("User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % BASE)
print("today.json ok | stories", len(stories), "| pages", len(urls))
