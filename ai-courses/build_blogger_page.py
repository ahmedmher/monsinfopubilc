#!/usr/bin/env python3
"""يبني blogger-page.html من القالب + courses.json (فهرس ثابت + JSON-LD + FAQ)."""
import json, re, html, pathlib
d = pathlib.Path(__file__).parent
courses = json.load(open(d/'courses.json', encoding='utf-8'))['courses']
t = (d/'blogger-page.template.html').read_text(encoding='utf-8')
e = html.escape
idx = ''.join(
    f'<h3>{e(c["title"])}</h3><p>{e(c.get("description",""))}</p>'
    f'<details><summary>دروس الكورس ({len(c["lessons"])} درس)</summary><ol>'
    + ''.join(f'<li>{e(l["title"])}</li>' for l in c['lessons']) + '</ol></details>'
    for c in courses)
pub = {"@type": "Organization", "name": "مدونة مونستر للمعلوماتية", "url": "https://www.youtube.com/@monsterinfo"}
items = [{"@type": "ListItem", "position": i+1, "item": {
    "@type": "Course", "name": c['title'], "description": c.get('description') or c['title'],
    "inLanguage": "ar", "isAccessibleForFree": True, "provider": pub,
    "numberOfLessons": len(c['lessons']), "image": c['cover'],
    "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "category": "Free"},
    "hasCourseInstance": {"@type": "CourseInstance", "courseMode": "online"}}}
    for i, c in enumerate(courses)]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "CollectionPage", "name": "كورسات الذكاء الاصطناعي المجانية بالعربي", "inLanguage": "ar", "isAccessibleForFree": True, "publisher": pub},
    {"@type": "ItemList", "name": "كورسات الذكاء الاصطناعي المجانية", "numberOfItems": len(courses), "itemListElement": items}]}
faq = [(re.sub('<.*?>', '', q), re.sub('<.*?>', '', a)) for q, a in
       re.findall(r'<details><summary>(.*?)</summary><p>(.*?)</p></details>', t)]
faqld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
    {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
j = lambda o: json.dumps(o, ensure_ascii=False).replace('</', '<\\/')
out = t.replace('<!--@INDEX@-->', idx).replace('<!--@LD@-->', j(ld)).replace('<!--@FAQ@-->', j(faqld))
(d/'blogger-page.html').write_text(out, encoding='utf-8')
print('ok', len(out), 'bytes; faq', len(faq))
