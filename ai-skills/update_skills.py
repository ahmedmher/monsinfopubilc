#!/usr/bin/env python3
"""يسحب الـ skills من مستودعات GitHub العامة (ملف sources.json)، يترجم الوصف للعربية،
ويصنّفها، ويكتب skills.json الذي تقرأه صفحة بلوجر. لا يخزّن أي ملفات skills: الزر يحمّلها من GitHub مباشرة."""
import json, os, re, subprocess, hashlib, pathlib, tempfile, urllib.request, urllib.error, shutil

D = pathlib.Path(__file__).parent
OUT = D / 'skills.json'
SRC = json.load(open(D / 'sources.json', encoding='utf-8'))
MODEL = os.environ.get('TRANSLATE_MODEL', 'claude-haiku-5-5')
API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GH_TOKEN = os.environ.get('GITHUB_TOKEN', '')

CATS = [
    ('dev', 'برمجة وتطوير'), ('docs', 'مستندات وملفات'), ('design', 'تصميم وواجهات'),
    ('content', 'كتابة ومحتوى'), ('media', 'فيديو وصوت وصور'), ('data', 'بيانات وتحليل'),
    ('automation', 'أتمتة وأدوات'), ('research', 'بحث ومعرفة'), ('business', 'أعمال وتسويق'),
    ('quality', 'اختبار وجودة وأمان'), ('other', 'أخرى')]
CAT_IDS = [c[0] for c in CATS]
KW = {
    'docs': r'docx|pdf|pptx|xlsx|spreadsheet|document|word|powerpoint|slides',
    'design': r'design|ui\b|ux|css|frontend|canvas|theme|brand|art\b',
    'media': r'video|audio|image|gif|photo|music|animation|thumbnail',
    'quality': r'test|review|security|debug|lint|audit|qa\b',
    'data': r'data|analy|sql|chart|csv|dashboard',
    'content': r'write|writing|blog|copy|humaniz|email|communication|content|doc-coauthoring',
    'business': r'market|sales|seo|lead|invoice|business|brand|competitive',
    'research': r'research|learn|knowledge|summar',
    'automation': r'mcp|automat|workflow|agent|tool|integration|skill-creator|zapier',
    'dev': r'code|api|git|build|deploy|react|python|typescript|refactor|develop',
}

def run(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k)

def parse_frontmatter(text):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', text, re.S)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    try:
        import yaml
        meta = yaml.safe_load(raw) or {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
        for k in ('name', 'description'):
            mm = re.search(rf'^{k}:\s*(.+)$', raw, re.M)
            if mm:
                meta[k] = mm.group(1).strip().strip('"\'')
    return meta, body

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

RULES = {
 'docs': [(r'\b(docx|pdf|pptx|xlsx|word|excel|powerpoint|spreadsheet|slides?|document|presentation|markdown|epub)\b', 3)],
 'design': [(r'\b(design|ui|ux|css|frontend|front-end|canvas|theme|brand|art|figma|tailwind|layout|accessibility|a11y|typography|animation)\b', 3)],
 'media': [(r'\b(video|audio|image|gif|photo|music|thumbnail|youtube|podcast|ffmpeg|voice|subtitle|caption)\b', 3)],
 'quality': [(r'\b(test|testing|tdd|review|security|debug|debugging|lint|audit|qa|performance|vulnerab\w*|e2e|benchmark)\b', 3)],
 'data': [(r'\b(data|analytics?|analysis|sql|chart|csv|dashboard|database|statistics|pandas|visuali[sz]ation)\b', 3)],
 'content': [(r'\b(writing|write|blog|copywriting|humaniz\w*|email|communication|content|article|editor|tone|translate|newsletter|resume|cover letter)\b', 3)],
 'business': [(r'\b(marketing|sales|seo|lead|invoice|business|competitive|pricing|startup|customer|brand|ads?|growth|crm)\b', 3)],
 'research': [(r'\b(research|learn\w*|knowledge|summari[sz]\w*|study|academy|tutorial|notes?|reading|citation|paper)\b', 3)],
 'automation': [(r'\b(mcp|automation|automate|workflow|agents?|integration|zapier|slack|github actions|n8n|pipeline|cli|plugin|skill-creator|skills?)\b', 2)],
 'dev': [(r'\b(code|coding|api|git|build|deploy\w*|react|python|typescript|javascript|refactor\w*|develop\w*|software|architecture|backend|node|docker|spec|planning|debugging)\b', 3)],
}

def score_cat(name, desc, body):
    best, bs = 'other', 0
    for c, rules in RULES.items():
        sc = 0
        for rx, w in rules:
            r = re.compile(rx, re.I)
            sc += w * (3 * len(r.findall(name.replace('-', ' '))) + len(r.findall(desc)) + 0.3 * len(r.findall(body)))
        if sc > bs:
            best, bs = c, sc
    return best if bs >= 2 else 'other'

def quality(s):
    """تقييم جودة شفاف من 100: شعبية المستودع + اكتمال الوصف والمحتوى + وجود سكربتات ومراجع ووسائط ورخصة."""
    import math
    pts = 38 * min(1, math.log10(s['stars'] + 1) / 5.3)
    pts += 15 * min(1, len(s['desc_en']) / 220)
    pts += 14 * min(1, s['body_len'] / 2500)
    pts += 8 * s['has']['scripts'] + 8 * s['has']['refs'] + 4 * s['has']['assets']
    pts += 6 * bool(s['media'] or s['repo_media']) + 4 * bool(s['license'])
    pts += 3 * bool(re.search(r'use when|trigger|when the user|use this', s['desc_en'], re.I))
    return round(pts)

def split_when(desc):
    m = re.search(r'(.*?)\s*((?:Use (?:this )?(?:skill )?when|Use it when|Use for|Trigger[s]? (?:on|when)|Activate when).*)$', desc, re.I)
    return (m.group(1).strip(' .'), m.group(2).strip()) if m and m.group(1).strip() else (desc, '')

def heuristic_cat(name, desc):
    t = f'{name} {desc}'.lower()
    for c, rx in KW.items():
        if re.search(rx, t):
            return c
    return 'other'

def gh_meta(repo):
    req = urllib.request.Request(f'https://api.github.com/repos/{repo}', headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'mons-skills',
        **({'Authorization': f'Bearer {GH_TOKEN}'} if GH_TOKEN else {})})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=30))
        return {'stars': d.get('stargazers_count', 0), 'license': (d.get('license') or {}).get('spdx_id') or '',
                'branch': d.get('default_branch', 'main'), 'about': d.get('description') or ''}
    except Exception as e:
        print('gh_meta failed', repo, e)
        return {}

