/* كورسات الذكاء الاصطناعي المجانية - مدونة مونستر للمعلوماتية
   يقرأ courses.json من نفس المجلد ويعرض الكورسات والدروس (يوتيوب). */
(function () {
  var script = document.currentScript;
  var base = script.src.replace(/[^\/]*$/, "");
  var root = document.getElementById("ai-courses");
  if (!root) return;

  /* خط عربي */
  if (!document.getElementById("aic-font")) {
    var f = document.createElement("link");
    f.id = "aic-font";
    f.rel = "stylesheet";
    f.href = "https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap";
    document.head.appendChild(f);
  }

  var css = `
#ai-courses{
  --bg:#f7f3ff;--ink:#3b2a5a;--muted:#7d6f99;--line:#eadfff;
  --p1:#e9ddff;--p2:#d8c4ff;--accent:#9b6df0;--accent-d:#7c4dcc;
  --pink:#ffe0ef;--mint:#d9f5e8;--peach:#ffe8d6;--sky:#dcefff;--lemon:#fff4cc;--lav:#ece2ff;
  direction:rtl;font-family:"Cairo","Segoe UI",Tahoma,Arial,sans-serif;color:var(--ink);
  background:var(--bg);border-radius:28px;padding:18px;max-width:1180px;margin:0 auto;
  box-sizing:border-box;line-height:1.7;text-align:right;
}
#ai-courses *{box-sizing:border-box;font-family:inherit}
#ai-courses a{text-decoration:none}

/* ---------- الهيرو ---------- */
#ai-courses .hero{position:relative;overflow:hidden;border-radius:26px;padding:38px 34px;
  background:linear-gradient(135deg,#e6d9ff 0%,#d6c3ff 45%,#f6d3f5 100%);}
#ai-courses .hero:before{content:"";position:absolute;left:-60px;bottom:-80px;width:280px;height:280px;border-radius:50%;background:rgba(255,255,255,.45)}
#ai-courses .hero:after{content:"";position:absolute;left:90px;top:-70px;width:160px;height:160px;border-radius:50%;background:rgba(255,255,255,.3)}
#ai-courses .badge{display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.7);color:var(--accent-d);
  border:1px solid rgba(155,109,240,.25);padding:6px 16px;border-radius:999px;font-weight:700;font-size:.82rem;position:relative;z-index:1}
#ai-courses .badge i{width:10px;height:10px;border-radius:50%;background:#6ee7a8;box-shadow:0 0 0 4px rgba(110,231,168,.3)}
#ai-courses .hero h1{position:relative;z-index:1;margin:14px 0 8px;font-size:clamp(1.6rem,4.2vw,2.7rem);line-height:1.5;font-weight:800;color:#3b1d6e}
#ai-courses .hero h1 mark{background:rgba(255,255,255,.65);color:#5b2fb3;padding:0 10px;border-radius:12px}
#ai-courses .hero p{position:relative;z-index:1;margin:0 0 18px;max-width:640px;color:#5b4a82;font-size:1rem}
#ai-courses .stats{position:relative;z-index:1;display:flex;flex-wrap:wrap;gap:10px}
#ai-courses .stat{background:rgba(255,255,255,.75);border-radius:16px;padding:8px 18px;font-weight:700;color:var(--accent-d);font-size:.92rem}
#ai-courses .stat b{font-size:1.15rem;margin-inline-start:4px}
#ai-courses .chips{position:absolute;left:26px;top:26px;z-index:1;display:flex;flex-direction:column;gap:10px;align-items:flex-start}
#ai-courses .chip{background:#fff;color:#5b2fb3;padding:7px 16px;border-radius:999px;font-weight:700;font-size:.8rem;box-shadow:0 6px 16px rgba(124,77,204,.15)}
#ai-courses .chip:nth-child(2){margin-inline-start:30px;background:#ffe0ef;color:#b0306f}
#ai-courses .chip:nth-child(3){background:#d9f5e8;color:#1f7a52}
@media(max-width:760px){#ai-courses .chips{display:none}#ai-courses .hero{padding:26px 20px}}

/* ---------- شبكة الكورسات ---------- */
#ai-courses .section-title{margin:26px 4px 14px;font-size:1.2rem;font-weight:800}
#ai-courses .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:18px}
#ai-courses .card{background:#fff;border:1px solid var(--line);border-radius:22px;overflow:hidden;cursor:pointer;
  transition:transform .2s,box-shadow .2s;box-shadow:0 4px 14px rgba(124,77,204,.07)}
#ai-courses .card:hover{transform:translateY(-5px);box-shadow:0 14px 28px rgba(124,77,204,.16)}
#ai-courses .cover{position:relative;aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;overflow:hidden}
#ai-courses .cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
#ai-courses .cover .num{font-size:3.4rem;font-weight:800;color:rgba(59,42,90,.35)}
#ai-courses .count{position:absolute;bottom:10px;right:10px;background:rgba(255,255,255,.92);color:var(--accent-d);
  padding:3px 12px;border-radius:999px;font-size:.78rem;font-weight:700;z-index:2}
#ai-courses .info{padding:14px 16px 16px}
#ai-courses .info h3{margin:0 0 10px;font-size:1.02rem;line-height:1.6;font-weight:700;color:var(--ink);min-height:3.2em}
#ai-courses .go{display:inline-flex;align-items:center;gap:6px;background:var(--p1);color:var(--accent-d);
  padding:6px 16px;border-radius:999px;font-weight:700;font-size:.85rem}
#ai-courses .card:hover .go{background:var(--accent);color:#fff}
#ai-courses .t0{background:var(--lav)}#ai-courses .t1{background:var(--pink)}#ai-courses .t2{background:var(--mint)}
#ai-courses .t3{background:var(--peach)}#ai-courses .t4{background:var(--sky)}#ai-courses .t5{background:var(--lemon)}

/* ---------- صفحة الكورس ---------- */
#ai-courses .top{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:2px 2px 14px}
#ai-courses .back{border:0;cursor:pointer;background:#fff;color:var(--accent-d);padding:9px 18px;border-radius:999px;
  font-weight:700;font-size:.9rem;box-shadow:0 3px 10px rgba(124,77,204,.12)}
#ai-courses .back:hover{background:var(--accent);color:#fff}
#ai-courses .ctitle{margin:0;font-size:clamp(1.15rem,2.6vw,1.6rem);font-weight:800;flex:1;min-width:200px}
#ai-courses .prog{background:#fff;border-radius:999px;padding:6px 16px;font-size:.82rem;font-weight:700;color:var(--accent-d)}
#ai-courses .layout{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(280px,1fr);gap:18px;align-items:start}
@media(max-width:900px){#ai-courses .layout{grid-template-columns:1fr}}
#ai-courses .player-box{background:#fff;border-radius:22px;padding:12px;border:1px solid var(--line)}
#ai-courses .player{width:100%;aspect-ratio:16/9;border:0;border-radius:16px;background:#2d1f4a;display:block}
#ai-courses .now{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;padding:12px 4px 2px}
#ai-courses .now h2{margin:0;font-size:1.05rem;font-weight:700;flex:1;min-width:200px;line-height:1.7}
#ai-courses .nav{display:flex;gap:8px}
#ai-courses .btn{border:0;cursor:pointer;background:var(--p1);color:var(--accent-d);padding:8px 16px;border-radius:999px;font-weight:700;font-size:.85rem}
#ai-courses .btn:hover:not([disabled]){background:var(--accent);color:#fff}
#ai-courses .btn[disabled]{opacity:.4;cursor:default}
#ai-courses .yt{display:inline-block;margin-top:8px;color:var(--muted);font-size:.8rem}
#ai-courses .list{position:relative;background:#fff;border-radius:22px;padding:12px;border:1px solid var(--line);max-height:640px;overflow:auto}
@media(max-width:900px){#ai-courses .list{max-height:none}}
#ai-courses .list h4{margin:4px 6px 10px;font-size:.95rem;color:var(--muted)}
#ai-courses .lesson{display:flex;gap:10px;align-items:center;padding:10px 12px;margin-bottom:8px;border-radius:16px;
  background:#faf7ff;cursor:pointer;border:1px solid transparent;transition:background .15s,border-color .15s}
#ai-courses .lesson:hover{background:var(--p1)}
#ai-courses .lesson.active{background:linear-gradient(135deg,#e6d9ff,#f6d3f5);border-color:#cdb6ff}
#ai-courses .lesson .n{flex:none;width:32px;height:32px;border-radius:50%;background:var(--p2);color:#4b2a8f;
  display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.82rem}
#ai-courses .lesson.done .n{background:#bdeed6;color:#1f7a52}
#ai-courses .lesson .t{font-size:.9rem;line-height:1.6;font-weight:600}
#ai-courses .msg{text-align:center;padding:50px 10px;color:var(--muted);font-weight:600}
#ai-courses .foot{text-align:center;color:var(--muted);font-size:.8rem;margin:22px 0 4px}
`;
  var st = document.createElement("style");
  st.textContent = css;
  document.head.appendChild(st);

  function ytId(url) {
    var m = String(url).match(/(?:v=|youtu\.be\/|embed\/|shorts\/)([A-Za-z0-9_-]{11})/);
    return m ? m[1] : "";
  }
  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : s;
    return d.innerHTML.replace(/"/g, "&quot;");
  }
  function coverUrl(c) {
    var u = String(c || "").trim();
    if (!u) return "";
    if (/^https?:\/\//i.test(u)) return u;
    if (/^[\w\-.\/]+\.(jpe?g|png|webp|gif|avif)$/i.test(u)) return base + u;
    return "";
  }
  function store(key, val) {
    try {
      if (val === undefined) return JSON.parse(localStorage.getItem(key) || "null");
      localStorage.setItem(key, JSON.stringify(val));
    } catch (e) {}
    return null;
  }

  var data = null;

  function home() {
    var lessons = data.courses.reduce(function (a, c) { return a + c.lessons.length; }, 0);
    var h = '<section class="hero">' +
      '<div class="chips"><span class="chip">Claude</span><span class="chip">Seedance 2.5</span><span class="chip">Higgsfield</span></div>' +
      '<span class="badge"><i></i>تعلّم مجانًا من يوتيوب</span>' +
      '<h1>كورسات <mark>الذكاء الاصطناعي</mark> المجانية</h1>' +
      '<p>مجموعة كورسات مرتبة درسًا بعد درس: من Claude وSeedance وHiggsfield إلى بناء المواقع والتطبيقات والربح من يوتيوب. اختر كورسًا وابدأ فورًا.</p>' +
      '<div class="stats"><span class="stat"><b>' + data.courses.length + '</b> كورسات</span>' +
      '<span class="stat"><b>' + lessons + '</b> درس</span><span class="stat">مجاني 100%</span></div></section>' +
      '<div class="section-title">اختر الكورس</div><div class="grid">';
    data.courses.forEach(function (c, i) {
      var img = coverUrl(c.cover);
      h += '<div class="card" data-id="' + esc(c.id) + '">' +
        '<div class="cover t' + (i % 6) + '"><span class="num">' + (i + 1) + '</span>' +
        (img ? '<img src="' + esc(img) + '" alt="' + esc(c.title) + '" loading="lazy" onerror="this.remove()">' : '') +
        '<span class="count">' + c.lessons.length + ' درس</span></div>' +
        '<div class="info"><h3>' + esc(c.title) + '</h3><span class="go">ابدأ الكورس ←</span></div></div>';
    });
    root.innerHTML = h + '</div><div class="foot">مدونة مونستر للمعلوماتية</div>';
    root.querySelectorAll(".card").forEach(function (el) {
      el.onclick = function () { location.hash = "#" + el.dataset.id; };
    });
  }

  function course(c, idx, auto) {
    var key = "aic-done-" + c.id;
    var done = store(key) || [];
    if (done.indexOf(idx) < 0) { done.push(idx); store(key, done); }
    var l = c.lessons[idx];
    var h = '<div class="top"><button class="back">→ كل الكورسات</button>' +
      '<h1 class="ctitle">' + esc(c.title) + '</h1>' +
      '<span class="prog">' + done.length + ' / ' + c.lessons.length + ' تمت مشاهدته</span></div>' +
      '<div class="layout"><div class="player-box">' +
      '<iframe class="player" allowfullscreen title="' + esc(l.title) + '" ' +
      'allow="accelerometer; autoplay; encrypted-media; picture-in-picture; fullscreen" ' +
      'src="https://www.youtube-nocookie.com/embed/' + ytId(l.url) + '?rel=0' + (auto ? '&autoplay=1' : '') + '"></iframe>' +
      '<div class="now"><h2>' + (idx + 1) + '. ' + esc(l.title) + '</h2><div class="nav">' +
      '<button class="btn" data-go="' + (idx + 1) + '"' + (idx + 1 >= c.lessons.length ? " disabled" : "") + '>الدرس التالي ←</button>' +
      '<button class="btn" data-go="' + (idx - 1) + '"' + (idx <= 0 ? " disabled" : "") + '>→ السابق</button></div></div>' +
      '<a class="yt" target="_blank" rel="noopener" href="' + esc(l.url) + '">فتح الدرس على يوتيوب ↗</a></div>' +
      '<div class="list"><h4>دروس الكورس (' + c.lessons.length + ')</h4>';
    c.lessons.forEach(function (x, i) {
      h += '<div class="lesson' + (i === idx ? " active" : "") + (done.indexOf(i) > -1 && i !== idx ? " done" : "") +
        '" data-i="' + i + '"><div class="n">' + (done.indexOf(i) > -1 && i !== idx ? "✓" : i + 1) +
        '</div><div class="t">' + esc(x.title) + '</div></div>';
    });
    root.innerHTML = h + "</div></div>";
    root.querySelector(".back").onclick = function () { location.hash = ""; };
    function go(i) {
      course(c, i, true);
      root.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    root.querySelectorAll(".lesson").forEach(function (el) { el.onclick = function () { go(+el.dataset.i); }; });
    root.querySelectorAll(".btn[data-go]").forEach(function (el) {
      el.onclick = function () { if (!el.disabled) go(+el.dataset.go); };
    });
    var act = root.querySelector(".lesson.active");
    var list = root.querySelector(".list");
    if (act && list && list.scrollHeight > list.clientHeight) list.scrollTop = act.offsetTop - 60;
  }

  function route() {
    var id = location.hash.replace("#", "");
    var c = data.courses.filter(function (x) { return x.id === id; })[0];
    c ? course(c, 0, false) : home();
  }

  root.innerHTML = '<div class="msg">جاري تحميل الكورسات...</div>';
  fetch(base + "courses.json?v=" + Math.floor(Date.now() / 600000))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      data = d;
      window.addEventListener("hashchange", route);
      route();
    })
    .catch(function () {
      root.innerHTML = '<div class="msg">تعذر تحميل الكورسات، حدّث الصفحة وحاول مرة أخرى.</div>';
    });
})();
