#!/usr/bin/env python3
"""Build servers.json: popular MCP servers on GitHub (topic search), with install config extracted from each README,
category, weekly star growth and an Arabic description (cached in ar-cache.json).
Env: GITHUB_TOKEN (raises the API rate limit), GH_API (default https://api.github.com)."""
import json, os, re, sys, time, datetime, urllib.request, urllib.parse
here = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("GH_API", "https://api.github.com"); TOKEN = os.environ.get("GITHUB_TOKEN", "")
TOP = int(os.environ.get("MCP_TOP", 150)); today = datetime.date.today().isoformat()
def get(url, raw=False):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json", "User-Agent": "mcp-directory"})
    if TOKEN: req.add_header("Authorization", "Bearer " + TOKEN)
    b = urllib.request.urlopen(req, timeout=60).read()
    return b.decode("utf8", "replace") if raw else json.loads(b)
def jload(p, d):
    try: return json.load(open(os.path.join(here, p), encoding="utf8"))
    except Exception: return d
# ---- 1) candidates: topic searches, merged and ranked by stars ----
repos = {}
for q in ("topic:mcp-server", "topic:model-context-protocol", "topic:mcp-servers", "topic:mcp"):
    for page in (1, 2, 3):
        try: r = get("%s/search/repositories?q=%s&sort=stars&order=desc&per_page=100&page=%d" % (API, urllib.parse.quote(q), page))
        except Exception as e: print("search failed:", q, page, str(e)[:80], file=sys.stderr); break
        for it in r.get("items", []):
            if it.get("archived") or it.get("fork"): continue
            repos[it["full_name"]] = it
        if len(r.get("items", [])) < 100: break
        time.sleep(2)
    time.sleep(2)
print("candidates:", len(repos))
if not repos: sys.exit(1)
ranked = sorted(repos.values(), key=lambda x: -x["stargazers_count"])
cutoff = (datetime.date.today() - datetime.timedelta(days=75)).isoformat()
new = [x for x in ranked if x["created_at"][:10] >= cutoff][:30]
pick = {x["full_name"]: x for x in ranked[:TOP]}; pick.update({x["full_name"]: x for x in new})
# ---- 2) README -> install config ----
def find_config(md):
    for blk in re.findall(r"```(?:json|jsonc)?\s*\n(.*?)```", md, flags=re.S):
        if "mcpServers" not in blk and '"command"' not in blk: continue
        try:
            j = json.loads(re.sub(r"^\s*//.*$", "", blk, flags=re.M))
        except Exception: continue
        srv = j.get("mcpServers") or j.get("servers") or ({"x": j} if "command" in j else None)
        if srv:
            name, v = next(iter(srv.items()))
            if isinstance(v, dict) and v.get("command"):
                return {"command": v["command"], "args": [str(a) for a in v.get("args", [])], "env": sorted((v.get("env") or {}).keys())}
    m = re.search(r"npx\s+(?:-y\s+|--yes\s+)?(@?[\w.\-]+(?:/[\w.\-]+)?(?:@[\w.\-]+)?)", md)
    if m and not m.group(1).startswith(("-", "create-")): return {"command": "npx", "args": ["-y", m.group(1)], "env": []}
    m = re.search(r"uvx\s+([\w.\-]+(?:@[\w.\-]+)?)", md)
    if m: return {"command": "uvx", "args": [m.group(1)], "env": []}
    return None
CATS = [("files", ["filesystem", "file system", "files", "pdf", "document", "obsidian", "notes"]), ("db", ["postgres", "mysql", "sqlite", "mongo", "database", "sql", "redis", "supabase", "vector"]),
        ("browser", ["browser", "playwright", "puppeteer", "selenium", "scrap", "crawl", "web page", "chrome"]), ("search", ["search", "web search", "brave", "tavily", "exa", "google"]),
        ("dev", ["github", "gitlab", "git ", "code", "docker", "kubernetes", "terminal", "shell", "debug", "ide", "lsp"]), ("design", ["figma", "design", "image", "blender", "3d", "photoshop", "video"]),
        ("work", ["notion", "slack", "gmail", "email", "calendar", "jira", "linear", "asana", "trello", "discord", "telegram", "whatsapp", "drive"]),
        ("cloud", ["aws", "azure", "cloudflare", "gcp", "terraform", "vercel", "netlify"]), ("data", ["analytics", "excel", "csv", "bigquery", "data", "finance", "stock", "crypto"]),
        ("ai", ["memory", "rag", "agent", "llm", "knowledge", "reasoning", "thinking"])]
def category(it):
    t = (it["name"] + " " + (it.get("description") or "") + " " + " ".join(it.get("topics", []))).lower()
    for cid, kws in CATS:
        if any(k in t for k in kws): return cid
    return "other"
# ---- 3) Arabic descriptions (cached) ----
cache = jload("ar-cache.json", {})
def translate(t):
    try:
        j = json.loads(urllib.request.urlopen(urllib.request.Request("https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=en&tl=ar&q=" + urllib.parse.quote(t[:300]), headers={"User-Agent": "Mozilla/5.0"}), timeout=12).read())
        r = j[0] if isinstance(j[0], str) else j[0][0]
        return r if r and r != t else None
    except Exception: return None
hist = jload("servers-hist.json", {}); items = []; tr_n = 0
for full, it in pick.items():
    try: md = get("%s/repos/%s/readme" % (API, full), raw=True)
    except Exception: md = ""
    cfg = find_config(md) if md else None
    d = (it.get("description") or "").strip()
    da = cache.get(full + "|" + d)
    if d and da is None and tr_n < 120 and not re.search(r"[؀-ۿ]", d):
        da = translate(d); tr_n += 1
        if da: cache[full + "|" + d] = da
    h = hist.setdefault(full, {}); h[today] = it["stargazers_count"]
    for k in sorted(h)[:-30]: del h[k]
    ks = sorted(h); g = h[ks[-1]] - h[ks[0]] if len(ks) > 1 else 0
    items.append({"r": full, "n": it["name"], "d": d[:240], "da": (da or "")[:260], "s": it["stargazers_count"], "g": g, "l": it.get("language") or "",
                  "lic": (it.get("license") or {}).get("spdx_id") or "", "u": it["html_url"], "cfg": cfg, "c": category(it), "cr": it["created_at"][:10], "p": it["pushed_at"][:10], "nw": 1 if it["created_at"][:10] >= cutoff else 0})
    time.sleep(0.15)
items.sort(key=lambda x: -x["s"])
json.dump({"updated": today, "count": len(items), "withConfig": sum(1 for x in items if x["cfg"]), "items": items}, open(os.path.join(here, "servers.json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
json.dump(hist, open(os.path.join(here, "servers-hist.json"), "w"), separators=(",", ":"))
json.dump(dict(list(cache.items())[-800:]), open(os.path.join(here, "ar-cache.json"), "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
print("servers:", len(items), "| with install config:", sum(1 for x in items if x["cfg"]), "| translated now:", tr_n)