IMG = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
VID = ('.mp4', '.webm', '.mov')
BAD = re.compile(r'shields\.io|badge|img\.shields|\.svg(\?|$)|travis|codecov|github\.com/.+/workflows|sponsor', re.I)

def readme_media(dst, repo, branch):
    """أول صورة أو فيديو رئيسي في README المستودع (يتجاهل الشارات)."""
    rd = next((f for f in dst.iterdir() if f.name.lower() in ('readme.md', 'readme.markdown')), None)
    if not rd:
        return None
    t = rd.read_text(encoding='utf-8', errors='ignore')
    cands = []
    for m in re.finditer(r'!\[[^\]]*\]\(\s*<?([^)\s>]+)|<img[^>]+src=["\']([^"\']+)|<video[^>]+src=["\']([^"\']+)|^\s*(https://github\.com/user-attachments/assets/\S+)\s*$|(https?://\S+\.(?:mp4|webm|mov))', t, re.M):
        u = next(g for g in m.groups() if g)
        cands.append(u)
    for u in cands:
        if BAD.search(u):
            continue
        if not u.startswith('http'):
            u = f'https://raw.githubusercontent.com/{repo}/{branch}/' + u.lstrip('./')
        low = u.lower().split('?')[0]
        kind = 'video' if low.endswith(VID) or ('user-attachments/assets' in low and not low.endswith(IMG)) else 'image'
        return {'type': kind, 'url': u}
    return None

def skill_media(folder, dst, repo, branch):
    """صورة/فيديو خاص بالـ skill نفسها فقط: ملف داخل مجلدها، أو صورة مذكورة في SKILL.md/README الخاص بها."""
    pref = re.compile(r'preview|cover|banner|hero|demo|screenshot|thumb|logo', re.I)
    best = None
    for f in sorted(folder.rglob('*')):
        n = f.name.lower()
        if f.is_file() and n.endswith(IMG + VID) and f.stat().st_size < 8_000_000 and 'node_modules' not in f.parts:
            if best is None or (pref.search(n) and not pref.search(best.name)):
                best = f
    if best:
        u = f'https://raw.githubusercontent.com/{repo}/{branch}/' + best.relative_to(dst).as_posix()
        return {'type': 'video' if best.name.lower().endswith(VID) else 'image', 'url': u}
    for md in (folder / 'SKILL.md', folder / 'README.md'):
        if not md.exists():
            continue
        for m in re.finditer(r'!\[[^\]]*\]\(\s*<?([^)\s>]+)|<img[^>]+src=["\']([^"\']+)', md.read_text(encoding='utf-8', errors='ignore')):
            u = next(g for g in m.groups() if g)
            if BAD.search(u) or not u.lower().split('?')[0].endswith(IMG):
                continue
            if not u.startswith('http'):
                u = f'https://raw.githubusercontent.com/{repo}/{branch}/' + (folder.relative_to(dst) / u.lstrip('./')).as_posix()
            return {'type': 'image', 'url': u}
    return None

