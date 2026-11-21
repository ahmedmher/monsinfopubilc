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
    pref = re.compile(r'preview|cover|banner|hero|demo|screenshot|thumb|logo', re.I)
    best = None
    for f in sorted(folder.rglob('*')):
        n = f.name.lower()
        if f.is_file() and n.endswith(IMG + VID) and f.stat().st_size < 8_000_000 and 'node_modules' not in f.parts:
            if best is None or (pref.search(n) and not pref.search(best.name)):
                best = f
    if not best:
        return None
    u = f'https://raw.githubusercontent.com/{repo}/{branch}/' + best.relative_to(dst).as_posix()
    return {'type': 'video' if best.name.lower().endswith(VID) else 'image', 'url': u}

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
        out.append({
            'id': slug(f'{repo}-{rel or name}'), 'name': name, 'desc_en': desc,
            'repo': repo, 'branch': branch, 'path': rel if rel != '.' else '',
            'files': files if ok else [], 'size': total, 'zip_ok': ok,
            'media': skill_media(folder, dst, repo, branch), 'repo_media': rmedia, 'og': og,
            'stars': meta.get('stars', 0), 'license': meta.get('license', ''),
            'when': re.sub(r'\s+', ' ', body.strip())[:700]})
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

def gtr(text):
    """ترجمة مجانية عبر نقطة جوجل العامة (بدون مفتاح)."""
    import urllib.parse, time
    out = []
    for chunk in re.findall(r'.{1,400}(?:\s|$)', text, re.S):
        if not chunk.strip():
            continue
        url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ar&dt=t&q=' + urllib.parse.quote(chunk)
        for _ in range(3):
            try:
                r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30))
                out.append(''.join(x[0] for x in r[0] if x[0]))
                break
            except Exception as e:
                time.sleep(2)
        else:
            return ''
        time.sleep(0.25)
    return ' '.join(out).strip()

def main():
    old = {}
    if OUT.exists():
        for s in json.load(open(OUT, encoding='utf-8')).get('skills', []):
            old[s['id']] = s
    tmp = pathlib.Path(tempfile.mkdtemp())
    skills = []
    for cfg in SRC['repos']:
        skills += scan_repo(cfg, tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    if not skills and old:
        print('nothing fetched, keeping old file'); return
    todo = []
    for s in skills:
        h = hashlib.md5((s['name'] + s['desc_en']).encode()).hexdigest()[:10]
        s['hash'] = h
        o = old.get(s['id'])
        if o and o.get('hash') == h and o.get('desc_ar'):
            s.update({k: o[k] for k in ('title_ar', 'desc_ar', 'cat')})
        else:
            todo.append(s)
    if todo and API_KEY:
        for i in range(0, len(todo), 15):
            res = translate_batch(todo[i:i + 15])
            for s in todo[i:i + 15]:
                r = res.get(s['id'])
                if r and r.get('desc_ar'):
                    s['title_ar'], s['desc_ar'] = r.get('title_ar', ''), r['desc_ar']
                    s['cat'] = r.get('cat') if r.get('cat') in CAT_IDS else heuristic_cat(s['name'], s['desc_en'])
    elif todo:
        for s in todo:
            s['desc_ar'] = gtr(s['desc_en'][:500])
            s['title_ar'] = gtr(re.sub(r'[-_]+', ' ', s['name'])) if s['desc_ar'] else ''
        print('google translate done for', len(todo))
    for s in skills:
        s.setdefault('title_ar', ''); s.setdefault('desc_ar', '')
        if s.get('cat') not in CAT_IDS:
            s['cat'] = heuristic_cat(s['name'], s['desc_en'])
    skills.sort(key=lambda s: (-s['stars'], s['name']))
    data = {'updated': __import__('datetime').date.today().isoformat(),
            'categories': [{'id': i, 'label': l} for i, l in CATS], 'skills': skills}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('ok', len(skills), 'skills,', len(todo), 'new/changed')

if __name__ == '__main__':
    main()
