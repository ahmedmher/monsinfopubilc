#!/usr/bin/env python3
"""Build projects.json: top GitHub repos per topic (topics.json), with weekly star growth.
Env: GITHUB_TOKEN (optional, raises rate limit), GH_API (default https://api.github.com)."""
import json, os, sys, time, datetime, re, base64, urllib.request, urllib.parse
here = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("GH_API", "https://api.github.com")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
PER = 30
today = datetime.date.today()
since = (today - datetime.timedelta(days=120)).isoformat()
path = os.path.join(here, "projects.json")
try: old = json.load(open(path))
except Exception: old = {}
hist = old.get("hist", {})

def get(url, raw=False):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json", "User-Agent": "projects-board"})
    if TOKEN: req.add_header("Authorization", "Bearer " + TOKEN)
    body = urllib.request.urlopen(req, timeout=60).read()
    return body.decode("utf8", "replace") if raw else json.loads(body)

DETAIL_TOP = 15          # repos per topic that get full details (README intro, languages, release...)
DETAIL_TTL_DAYS = 7

def clean_readme(md):
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    md = re.sub(r"<!--.*?-->", " ", md, flags=re.S)
    heads = [re.sub(r"[#*`\[\]]|\(.*?\)", "", h).strip() for h in re.findall(r"^##\s+(.+)$", md, flags=re.M)]
    heads = [h for h in heads if 2 < len(h) < 60][:8]
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)
    md = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", " ", md)
    md = re.sub(r"<[^>]+>", " ", md)
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)
    paras = []
    for blk in re.split(r"\n\s*\n", md):
        s = re.sub(r"[#*`>_|]", "", blk)
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) >= 60 and not s.lower().startswith(("table of contents", "license")):
            paras.append(s)
        if len(paras) == 3: break
    return " ".join(paras)[:800], heads

def fetch_details(full):
    d = {}
    r = get("%s/repos/%s" % (API, full))
    d.update({"w": r.get("subscribers_count", r.get("watchers_count", 0)), "i": r.get("open_issues_count", 0),
              "lic": ((r.get("license") or {}).get("spdx_id") or ""), "hp": r.get("homepage") or "",
              "br": r.get("default_branch") or "main", "sz": r.get("size", 0)})
    try:
        langs = get("%s/repos/%s/languages" % (API, full))
        tot = sum(langs.values()) or 1
        d["ls"] = [[k, round(v * 100 / tot)] for k, v in sorted(langs.items(), key=lambda kv: -kv[1])[:5]]
    except Exception: d["ls"] = []
    try:
        rel = get("%s/repos/%s/releases/latest" % (API, full))
        d["rel"] = [rel.get("tag_name", ""), (rel.get("published_at") or "")[:10]]
    except Exception: d["rel"] = []
    try:
        d["r"], d["h"] = clean_readme(get("%s/repos/%s/readme" % (API, full), raw=True))
    except Exception: d["r"], d["h"] = "", []
    d["at"] = today.isoformat()
    return d

topics_out = []
for t in json.load(open(os.path.join(here, "topics.json"))):
    q = "%s stars:>=%d pushed:>=%s archived:false" % (t["q"], t["min"], since)
    url = "%s/search/repositories?%s" % (API, urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": PER}))
    try:
        items = get(url).get("items", [])
    except Exception as e:
        print("failed", t["id"], e, file=sys.stderr)
        prev = [x for x in old.get("topics", []) if x["id"] == t["id"]]
        if prev: topics_out.append(prev[0])
        continue
    out = []
    for r in items:
        full = r["full_name"]
        h = hist.setdefault(full, {})
        h[today.isoformat()] = r["stargazers_count"]
        for d in sorted(h)[:-8]: del h[d]
        first = h[sorted(h)[0]]
        out.append({"n": full, "d": (r.get("description") or "")[:220], "s": r["stargazers_count"], "f": r["forks_count"],
                    "l": r.get("language") or "", "u": r["html_url"], "p": r["pushed_at"][:10], "c": r["created_at"][:10],
                    "t": (r.get("topics") or [])[:4], "g": r["stargazers_count"] - first, "o": r["owner"]["login"]})
    topics_out.append({"id": t["id"], "label": t["label"], "items": out})
    time.sleep(2.2)  # stay under the search rate limit
details = old.get("details", {}) if False else {}
try: details = json.load(open(os.path.join(here, "details.json")))
except Exception: details = {}
want = []
for t in topics_out:
    for x in t["items"][:DETAIL_TOP]:
        if x["n"] not in want: want.append(x["n"])
pushed = {x["n"]: x["p"] for t in topics_out for x in t["items"]}
for full in want:
    d = details.get(full)
    if d and (today - datetime.date.fromisoformat(d["at"])).days < DETAIL_TTL_DAYS: continue
    try:
        details[full] = fetch_details(full)
    except Exception as e:
        print("detail failed", full, e, file=sys.stderr)
    time.sleep(0.3)
details = {k: v for k, v in details.items() if k in want}
json.dump(details, open(os.path.join(here, "details.json"), "w"), ensure_ascii=False, separators=(",", ":"))
keep = {x["n"] for t in topics_out for x in t["items"]}
hist = {k: v for k, v in hist.items() if k in keep}
json.dump({"updated": today.isoformat(), "topics": topics_out, "hist": hist}, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
print("wrote", sum(len(t["items"]) for t in topics_out), "repos")