def scan_repo(cfg, tmp):
    repo = cfg['repo']
    dst = tmp / slug(repo)
    r = run('git', 'clone', '--depth', '1', f'https://github.com/{repo}', str(dst))
    if r.returncode:
        print('clone failed', repo, r.stderr[:200]); return []
    branch = run('git', '-C', str(dst), 'rev-parse', '--abbrev-ref', 'HEAD').stdout.strip() or 'main'
    meta = gh_meta(repo)
    branch = meta.get('branch', branch)
    base = dst / cfg.get('path', '')
    rmedia = readme_media(dst, repo, branch)
    og = f'https://opengraph.githubassets.com/1/{repo}'
    out = []
    for sk in sorted(base.rglob('SKILL.md')):
        if '.git' in sk.parts or 'node_modules' in sk.parts:
            continue
        if any(x in sk.relative_to(dst).as_posix() for x in cfg.get('exclude', [])):
            continue
        folder = sk.parent
        rel = folder.relative_to(dst).as_posix()
        fm, body = parse_frontmatter(sk.read_text(encoding='utf-8', errors='ignore'))
        name = str(fm.get('name') or folder.name or repo.split('/')[-1]).strip()
        desc = re.sub(r'\s+', ' ', str(fm.get('description') or '')).strip()
        if not desc:
            first = next((l.strip() for l in body.splitlines() if l.strip() and not l.startswith('#')), '')
            desc = first[:300]
        files, total = [], 0
        for f in sorted(folder.rglob('*')):
            if f.is_file() and '.git' not in f.parts and 'node_modules' not in f.parts:
                total += f.stat().st_size
                files.append(f.relative_to(dst).as_posix())
        ok = len(files) <= SRC.get('max_files_per_skill', 60) and total <= SRC.get('max_skill_bytes', 6_000_000)
        sub = [f.relative_to(folder).as_posix().lower() for f in folder.rglob('*') if f.is_file()]
        has = {'scripts': int(any(x.startswith('scripts/') for x in sub)), 'refs': int(any(x.startswith(('references/', 'reference/', 'docs/')) for x in sub)), 'assets': int(any(x.startswith(('assets/', 'templates/', 'examples/')) for x in sub))}
        out.append({
            'has': has, 'body_len': len(body), 'body': body[:3000],
            'id': slug(f'{repo}-{rel or name}'), 'name': name, 'desc_en': desc,
            'repo': repo, 'branch': branch, 'path': rel if rel != '.' else '',
            'files': files if ok else [], 'size': total, 'zip_ok': ok,
            'media': skill_media(folder, dst, repo, branch), 'repo_media': rmedia, 'og': og,
            'stars': meta.get('stars', 0), 'license': meta.get('license', ''),
            'when': ''})
    print(repo, len(out), 'skills')
    return out

def translate_batch(items):
    """items: [{id,name,desc_en}] -> {id:{title_ar,desc_ar,cat}} عبر Claude API."""
    prompt = ('ترجم لكل skill اسمه ووصفه للعربية (عنوان قصير واضح 2-5 كلمات، ووصف 1-2 جملة بالعربية المبسطة، '
              'أبقِ أسماء الأدوات والمصطلحات التقنية بالإنجليزية كما هي) وصنّفه في واحد من: '
              + ', '.join(f'{i} ({l})' for i, l in CATS) +
              '. أعد JSON فقط على الشكل {"id": {"title_ar": "", "desc_ar": "", "cat": ""}} بلا أي نص آخر.\n\n'
              + json.dumps([{'id': i['id'], 'name': i['name'], 'description': i['desc_en'][:600]} for i in items], ensure_ascii=False))
    body = json.dumps({'model': MODEL, 'max_tokens': 8000, 'messages': [{'role': 'user', 'content': prompt}]}).encode()
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', body, {
        'content-type': 'application/json', 'x-api-key': API_KEY, 'anthropic-version': '2023-06-01'})
    try:
        res = json.load(urllib.request.urlopen(req, timeout=180))
        txt = ''.join(b.get('text', '') for b in res['content'])
        return json.loads(re.search(r'\{.*\}', txt, re.S).group(0))
    except Exception as e:
        print('translate failed:', e); return {}

GT_FAILS = {}
LAST_ERR = {}
UA = {'User-Agent': 'Mozilla/5.0'}

def _get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))

