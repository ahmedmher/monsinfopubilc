/*! Pose Mannequin — أداة مانيكان 3D للتحكم بالوضعيات بالماوس (Three.js r128)
 *  الاستخدام:  <div id="pose-mannequin"></div>  +  <script src=".../pose-mannequin.js"></script>
 */
(function () {
  'use strict';
  var THREE_URL = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';

  function boot() {
    if (window.THREE) return init();
    var s = document.createElement('script');
    s.src = THREE_URL;
    s.onload = init;
    s.onerror = function () { alert('تعذر تحميل مكتبة Three.js'); };
    document.head.appendChild(s);
  }

  var CSS = '\
#pm-app{font-family:Tahoma,Arial,sans-serif;direction:rtl;color:#222;max-width:1100px;margin:0 auto;box-sizing:border-box}\
#pm-app *{box-sizing:border-box}\
#pm-app .pm-main{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start}\
#pm-app .pm-stagewrap{flex:1 1 460px;min-width:280px}\
#pm-app .pm-stage{width:100%;aspect-ratio:3/4;border-radius:14px;overflow:hidden;background:#e8e6e0;position:relative;touch-action:none;box-shadow:0 2px 14px rgba(0,0,0,.18)}\
#pm-app .pm-stage canvas{display:block;width:100%;height:100%}\
#pm-app .pm-hint{font-size:12px;color:#666;margin:6px 2px;line-height:1.7}\
#pm-app .pm-side{flex:0 0 320px;max-width:100%;display:flex;flex-direction:column;gap:12px}\
#pm-app .pm-card{background:#fafafa;border:1px solid #e3e3e3;border-radius:12px;padding:12px}\
#pm-app h4{margin:0 0 8px;font-size:14px}\
#pm-app .pm-btns{display:flex;flex-wrap:wrap;gap:6px}\
#pm-app button,#pm-app select{font:inherit;font-size:13px;padding:7px 11px;border-radius:8px;border:1px solid #cfcfcf;background:#fff;cursor:pointer;color:#222}\
#pm-app button:hover{background:#f0f0f0}\
#pm-app button.pm-primary{background:#5b3df5;border-color:#5b3df5;color:#fff;font-weight:bold}\
#pm-app button.pm-primary:hover{background:#4a2fe0}\
#pm-app label{display:block;font-size:12px;margin:8px 0 2px;color:#444}\
#pm-app input[type=range]{width:100%}\
#pm-app textarea{width:100%;min-height:70px;font:inherit;font-size:13px;border:1px solid #cfcfcf;border-radius:8px;padding:8px;resize:vertical}\
#pm-app .pm-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}\
#pm-app img.pm-prev{max-width:100%;border-radius:8px;border:1px solid #ddd;display:none;margin-top:8px;background:#e8e6e0}\
#pm-app .pm-toast{font-size:12px;color:#0a7a3d;min-height:16px;margin-top:4px}';

  var HTML = '\
<div class="pm-main">\
 <div class="pm-stagewrap">\
  <div class="pm-stage" id="pm-stage"></div>\
  <div class="pm-hint">🖱️ اسحب الدوائر الملونة لتحريك المفاصل (يد/كوع/قدم/ركبة/حوض/صدر/راس) · <b>Shift</b> أثناء السحب = تحريك للأمام/للخلف · اسحب الخلفية للدوران · عجلة الماوس للتقريب · كليك يمين وسحب = تحريك الكاميرا</div>\
 </div>\
 <div class="pm-side">\
  <div class="pm-card"><h4>وضعيات جاهزة</h4>\
   <div class="pm-btns" id="pm-presets"></div></div>\
  <div class="pm-card"><h4>لف الجسم</h4>\
   <label>لف الحوض <span id="pm-v-hip">0</span>°</label><input type="range" id="pm-hip" min="-90" max="90" value="0">\
   <label>لف الصدر <span id="pm-v-chest">0</span>°</label><input type="range" id="pm-chest" min="-90" max="90" value="0">\
   <label>لف الراس <span id="pm-v-head">0</span>°</label><input type="range" id="pm-head" min="-90" max="90" value="0">\
  </div>\
  <div class="pm-card"><h4>الصورة</h4>\
   <div class="pm-row"><label style="margin:0">النسبة</label>\
    <select id="pm-aspect"><option value="3/4">3:4</option><option value="1/1">1:1</option><option value="4/3">4:3</option><option value="9/16">9:16</option><option value="16/9">16:9</option></select>\
    <select id="pm-mode"><option value="mannequin">مانيكان رمادي</option><option value="skeleton">هيكل OpenPose</option></select></div>\
   <div class="pm-row" style="margin-top:8px"><button class="pm-primary" id="pm-export">📸 توليد صورة الوضعية</button></div>\
   <img class="pm-prev" id="pm-prev" alt="pose">\
   <div class="pm-row" id="pm-after" style="margin-top:8px;display:none"><button id="pm-dl">⬇️ تحميل PNG</button><button id="pm-copyimg">📋 نسخ الصورة</button></div>\
  </div>\
  <div class="pm-card"><h4>برومبت الذكاء الاصطناعي</h4>\
   <label>صف الشخص/المشهد</label>\
   <textarea id="pm-desc" placeholder="مثال: شاب بجاكيت جلد بني وكاب أحمر ونظارة، خلفية استوديو بيضاء"></textarea>\
   <label>الستايل</label>\
   <select id="pm-style" style="width:100%"><option value="photorealistic, studio lighting, 85mm lens, sharp focus">صورة واقعية</option><option value="cinematic film still, dramatic lighting">سينمائي</option><option value="anime style, clean line art, vibrant colors">أنمي</option><option value="3D render, Pixar style, soft lighting">3D كرتوني</option><option value="digital illustration, concept art">رسم رقمي</option></select>\
   <div class="pm-row" style="margin-top:8px"><button id="pm-mkprompt">✍️ ابني البرومبت</button><button id="pm-copyprompt">📋 نسخ</button></div>\
   <textarea id="pm-prompt" readonly style="margin-top:8px"></textarea>\
   <div class="pm-hint">ارفع صورة الوضعية في أداة الذكاء الاصطناعي (ChatGPT / Gemini / Stable Diffusion ControlNet) مع البرومبت.</div>\
   <div class="pm-toast" id="pm-toast"></div>\
  </div>\
 </div>\
</div>';

  function init() {
    var THREE = window.THREE;
    var host = document.getElementById('pose-mannequin');
    if (!host) {
      host = document.createElement('div');
      host.id = 'pose-mannequin';
      var cs = document.currentScript || document.scripts[document.scripts.length - 1];
      if (cs && cs.parentNode) cs.parentNode.insertBefore(host, cs); else document.body.appendChild(host);
    }
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    host.innerHTML = '<div id="pm-app">' + HTML + '</div>';
    var $ = function (id) { return document.getElementById(id); };

    /* ---------- three setup ---------- */
    var wrap = $('pm-stage');
    var renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    wrap.appendChild(renderer.domElement);
    var scene = new THREE.Scene();
    scene.background = new THREE.Color(0xe8e6e0);
    var camera = new THREE.PerspectiveCamera(35, 0.75, 0.1, 60);
    var orbit = { theta: 0, phi: 1.4, r: 3.5, target: new THREE.Vector3(0, 0.9, 0) };
    function placeCamera() {
      var o = orbit;
      camera.position.set(
        o.target.x + o.r * Math.sin(o.phi) * Math.sin(o.theta),
        o.target.y + o.r * Math.cos(o.phi),
        o.target.z + o.r * Math.sin(o.phi) * Math.cos(o.theta));
      camera.lookAt(o.target);
    }
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8a84, 0.85));
    var sun = new THREE.DirectionalLight(0xffffff, 0.75);
    sun.position.set(2, 4, 3); sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    var sc = sun.shadow.camera; sc.left = -3; sc.right = 3; sc.top = 3; sc.bottom = -3; sc.near = 0.5; sc.far = 12;
    scene.add(sun);
    var floor = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), new THREE.ShadowMaterial({ opacity: 0.22 }));
    floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
    var grid = new THREE.GridHelper(6, 12, 0xaaaaaa, 0xcfcfca); grid.position.y = 0.001; scene.add(grid);

    /* ---------- body parts ---------- */
    var V = function (x, y, z) { return new THREE.Vector3(x, y, z); };
    var mat = new THREE.MeshStandardMaterial({ color: 0xc4c4c4, roughness: 0.55, metalness: 0 });
    var body = new THREE.Group(); scene.add(body);
    var Yaxis = V(0, 1, 0), tmp = V(0, 0, 0), M4 = new THREE.Matrix4();
    function mkSeg(r1, r2) { var m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, 1, 20), mat); m.castShadow = true; body.add(m); return m; }
    function mkBall(r) { var m = new THREE.Mesh(new THREE.SphereGeometry(r || 1, 24, 16), mat); m.castShadow = true; body.add(m); return m; }
    function setSeg(m, a, b) {
      tmp.subVectors(b, a); var L = tmp.length() || 1e-4;
      m.position.copy(a).addScaledVector(tmp, 0.5);
      m.quaternion.setFromUnitVectors(Yaxis, tmp.normalize());
      m.scale.set(1, L, 1);
    }
    function setEll(m, c, f, sx, sy, sz) {
      m.position.copy(c);
      m.quaternion.setFromRotationMatrix(M4.makeBasis(f.x, f.y, f.z));
      m.scale.set(sx, sy, sz);
    }
    var P = {
      pelvis: mkBall(1), abdomen: mkBall(1), chest: mkBall(1), neck: mkSeg(0.04, 0.045), head: mkBall(1), nose: mkBall(0.022),
      shL: mkBall(0.055), shR: mkBall(0.055), elL: mkBall(0.042), elR: mkBall(0.042),
      uaL: mkSeg(0.04, 0.05), uaR: mkSeg(0.04, 0.05), faL: mkSeg(0.03, 0.04), faR: mkSeg(0.03, 0.04),
      haL: mkBall(1), haR: mkBall(1),
      hpL: mkBall(0.07), hpR: mkBall(0.07), knL: mkBall(0.055), knR: mkBall(0.055),
      thL: mkSeg(0.055, 0.075), thR: mkSeg(0.055, 0.075), shnL: mkSeg(0.04, 0.055), shnR: mkSeg(0.04, 0.055),
      anL: mkBall(0.04), anR: mkBall(0.04), ftL: mkBall(1), ftR: mkBall(1)
    };

    /* ---------- state ---------- */
    var LEN = { torso: 0.5, neck: 0.1, headC: 0.23, ua: 0.30, fa: 0.28, th: 0.45, sh: 0.45, shW: 0.19, hipW: 0.1 };
    var S = {};  // vectors
    var tw = { hip: 0, chest: 0, head: 0 };
    var J = {};  // computed joints
    var KEYS = ['pelvis', 'chest', 'head', 'handL', 'handR', 'elbowL', 'elbowR', 'footL', 'footR', 'kneeL', 'kneeR'];
    var COL = { pelvis: 0xff9800, chest: 0xff9800, head: 0xe91e63, handL: 0x2196f3, handR: 0x2196f3, elbowL: 0x00bcd4, elbowR: 0x00bcd4, footL: 0x4caf50, footR: 0x4caf50, kneeL: 0x8bc34a, kneeR: 0x8bc34a };
    var handleGroup = new THREE.Group(); scene.add(handleGroup);
    var H = {}, handleMeshes = [];
    KEYS.forEach(function (k) {
      var big = (k === 'pelvis' || k === 'chest' || k === 'head' || k.indexOf('hand') === 0 || k.indexOf('foot') === 0);
      var m = new THREE.Mesh(new THREE.SphereGeometry(big ? 0.05 : 0.038, 16, 12),
        new THREE.MeshBasicMaterial({ color: COL[k], transparent: true, opacity: 0.92, depthTest: false }));
      m.renderOrder = 10; m.userData.key = k; handleGroup.add(m); H[k] = m; handleMeshes.push(m);
    });

    function mirror(p) { return p; }
    var PRESETS = {
      'واقف': function () { return { pelvis: V(0, .95, 0), chest: V(0, 1.45, 0), head: V(0, 1.75, 0), handL: V(.26, .9, .05), handR: V(-.26, .9, .05), elbowL: V(.32, 1.15, -.35), elbowR: V(-.32, 1.15, -.35), footL: V(.12, .05, 0), footR: V(-.12, .05, 0), kneeL: V(.12, .5, .6), kneeR: V(-.12, .5, .6) }; },
      'T-Pose': function () { return { pelvis: V(0, .95, 0), chest: V(0, 1.45, 0), head: V(0, 1.75, 0), handL: V(.75, 1.41, 0), handR: V(-.75, 1.41, 0), elbowL: V(.4, 1.41, -.4), elbowR: V(-.4, 1.41, -.4), footL: V(.12, .05, 0), footR: V(-.12, .05, 0), kneeL: V(.12, .5, .6), kneeR: V(-.12, .5, .6) }; },
      'دراعات متقاطعة': function () { return { pelvis: V(0, .95, 0), chest: V(0, 1.45, 0), head: V(0, 1.75, 0), handL: V(-.22, 1.4, .13), handR: V(.24, 1.27, .16), elbowL: V(.2, 1.0, .4), elbowR: V(-.2, 1.0, .5), footL: V(.15, .05, 0), footR: V(-.15, .05, 0), kneeL: V(.15, .5, .6), kneeR: V(-.15, .5, .6) }; },
      'قاعد': function () { return { pelvis: V(0, .5, 0), chest: V(0, .97, .1), head: V(0, 1.27, .14), handL: V(.2, .56, .4), handR: V(-.2, .56, .4), elbowL: V(.45, .9, -.1), elbowR: V(-.45, .9, -.1), footL: V(.12, .05, .5), footR: V(-.12, .05, .5), kneeL: V(.12, .6, .7), kneeR: V(-.12, .6, .7) }; },
      'ماشي': function () { return { pelvis: V(0, .88, 0), chest: V(0, 1.38, .04), head: V(0, 1.68, .06), handL: V(.22, .95, -.28), handR: V(-.2, 1.0, .32), elbowL: V(.3, 1.0, -.6), elbowR: V(-.3, 1.0, -.2), footL: V(.1, .05, .38), footR: V(-.1, .15, -.35), kneeL: V(.1, .5, .9), kneeR: V(-.1, .4, .4) }; },
      'مستلقي': function () { return { pelvis: V(0, .14, -.1), chest: V(0, .14, .4), head: V(0, .14, .8), handL: V(-.3, .07, -.05), handR: V(.3, .07, -.05), elbowL: V(-.5, .3, .1), elbowR: V(.5, .3, .1), footL: V(-.1, .07, -.95), footR: V(.1, .07, -.95), kneeL: V(-.1, .8, -.6), kneeR: V(.1, .8, -.6) }; }
    };
    function setPose(name) {
      var p = PRESETS[name](); KEYS.forEach(function (k) { S[k] = p[k]; });
      tw.hip = tw.chest = tw.head = 0; syncSliders();
      var lying = name === 'مستلقي'; orbit.phi = lying ? 0.55 : 1.4; orbit.target.set(0, lying ? 0.25 : 0.9, 0); orbit.r = lying ? 3.6 : 3.5; placeCamera(); update();
    }
    var pr = $('pm-presets');
    Object.keys(PRESETS).forEach(function (n) {
      var b = document.createElement('button'); b.textContent = n; b.onclick = function () { setPose(n); }; pr.appendChild(b);
    });

    /* ---------- kinematics ---------- */
    function frame(up, twist) {
      var base = V(0, 0, 1); base.addScaledVector(up, -base.dot(up));
      if (base.lengthSq() < 0.04) { base.set(0, 1, 0); base.addScaledVector(up, -base.dot(up)); }
      base.normalize().applyAxisAngle(up, twist);
      var side = new THREE.Vector3().crossVectors(up, base).normalize();
      var fwd = new THREE.Vector3().crossVectors(side, up).normalize();
      return { x: side, y: up.clone(), z: fwd };
    }
    function ik(root, target, pole, l1, l2) {
      var d = new THREE.Vector3().subVectors(target, root), dist = d.length();
      if (dist < 1e-6) d.set(0, -1, 0);
      d.normalize();
      var D = Math.min(Math.max(dist, Math.abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3);
      var end = root.clone().addScaledVector(d, D);
      var a = (l1 * l1 - l2 * l2 + D * D) / (2 * D);
      var h = Math.sqrt(Math.max(l1 * l1 - a * a, 0));
      var p = new THREE.Vector3().subVectors(pole, root); p.addScaledVector(d, -p.dot(d));
      if (p.lengthSq() < 1e-6) { p.set(0, 0, 1); p.addScaledVector(d, -p.dot(d)); if (p.lengthSq() < 1e-6) p.set(1, 0, 0); }
      p.normalize();
      return { mid: root.clone().addScaledVector(d, a).addScaledVector(p, h), end: end };
    }
    var DEG = Math.PI / 180;
    function update() {
      var pel = S.pelvis;
      var up = new THREE.Vector3().subVectors(S.chest, pel);
      if (up.lengthSq() < 1e-6) up.set(0, 1, 0); up.normalize();
      var Cpt = pel.clone().addScaledVector(up, LEN.torso);
      var fu = up.y > 0.6 ? V(0, 1, 0) : up.clone();
      var fc = frame(up, tw.chest * DEG), fh = frame(fu, tw.hip * DEG);
      var hdir = new THREE.Vector3().subVectors(S.head, Cpt); if (hdir.lengthSq() < 1e-6) hdir.copy(up); hdir.normalize();
      var Hc = Cpt.clone().addScaledVector(hdir, LEN.headC), Nk = Cpt.clone().addScaledVector(hdir, LEN.neck);
      var fHd = frame(hdir, (tw.chest + tw.head) * DEG);

      J.pelvis = pel; J.chest = Cpt; J.head = Hc; J.neck = Cpt.clone();
      setEll(P.pelvis, pel, fh, .17, .11, .11);
      setEll(P.abdomen, pel.clone().addScaledVector(up, .2), fc, .15, .17, .1);
      setEll(P.chest, Cpt.clone().addScaledVector(up, -.13), fc, .2, .17, .115);
      setSeg(P.neck, Cpt, Nk);
      setEll(P.head, Hc, fHd, .095, .12, .105);
      P.nose.position.copy(Hc).addScaledVector(fHd.z, .098).addScaledVector(fHd.y, -.015);
      J.nose = Hc.clone().addScaledVector(fHd.z, .105);
      J.eyeL = Hc.clone().addScaledVector(fHd.z, .085).addScaledVector(fHd.x, .035).addScaledVector(fHd.y, .02);
      J.eyeR = Hc.clone().addScaledVector(fHd.z, .085).addScaledVector(fHd.x, -.035).addScaledVector(fHd.y, .02);
      J.earL = Hc.clone().addScaledVector(fHd.x, .097); J.earR = Hc.clone().addScaledVector(fHd.x, -.097);

      [['L', 1], ['R', -1]].forEach(function (s) {
        var n = s[0], k = s[1];
        var sh = Cpt.clone().addScaledVector(fc.x, k * LEN.shW).addScaledVector(up, -.04);
        var a = ik(sh, S['hand' + n], S['elbow' + n], LEN.ua, LEN.fa);
        P['sh' + n].position.copy(sh); P['el' + n].position.copy(a.mid);
        setSeg(P['ua' + n], sh, a.mid); setSeg(P['fa' + n], a.mid, a.end);
        var df = new THREE.Vector3().subVectors(a.end, a.mid).normalize();
        var hx = new THREE.Vector3().crossVectors(df, fc.z); if (hx.lengthSq() < 1e-4) hx.crossVectors(df, V(1, 0, 0)); hx.normalize();
        var hz = new THREE.Vector3().crossVectors(hx, df).normalize();
        setEll(P['ha' + n], a.end.clone().addScaledVector(df, .05), { x: hx, y: df, z: hz }, .022, .075, .045);
        J['sho' + n] = sh; J['elb' + n] = a.mid; J['wri' + n] = a.end;

        var hip = pel.clone().addScaledVector(fh.x, k * LEN.hipW).addScaledVector(fu, -.04);
        var l = ik(hip, S['foot' + n], S['knee' + n], LEN.th, LEN.sh);
        P['hp' + n].position.copy(hip); P['kn' + n].position.copy(l.mid); P['an' + n].position.copy(l.end);
        setSeg(P['th' + n], hip, l.mid); setSeg(P['shn' + n], l.mid, l.end);
        setEll(P['ft' + n], l.end.clone().addScaledVector(fh.z, .07).addScaledVector(fh.y, -.012), fh, .045, .035, .11);
        J['hip' + n] = hip; J['kne' + n] = l.mid; J['ank' + n] = l.end;

        H['hand' + n].position.copy(a.end); H['elbow' + n].position.copy(a.mid);
        H['foot' + n].position.copy(l.end); H['knee' + n].position.copy(l.mid);
      });
      H.pelvis.position.copy(pel); H.chest.position.copy(Cpt); H.head.position.copy(Hc);
      dirty = true;
    }

    /* ---------- interaction ---------- */
    var dirty = true, drag = null, orb = null, hoverKey = null;
    var ray = new THREE.Raycaster(), mouse = new THREE.Vector2(), pointers = {}, pinch0 = 0;
    var MINY = { footL: .04, footR: .04, handL: .03, handR: .03, pelvis: .08 };
    function setMouse(e) { var r = renderer.domElement.getBoundingClientRect(); mouse.x = ((e.clientX - r.left) / r.width) * 2 - 1; mouse.y = -((e.clientY - r.top) / r.height) * 2 + 1; ray.setFromCamera(mouse, camera); }
    function camFwd() { var d = new THREE.Vector3(); camera.getWorldDirection(d); return d; }
    function applyDrag(k, np) {
      var old = H[k].position.clone();
      np.y = Math.max(np.y, MINY[k] || 0.02);
      if (k === 'pelvis') { var d = np.clone().sub(old); S.pelvis.copy(np); S.chest.add(d); S.head.add(d); }
      else if (k === 'chest') { var d2 = np.clone().sub(old); S.chest.copy(np); S.head.add(d2); }
      else S[k].copy(np);
      update();
    }
    var cv = renderer.domElement;
    cv.addEventListener('contextmenu', function (e) { e.preventDefault(); });
    cv.addEventListener('pointerdown', function (e) {
      cv.setPointerCapture(e.pointerId); pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
      if (Object.keys(pointers).length === 2) { drag = null; orb = null; var ps = Object.keys(pointers).map(function (i) { return pointers[i]; }); pinch0 = Math.hypot(ps[0].x - ps[1].x, ps[0].y - ps[1].y); return; }
      setMouse(e);
      var hit = e.button === 2 ? [] : ray.intersectObjects(handleMeshes);
      if (hit.length) {
        var k = hit[0].object.userData.key, pos = H[k].position.clone();
        var plane = new THREE.Plane().setFromNormalAndCoplanarPoint(camFwd(), pos);
        var ip = new THREE.Vector3(); ray.ray.intersectPlane(plane, ip);
        drag = { k: k, plane: plane, off: pos.clone().sub(ip || pos), y: e.clientY };
        setSel(k);
      } else orb = { x: e.clientX, y: e.clientY, pan: e.button === 2 || e.button === 1 };
    });
    cv.addEventListener('pointermove', function (e) {
      if (pointers[e.pointerId]) pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
      var keys = Object.keys(pointers);
      if (keys.length === 2) {
        var a = pointers[keys[0]], b = pointers[keys[1]], dd = Math.hypot(a.x - b.x, a.y - b.y);
        if (pinch0) { orbit.r = Math.min(10, Math.max(1.5, orbit.r * pinch0 / dd)); placeCamera(); dirty = true; } pinch0 = dd; return;
      }
      if (drag) {
        setMouse(e);
        var cur = H[drag.k].position.clone();
        if (e.shiftKey) {
          var dy = e.clientY - drag.y; drag.y = e.clientY;
          cur.addScaledVector(camFwd(), -dy * 0.006);
          drag.plane.setFromNormalAndCoplanarPoint(camFwd(), cur); drag.off.set(0, 0, 0);
          applyDrag(drag.k, cur);
        } else {
          var ip = new THREE.Vector3();
          if (ray.ray.intersectPlane(drag.plane, ip)) applyDrag(drag.k, ip.add(drag.off));
        }
      } else if (orb) {
        var dx = e.clientX - orb.x, dy2 = e.clientY - orb.y; orb.x = e.clientX; orb.y = e.clientY;
        if (orb.pan) {
          var right = V(1, 0, 0).applyQuaternion(camera.quaternion), upv = V(0, 1, 0).applyQuaternion(camera.quaternion), k2 = orbit.r * 0.0018;
          orbit.target.addScaledVector(right, -dx * k2).addScaledVector(upv, dy2 * k2);
        } else {
          orbit.theta -= dx * 0.008; orbit.phi = Math.min(Math.PI - 0.15, Math.max(0.15, orbit.phi - dy2 * 0.008));
        }
        placeCamera(); dirty = true;
      } else {
        setMouse(e); var h = ray.intersectObjects(handleMeshes);
        var hk = h.length ? h[0].object.userData.key : null;
        if (hk !== hoverKey) { hoverKey = hk; cv.style.cursor = hk ? 'grab' : 'default'; }
      }
    });
    function up(e) { delete pointers[e.pointerId]; pinch0 = 0; drag = null; orb = null; setSel(null); }
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('wheel', function (e) { e.preventDefault(); orbit.r = Math.min(10, Math.max(1.5, orbit.r * Math.exp(e.deltaY * 0.001))); placeCamera(); dirty = true; }, { passive: false });
    function setSel(k) { KEYS.forEach(function (n) { H[n].scale.setScalar(n === k ? 1.5 : 1); }); dirty = true; }

    /* ---------- sliders / ui ---------- */
    function syncSliders() { ['hip', 'chest', 'head'].forEach(function (n) { $('pm-' + n).value = tw[n]; $('pm-v-' + n).textContent = tw[n]; }); }
    ['hip', 'chest', 'head'].forEach(function (n) {
      $('pm-' + n).addEventListener('input', function () { tw[n] = +this.value; $('pm-v-' + n).textContent = this.value; update(); });
    });
    $('pm-aspect').addEventListener('change', function () { wrap.style.aspectRatio = this.value; resize(); });
    function resize() {
      var w = wrap.clientWidth, h = wrap.clientHeight; if (!w || !h) return;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); dirty = true;
    }
    if (window.ResizeObserver) new ResizeObserver(resize).observe(wrap); else window.addEventListener('resize', resize);

    /* ---------- export ---------- */
    var lastURL = null;
    function snapshot(mode) {
      var w = wrap.clientWidth, h = wrap.clientHeight, s = Math.max(1, 1280 / Math.max(w, h)), url;
      var hv = handleGroup.visible, gv = grid.visible; handleGroup.visible = false; grid.visible = false;
      if (mode === 'skeleton') {
        var c = document.createElement('canvas'); c.width = Math.round(w * s); c.height = Math.round(h * s);
        var g = c.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, c.width, c.height);
        var pt = function (v) { var p = v.clone().project(camera); return [(p.x * .5 + .5) * c.width, (-p.y * .5 + .5) * c.height]; };
        var pts = { nose: J.nose, neck: J.chest, shoR: J.shoR, elbR: J.elbR, wriR: J.wriR, shoL: J.shoL, elbL: J.elbL, wriL: J.wriL, hipR: J.hipR, kneR: J.kneR, ankR: J.ankR, hipL: J.hipL, kneL: J.kneL, ankL: J.ankL, eyeR: J.eyeR, eyeL: J.eyeL, earR: J.earR, earL: J.earL };
        var E = [['neck', 'shoR'], ['neck', 'shoL'], ['shoR', 'elbR'], ['elbR', 'wriR'], ['shoL', 'elbL'], ['elbL', 'wriL'], ['neck', 'hipR'], ['hipR', 'kneR'], ['kneR', 'ankR'], ['neck', 'hipL'], ['hipL', 'kneL'], ['kneL', 'ankL'], ['neck', 'nose'], ['nose', 'eyeR'], ['eyeR', 'earR'], ['nose', 'eyeL'], ['eyeL', 'earL']];
        var lw = Math.max(4, c.width / 110); g.lineCap = 'round';
        E.forEach(function (e, i) { var a = pt(pts[e[0]]), b = pt(pts[e[1]]); g.strokeStyle = 'hsl(' + (i * 21) + ',100%,50%)'; g.lineWidth = lw; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); });
        Object.keys(pts).forEach(function (k, i) { var a = pt(pts[k]); g.fillStyle = 'hsl(' + (i * 20) + ',100%,55%)'; g.beginPath(); g.arc(a[0], a[1], lw * 0.8, 0, 7); g.fill(); });
        url = c.toDataURL('image/png');
      } else {
        renderer.setPixelRatio(s); renderer.setSize(w, h, false); renderer.render(scene, camera);
        url = renderer.domElement.toDataURL('image/png');
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); renderer.setSize(w, h, false);
      }
      handleGroup.visible = hv; grid.visible = gv; dirty = true; return url;
    }
    function toast(t) { $('pm-toast').textContent = t; setTimeout(function () { $('pm-toast').textContent = ''; }, 2500); }
    $('pm-export').onclick = function () {
      lastURL = snapshot($('pm-mode').value);
      var im = $('pm-prev'); im.src = lastURL; im.style.display = 'block'; $('pm-after').style.display = 'flex';
      if (!$('pm-prompt').value) buildPrompt();
    };
    $('pm-dl').onclick = function () { var a = document.createElement('a'); a.href = lastURL; a.download = 'pose.png'; document.body.appendChild(a); a.click(); a.remove(); };
    $('pm-copyimg').onclick = function () {
      fetch(lastURL).then(function (r) { return r.blob(); }).then(function (b) { return navigator.clipboard.write([new ClipboardItem({ 'image/png': b })]); })
        .then(function () { toast('تم نسخ الصورة ✓'); }, function () { toast('المتصفح منع النسخ، استخدم التحميل'); });
    };
    function buildPrompt() {
      var d = $('pm-desc').value.trim() || 'a person';
      $('pm-prompt').value = d + '. Full-body shot, the subject strictly follows the pose in the attached reference pose image (match arms, legs, torso and head orientation exactly), ' + $('pm-style').value + ', natural proportions, high detail.';
    }
    $('pm-mkprompt').onclick = buildPrompt;
    $('pm-copyprompt').onclick = function () {
      if (!$('pm-prompt').value) buildPrompt();
      var t = $('pm-prompt'); t.select();
      (navigator.clipboard ? navigator.clipboard.writeText(t.value) : Promise.reject()).then(function () { toast('تم نسخ البرومبت ✓'); }, function () { document.execCommand('copy'); toast('تم النسخ ✓'); });
    };

    /* ---------- loop ---------- */
    function loop() { requestAnimationFrame(loop); if (!dirty) return; dirty = false; renderer.render(scene, camera); }
    placeCamera(); setPose('واقف'); resize(); loop();
    window.PoseMannequin = { setPose: setPose, snapshot: snapshot, state: S };
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
