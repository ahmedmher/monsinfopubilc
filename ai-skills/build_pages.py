#!/usr/bin/env python3
"""يولّد صفحة HTML ثابتة لكل skill (للسيو) + sitemap.xml من skills.json."""
import json, html, pathlib
D = pathlib.Path(__file__).parent
data = json.load(open(D / 'skills.json', encoding='utf-8'))
cfg = json.load(open(D / 'config.json', encoding='utf-8'))
cats = {c['id']: c['label'] for c in data['categories']}
OUT = D / 'p'
OUT.mkdir(exist_ok=True)
for f in OUT.glob('*.html'):
    f.unlink()
e = lambda t: html.escape(str(t or ''), quote=True)
SEC = {'safe': ('نصوص فقط، ولا سكربتات تنفَّذ على جهازك.', '#047857'),
       'review': ('تتضمن سكربتات أو أوامر. راجعها قبل التشغيل.', '#9a3412'),
       'warn': ('اكتُشفت أنماط حساسة. افحص الملفات بنفسك قبل أي استخدام.', '#b91c1c')}
CSS = """*{box-sizing:border-box}body{margin:0;background:#f6f4fc;color:#1b1740;font-family:'IBM Plex Sans Arabic',Tahoma,Arial,sans-serif;line-height:1.9;direction:rtl}
.w{max-width:820px;margin:0 auto;padding:18px}.hero{border-radius:22px;padding:30px 26px;color:#fff;background:radial-gradient(circle at 85% 10%,rgba(255,255,255,.18),transparent 40%),linear-gradient(120deg,#0f172a,#4c1d95 55%,#a24bf0)}
.hero h1{margin:0 0 6px;font-size:clamp(24px,4vw,36px);line-height:1.4}.hero small{direction:ltr;display:block;opacity:.8}
.bx{background:#fff;border:1px solid #e6e1f5;border-radius:18px;padding:14px 18px;margin-top:14px}.bx h2{margin:0 0 8px;font-size:18px}
.m{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.m span{background:rgba(255,255,255,.16);border-radius:30px;padding:0 12px;font-size:13px}
.btn{display:inline-block;margin:6px 0 0 8px;padding:6px 20px;border-radius:30px;border:1.5px solid #7c3aed;color:#7c3aed;text-decoration:none;font-weight:700}.btn.p{background:#7c3aed;color:#fff}
.ex{background:#faf7ff;border:1.5px dashed #c4b5fd;border-radius:14px;padding:10px 14px}ul{margin:0;padding-inline-start:20px}a{color:#6d28d9}
.nt{color:#65618a;font-size:13px}"""
cards = []
for s in data['skills']:
    cat = cats.get(s['cat'], 'أخرى')
    t = s.get('title_ar') or s['name']
    d = s.get('desc_ar') or s.get('desc_main') or s.get('desc_en') or ''
    url = cfg['pages_base'] + 'p/' + s['id'] + '.html'
    app = cfg['page_url'] + '#/k/' + s['id']
    gh = 'https://github.com/' + s['repo'] + ('/tree/' + s['branch'] + '/' + s['path'] if s.get('path') else '')
    sec = s.get('sec', {'level': 'safe', 'flags': []})
    lab, col = SEC.get(sec['level'], SEC['safe'])
    ld = {"@context": "https://schema.org", "@type": "SoftwareSourceCode", "name": t, "alternateName": s['name'],
          "description": d, "inLanguage": "ar", "codeRepository": gh, "url": url,
          "license": s.get('license') if s.get('license') not in (None, 'NOASSERTION') else None,
          "author": {"@type": "Person", "name": s['repo'].split('/')[0]}}
    ld = {k: v for k, v in ld.items() if v}
    parts = [f'<div class="bx"><h2>عن المهارة</h2><p>{e(d)}</p>']
    if s.get('when_ar'):
        parts.append(f'<h2>متى تستخدمها؟</h2><p>{e(s["when_ar"])}</p>')
    parts.append('</div>')
    if s.get('guide_ar'):
        parts.append('<div class="bx"><h2>ملخص الدليل بالعربي</h2><ul>' + ''.join(f'<li>{e(x)}</li>' for x in s['guide_ar']) + '</ul></div>')
    if s.get('ex_ar'):
        parts.append(f'<div class="bx"><h2>جرّب هذا الطلب</h2><div class="ex">{e(s["ex_ar"])}</div></div>')
    flags = ''.join(f'<li>{e(x)}</li>' for x in sec.get('flags', []))
    parts.append(f'<div class="bx"><h2>فحص أمني تقريبي</h2><p style="color:{col};font-weight:700">{lab}</p>' + (f'<ul>{flags}</ul>' if flags else '') + '<p class="nt">فحص آلي بالكلمات المفتاحية، ولا يغني عن القراءة اليدوية.</p></div>')
    page = f'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(t)} | مكتبة Skills للذكاء الاصطناعي بالعربي</title><meta name="description" content="{e(d[:155])}">
<link rel="canonical" href="{e(url)}"><meta property="og:title" content="{e(t)}"><meta property="og:description" content="{e(d[:155])}"><meta property="og:type" content="article">
{('<meta property="og:image" content="' + e(s["og"]) + '">') if s.get('og') else ''}
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style><script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")}</script></head><body><div class="w">
<div class="hero"><h1>{e(t)}</h1><small>{e(s["name"])}</small><div class="m"><span>{e(cat)}</span><span>★ {s["stars"]}</span><span>جودة {s["rating"]}/5</span><span>{e(s["repo"])}</span></div></div>
<div class="bx"><a class="btn p" href="{e(app)}">تحميل المهارة (ZIP)</a><a class="btn" href="{e(gh)}" rel="noopener">فتح على GitHub</a><a class="btn" href="{e(cfg["page_url"])}">كل المهارات</a></div>
{''.join(parts)}
<p class="nt">المهارة ملك لصاحبها وتُحمَّل مباشرة من مستودعه، وتخضع لرخصته. آخر تحديث: {e(data["updated"])}</p></div></body></html>'''
    (OUT / (s['id'] + '.html')).write_text(page, encoding='utf-8')
    cards.append(url)
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u in [cfg['page_url']] + cards:
    sm.append(f'<url><loc>{e(u)}</loc></url>')
sm.append('</urlset>')
(D / 'sitemap.xml').write_text('\n'.join(sm), encoding='utf-8')
print('pages', len(cards))