def _google(chunk):
    import urllib.parse
    r = _get('https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ar&dt=t&q=' + urllib.parse.quote(chunk))
    return ''.join(x[0] for x in r[0] if x[0])

def _mymemory(chunk):
    import urllib.parse
    url = 'https://api.mymemory.translated.net/get?langpair=en|ar&q=' + urllib.parse.quote(chunk[:450])
    r = _get(url)
    t = r['responseData']['translatedText']
    if r.get('responseStatus') != 200 or 'MYMEMORY' in t.upper():
        raise RuntimeError(str(r.get('responseDetails'))[:100])
    return t

def _lingva(chunk):
    import urllib.parse
    err = None
    for host in ('lingva.ml', 'lingva.lunar.icu'):
        try:
            return _get(f'https://{host}/api/v1/en/ar/' + urllib.parse.quote(chunk))['translation']
        except Exception as e:
            err = e
    raise err

ENGINES = [('google', _google), ('mymemory', _mymemory), ('lingva', _lingva)]

def gtr(text):
    """ترجمة مجانية بدون مفتاح: جوجل ثم MyMemory ثم Lingva. يتخطى أي محرك فشل 3 مرات متتالية."""
    import time
    out = []
    for chunk in re.findall(r'.{1,400}(?:\s|$)', text, re.S):
        if not chunk.strip():
            continue
        for name, fn in ENGINES:
            if GT_FAILS.get(name, 0) >= 3:
                continue
            try:
                out.append(fn(chunk)); GT_FAILS[name] = 0; time.sleep(0.3); break
            except Exception as e:
                GT_FAILS[name] = GT_FAILS.get(name, 0) + 1
                if name not in LAST_ERR:
                    LAST_ERR[name] = str(e)[:150]; print('translate engine failed:', name, e)
        else:
            return ''
    return ' '.join(out).strip()

def main():
    old = {}
    if OUT.exists():
        for s in json.load(open(OUT, encoding='utf-8')).get('skills', []):
            old[s['id']] = s
    ov_file = D / 'overrides.json'
    overrides = json.load(open(ov_file, encoding='utf-8')) if ov_file.exists() else {}
    tmp = pathlib.Path(tempfile.mkdtemp())
    skills = []
    for cfg in SRC['repos']:
        skills += scan_repo(cfg, tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    if not skills and old:
        print('nothing fetched, keeping old file'); return
    todo = []
    for s in skills:
        s['desc_main'], s['when_en'] = split_when(s['desc_en'])
        s['hash'] = hashlib.md5((s['name'] + s['desc_en']).encode()).hexdigest()[:10]
        o = old.get(s['id'])
        if o and o.get('hash') == s['hash'] and o.get('desc_ar'):
            s.update({k: o.get(k, '') for k in ('title_ar', 'desc_ar', 'when_ar')})
        else:
            todo.append(s)
    if todo and API_KEY:
        for i in range(0, len(todo), 15):
            res = translate_batch(todo[i:i + 15])
            for s in todo[i:i + 15]:
                r = res.get(s['id'])
                if r and r.get('desc_ar'):
                    s['title_ar'], s['desc_ar'] = r.get('title_ar', ''), r['desc_ar']
                    if r.get('cat') in CAT_IDS:
                        s['ai_cat'] = r['cat']
    elif todo:
        for s in todo:
            s['desc_ar'] = gtr(s['desc_main'][:450])
            s['when_ar'] = gtr(s['when_en'][:350]) if s['when_en'] and s['desc_ar'] else ''
            s['title_ar'] = gtr(re.sub(r'[-_]+', ' ', s['name'])) if s['desc_ar'] else ''
        print('google translate done for', len(todo))
    for s in skills:
        s.setdefault('title_ar', ''); s.setdefault('desc_ar', ''); s.setdefault('when_ar', '')
        s['cat'] = s.pop('ai_cat', None) or score_cat(s['name'], s['desc_en'], s.get('body', ''))
        s['score'] = quality(s)
        s['rating'] = 5 if s['score'] >= 52 else 4 if s['score'] >= 44 else 3 if s['score'] >= 36 else 2 if s['score'] >= 30 else 1
        ov = overrides.get(s['id']) or overrides.get(s['name']) or {}
        s.update({k: v for k, v in ov.items() if k in ('title_ar', 'desc_ar', 'when_ar', 'cat', 'featured')})
        s.pop('body', None)
    skills.sort(key=lambda s: (-bool(s.get('featured')), -s['score'], s['name']))
    data = {'updated': __import__('datetime').date.today().isoformat(),
            'categories': [{'id': i, 'label': l} for i, l in CATS], 'skills': skills}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('ok', len(skills), 'skills,', len(todo), 'new/changed')

if __name__ == '__main__':
    main()
