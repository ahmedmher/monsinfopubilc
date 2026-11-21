#!/usr/bin/env python3
"""يرسل إشعار تيليجرام بالمهارات الجديدة (الموجودة الآن وغير الموجودة في آخر نسخة مثبتة). يتجاهل بصمت لو لا يوجد توكن."""
import json, os, subprocess, pathlib, urllib.request, urllib.parse
D = pathlib.Path(__file__).parent
tok, chat = os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
if not tok or not chat:
    print('no telegram secrets, skip'); raise SystemExit
cfg = json.load(open(D / 'config.json', encoding='utf-8'))
now = json.load(open(D / 'skills.json', encoding='utf-8'))['skills']
try:
    old = json.loads(subprocess.check_output(['git', 'show', 'HEAD:ai-skills/skills.json'], text=True, cwd=D))['skills']
except Exception:
    print('no previous version, skip'); raise SystemExit
seen = {s['id'] for s in old}
new = [s for s in now if s['id'] not in seen and not s.get('hidden')]
if not new:
    print('nothing new'); raise SystemExit
lines = ['🧩 مهارات جديدة في مكتبة Skills:', '']
for s in new[:10]:
    lines.append(f"• {s.get('title_ar') or s['name']}\n{cfg['page_url']}#/k/{s['id']}")
if len(new) > 10:
    lines.append(f'… و{len(new) - 10} أخرى')
body = urllib.parse.urlencode({'chat_id': chat, 'text': '\n'.join(lines), 'disable_web_page_preview': 'true'}).encode()
urllib.request.urlopen(urllib.request.Request(f'https://api.telegram.org/bot{tok}/sendMessage', data=body), timeout=30)
print('sent', len(new))
