/* ComputeSight — site interactions + live vision simulation */
(() => {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const pad = (n, l = 3) => String(n).padStart(l, '0');
  const TAU = Math.PI * 2;
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const CFG = window.CS_CONFIG || {};

  /* ---------------- basic page chrome ---------------- */
  $('#year').textContent = new Date().getFullYear();

  const nav = $('#nav');
  const onScroll = () => nav.classList.toggle('scrolled', scrollY > 20);
  addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  const navToggle = $('#navToggle');
  const navLinks = $('#navLinks');
  navToggle.addEventListener('click', () => {
    const open = navLinks.classList.toggle('open');
    navToggle.setAttribute('aria-expanded', open);
  });
  navLinks.addEventListener('click', (e) => {
    if (e.target.closest('a')) {
      navLinks.classList.remove('open');
      navToggle.setAttribute('aria-expanded', 'false');
    }
  });

  // spotlight on cards
  $$('.card').forEach((c) => c.addEventListener('pointermove', (e) => {
    const r = c.getBoundingClientRect();
    c.style.setProperty('--mx', `${e.clientX - r.left}px`);
    c.style.setProperty('--my', `${e.clientY - r.top}px`);
  }));

  // reveal on scroll
  const revealIO = new IntersectionObserver((entries) => entries.forEach((en) => {
    if (en.isIntersecting) { en.target.classList.add('in'); revealIO.unobserve(en.target); }
  }), { threshold: 0.12 });
  $$('[data-reveal]').forEach((el, i) => { el.style.transitionDelay = `${(i % 4) * 70}ms`; revealIO.observe(el); });

  // counters
  const runCount = (el) => {
    const end = parseFloat(el.dataset.count);
    const dec = +el.dataset.decimals || 0;
    const suf = el.dataset.suffix || '';
    if (reduceMotion) { el.textContent = end.toFixed(dec) + suf; return; }
    const t0 = performance.now(), dur = 1600;
    const step = (now) => {
      const p = Math.min(1, (now - t0) / dur);
      el.textContent = (end * (1 - Math.pow(1 - p, 3))).toFixed(dec) + suf;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const countIO = new IntersectionObserver((entries) => entries.forEach((en) => {
    if (en.isIntersecting) { runCount(en.target); countIO.unobserve(en.target); }
  }), { threshold: 0.5 });
  $$('[data-count]').forEach((el) => countIO.observe(el));

  /* ---------------- shared drawing helpers ---------------- */
  const HEAT_STOPS = [
    [0, [0, 0, 0, 0]], [0.18, [47, 91, 234, 90]], [0.42, [122, 162, 255, 160]],
    [0.68, [45, 212, 191, 200]], [1, [248, 113, 113, 235]],
  ];
  function heatColor(v) {
    v = clamp(v, 0, 1);
    for (let i = 1; i < HEAT_STOPS.length; i++) {
      const [p1, c1] = HEAT_STOPS[i];
      if (v <= p1) {
        const [p0, c0] = HEAT_STOPS[i - 1];
        const t = (v - p0) / (p1 - p0);
        return c0.map((c, k) => c + (c1[k] - c) * t);
      }
    }
    return HEAT_STOPS[HEAT_STOPS.length - 1][1];
  }

  function drawPitch(ctx, x, y, w, h, alpha = 0.5) {
    const n = 12;
    for (let i = 0; i < n; i++) {
      ctx.fillStyle = i % 2 ? '#0c2619' : '#0f2e1f';
      ctx.fillRect(x + (i * w) / n, y, w / n + 1, h);
    }
    const mx = (m) => x + (m / 105) * w;
    const my = (m) => y + (m / 68) * h;
    const sx = (m) => (m / 105) * w;
    const sy = (m) => (m / 68) * h;
    ctx.strokeStyle = `rgba(232,238,252,${alpha})`;
    ctx.lineWidth = 1.2;
    ctx.strokeRect(x, y, w, h);
    ctx.beginPath(); ctx.moveTo(mx(52.5), y); ctx.lineTo(mx(52.5), y + h); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(mx(52.5), my(34), sx(9.15), sy(9.15), 0, 0, TAU); ctx.stroke();
    ctx.strokeRect(x, my(13.85), sx(16.5), sy(40.3));
    ctx.strokeRect(mx(88.5), my(13.85), sx(16.5), sy(40.3));
    ctx.strokeRect(x, my(24.84), sx(5.5), sy(18.32));
    ctx.strokeRect(mx(99.5), my(24.84), sx(5.5), sy(18.32));
    ctx.strokeRect(x - sx(1.8), my(30.34), sx(1.8), sy(7.32));
    ctx.strokeRect(mx(105), my(30.34), sx(1.8), sy(7.32));
    ctx.fillStyle = `rgba(232,238,252,${alpha})`;
    [[52.5, 34], [11, 34], [94, 34]].forEach(([a, b]) => { ctx.beginPath(); ctx.arc(mx(a), my(b), 2, 0, TAU); ctx.fill(); });
  }

  /* ================================================================
     LIVE VISION LAB — simulated detection + tracking engine
     ================================================================ */
  function initFeed() {
    const canvas = $('#feed');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const wrap = canvas.parentElement;
    const tip = $('#feedTip');
    const statsEl = $('#sideStats');
    const logEl = $('#eventLog');
    const opts = { boxes: true, trails: true, heat: false, conf: 0.5 };

    const env = { ctx, W: 0, H: 0, S: 1, FS: 10, t: 0, silent: false, log };
    const HW = 80, HH = 45;
    const heat = new Float32Array(HW * HH);
    const hc = document.createElement('canvas');
    hc.width = HW; hc.height = HH;
    const hctx = hc.getContext('2d');
    const himg = hctx.createImageData(HW, HH);

    function resize() {
      const r = wrap.getBoundingClientRect();
      const dpr = Math.min(2, devicePixelRatio || 1);
      env.W = r.width; env.H = r.height;
      canvas.width = Math.round(r.width * dpr);
      canvas.height = Math.round(r.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      env.S = Math.max(0.45, Math.min(r.width / 1000, r.height / 562));
      env.FS = Math.round(clamp(r.width / 95, 9, 11));
      if (!running) draw();
    }

    function log(cls, label, text) {
      if (env.silent) return;
      const li = document.createElement('li');
      li.className = cls;
      li.innerHTML = `<time>${new Date().toTimeString().slice(0, 8)}</time><span><b>${label}</b> ${text}</span>`;
      logEl.prepend(li);
      while (logEl.children.length > 16) logEl.lastChild.remove();
    }

    function renderStats() {
      const s = scene.stats();
      if (statsEl.dataset.mode !== scene.name) {
        statsEl.innerHTML = s.map((x) => `<div class="stat"><span>${x.k}</span><strong></strong></div>`).join('');
        statsEl.dataset.mode = scene.name;
      }
      s.forEach((x, i) => {
        const el = statsEl.children[i];
        el.className = `stat ${x.cls || ''}`;
        el.lastChild.textContent = x.v;
      });
    }

    function drawBox(b, color, text, hot) {
      const { x, y, w, h } = b;
      ctx.save();
      ctx.fillStyle = color;
      ctx.globalAlpha = hot ? 0.16 : 0.06;
      ctx.fillRect(x, y, w, h);
      ctx.globalAlpha = 0.45;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.strokeRect(x + 0.5, y + 0.5, w, h);
      ctx.globalAlpha = 1;
      ctx.lineWidth = hot ? 3 : 2;
      const c = Math.max(5, Math.min(w, h) * 0.28);
      ctx.beginPath();
      ctx.moveTo(x, y + c); ctx.lineTo(x, y); ctx.lineTo(x + c, y);
      ctx.moveTo(x + w - c, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + c);
      ctx.moveTo(x + w, y + h - c); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w - c, y + h);
      ctx.moveTo(x + c, y + h); ctx.lineTo(x, y + h); ctx.lineTo(x, y + h - c);
      ctx.stroke();
      if (text) {
        const fs = env.FS;
        ctx.font = `500 ${fs}px "JetBrains Mono", monospace`;
        const tw = ctx.measureText(text).width + 8;
        const th = fs + 6;
        let ty = y - th - 2;
        if (ty < 2) ty = y + h + 2;
        const tx = clamp(x - 1, 2, env.W - tw - 2);
        ctx.fillStyle = color;
        ctx.fillRect(tx, ty, tw, th);
        ctx.fillStyle = '#0b1220';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, tx + 4, ty + th / 2 + 0.5);
      }
      ctx.restore();
    }

    function drawTrail(o, color) {
      const tr = o.trail;
      if (tr.length < 2) return;
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineCap = 'round';
      for (let i = 1; i < tr.length; i++) {
        ctx.globalAlpha = (i / tr.length) * 0.6;
        ctx.beginPath();
        ctx.moveTo(tr[i - 1][0] * env.W, tr[i - 1][1] * env.H);
        ctx.lineTo(tr[i][0] * env.W, tr[i][1] * env.H);
        ctx.stroke();
      }
      ctx.restore();
    }

    function addHeat(x, y) {
      const gx = Math.floor(x * HW), gy = Math.floor(y * HH);
      for (let j = -1; j <= 1; j++) {
        for (let i = -1; i <= 1; i++) {
          const X = gx + i, Y = gy + j;
          if (X < 0 || Y < 0 || X >= HW || Y >= HH) continue;
          heat[Y * HW + X] += (i === 0 && j === 0) ? 0.03 : 0.012;
        }
      }
    }

    function drawHeat() {
      const d = himg.data;
      for (let i = 0; i < heat.length; i++) {
        const c = heatColor(Math.min(1, heat[i]));
        d[i * 4] = c[0]; d[i * 4 + 1] = c[1]; d[i * 4 + 2] = c[2]; d[i * 4 + 3] = c[3];
      }
      hctx.putImageData(himg, 0, 0);
      ctx.save();
      ctx.imageSmoothingEnabled = true;
      ctx.globalAlpha = 0.75;
      ctx.drawImage(hc, 0, 0, env.W, env.H);
      ctx.restore();
    }

    function drawOverlay() {
      const { W, H, t } = env;
      // scanline
      const sy = ((t * 0.12) % 1) * H;
      const g = ctx.createLinearGradient(0, sy - 40, 0, sy);
      g.addColorStop(0, 'rgba(122,162,255,0)');
      g.addColorStop(1, 'rgba(122,162,255,0.08)');
      ctx.fillStyle = g;
      ctx.fillRect(0, sy - 40, W, 40);
      // vignette
      const v = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.35, W / 2, H / 2, Math.max(W, H) * 0.75);
      v.addColorStop(0, 'rgba(0,0,0,0)');
      v.addColorStop(1, 'rgba(0,0,0,0.55)');
      ctx.fillStyle = v;
      ctx.fillRect(0, 0, W, H);
    }

    let mouse = null, hovered = null;
    function draw() {
      if (!scene || !env.W) return;
      ctx.clearRect(0, 0, env.W, env.H);
      scene.drawBg();
      if (opts.heat) drawHeat();
      const objs = scene.objects();

      hovered = null;
      if (mouse) {
        for (let i = objs.length - 1; i >= 0; i--) {
          const b = scene.bbox(objs[i]);
          if (mouse.x >= b.x && mouse.x <= b.x + b.w && mouse.y >= b.y && mouse.y <= b.y + b.h) { hovered = objs[i]; break; }
        }
      }

      if (opts.trails) objs.forEach((o) => { if (o.conf >= opts.conf) drawTrail(o, scene.style(o).color); });
      objs.forEach((o) => scene.drawObj(o));
      if (opts.boxes) {
        objs.forEach((o) => {
          if (o.conf < opts.conf && o !== hovered) return;
          const st = scene.style(o);
          drawBox(scene.bbox(o), st.color, st.label, o === hovered);
        });
      }
      drawOverlay();
      updateTip();
    }

    function updateTip() {
      if (!hovered || !mouse) { tip.hidden = true; canvas.style.cursor = 'crosshair'; return; }
      canvas.style.cursor = 'pointer';
      const rows = scene.info(hovered);
      tip.innerHTML = `<b>${rows[0][1]}</b>` + rows.slice(1).map(([k, v]) => `<br>${k}: ${v}`).join('');
      tip.hidden = false;
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      let x = mouse.x + 16, y = mouse.y + 16;
      if (x + tw > env.W - 6) x = mouse.x - tw - 16;
      if (y + th > env.H - 6) y = mouse.y - th - 16;
      tip.style.left = `${Math.max(6, x)}px`;
      tip.style.top = `${Math.max(6, y)}px`;
    }

    canvas.addEventListener('pointermove', (e) => {
      const r = canvas.getBoundingClientRect();
      mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
    });
    canvas.addEventListener('pointerleave', () => { mouse = null; tip.hidden = true; });

    /* ---------- scene: retail / loss prevention ---------- */
    function makeRetail() {
      const shelves = [
        { x: 0.05, y: 0.17, w: 0.54, h: 0.07 },
        { x: 0.05, y: 0.43, w: 0.54, h: 0.07 },
        { x: 0.05, y: 0.69, w: 0.54, h: 0.07 },
      ];
      const aisles = [0.09, 0.335, 0.595, 0.87];
      const counters = [{ x: 0.74, y: 0.2, w: 0.13, h: 0.05 }, { x: 0.74, y: 0.48, w: 0.13, h: 0.05 }];
      const laneY = [0.29, 0.6];
      const corridor = 0.655;
      const shirts = ['#3d7bff', '#ff8a3d', '#7d8aa8', '#e8eefc', '#9b7bff', '#3dd6a0', '#c74d6b', '#d9b45a'];
      const prodColors = ['#3d7bff', '#ff8a3d', '#ffd23d', '#3dffb0', '#ff4d8d', '#9b7bff', '#e8eefc'];
      const products = shelves.map((s) => Array.from({ length: 26 }, (_, i) => ({
        x: s.x + 0.006 + (i % 13) * (s.w / 13), y: s.y + 0.008 + Math.floor(i / 13) * (s.h / 2),
        w: s.w / 13 - 0.008, h: s.h / 2 - 0.014, c: pick(prodColors),
      })));

      let people = [];
      let nextId = 1, spawnT = 0, alerts = 0, paid = 0;

      function route(p) {
        const pts = [{ x: 0.92, y: 0.9 }, { x: corridor, y: 0.87 }];
        const n = 1 + Math.floor(Math.random() * 3);
        for (let i = 0; i < n; i++) {
          const ai = Math.floor(Math.random() * aisles.length);
          const ay = aisles[ai];
          pts.push({ x: corridor, y: ay }, { x: rand(0.1, 0.55), y: ay, dwell: rand(0.6, 2.6), shelf: true, aisle: ai + 1 }, { x: corridor, y: ay });
        }
        if (p.susp) {
          const first = pts.find((w) => w.shelf);
          first.dwell = 3.2; first.conceal = true;
          pts.push({ x: corridor, y: 0.87 }, { x: 0.92, y: 0.93 }, { x: 1.04, y: 0.94, exit: true });
        } else {
          const lane = Math.random() < 0.5 ? 0 : 1;
          const ly = laneY[lane];
          pts.push({ x: corridor, y: ly }, { x: 0.8, y: ly, pay: lane + 1, dwell: rand(1.6, 3) }, { x: 0.93, y: ly }, { x: 0.93, y: 0.9 }, { x: 1.04, y: 0.94, exit: true });
        }
        return pts;
      }

      function spawn() {
        const p = {
          id: nextId++, trail: [], susp: Math.random() < 0.22, flagged: false,
          base: Math.random() < 0.15 ? rand(0.42, 0.62) : rand(0.82, 0.98), conf: 0.9,
          speed: rand(0.07, 0.11), heading: Math.PI, wi: 0, wait: 0, cur: null,
          state: 'entering', age: 0, shirt: pick(shirts), items: 0, x: 1.03, y: 0.9,
        };
        p.path = route(p);
        people.push(p);
        if (Math.random() < 0.5) log('info', 'ENTER', `P-${pad(p.id)} · main door`);
      }

      function finishWait(p) {
        const wp = p.cur;
        if (wp.conceal) {
          p.flagged = true; p.state = 'concealment';
          alerts++;
          log('bad', 'ALERT', `P-${pad(p.id)} concealment · aisle ${wp.aisle} · ${rand(0.86, 0.97).toFixed(2)}`);
        } else if (wp.pay) {
          paid++; p.state = 'exiting';
          log('ok', 'PAID', `P-${pad(p.id)} · lane ${wp.pay} · ${p.items} items matched POS`);
        } else if (wp.shelf) {
          p.items += 1 + Math.floor(Math.random() * 3);
          if (wp.dwell > 2.3) log('warn', 'DWELL', `P-${pad(p.id)} ${Math.round(wp.dwell * 20)}s · aisle ${wp.aisle}`);
          if (!p.flagged) p.state = 'browsing';
        }
        p.cur = null;
        p.wi++;
      }

      return {
        name: 'retail', cam: 'STORE FLOOR', model: 'cs-retail-v5',
        objects: () => people,
        update(dt) {
          spawnT -= dt;
          if (spawnT <= 0 && people.length < 13) { spawn(); spawnT = rand(1.1, 2.4); }
          for (const p of people) {
            p.age += dt;
            const near = shelves.some((s) => Math.abs(p.y - (s.y + s.h / 2)) < 0.1 && p.x < 0.6);
            p.conf = clamp(p.base - (near ? 0.04 : 0) + Math.sin(env.t * 3 + p.id) * 0.03, 0.3, 0.99);
            if (p.wait > 0) { p.wait -= dt; if (p.wait <= 0) finishWait(p); continue; }
            const wp = p.path[p.wi];
            if (!wp) { p.dead = true; continue; }
            const dx = (wp.x - p.x) * env.W, dy = (wp.y - p.y) * env.H;
            const d = Math.hypot(dx, dy);
            if (d < 1.5) {
              p.x = wp.x; p.y = wp.y;
              if (wp.exit) {
                p.dead = true;
                if (p.flagged) log('bad', 'EXIT', `P-${pad(p.id)} left without paying · clip sent`);
              } else if (wp.dwell) {
                p.wait = wp.dwell; p.cur = wp;
                if (wp.pay) p.state = 'paying';
              } else p.wi++;
            } else {
              const step = Math.min(1, (p.speed * env.W * dt) / d);
              p.x += (wp.x - p.x) * step;
              p.y += (wp.y - p.y) * step;
              p.heading = Math.atan2(dy, dx);
              if (p.state === 'entering' && p.wi > 1) p.state = 'browsing';
            }
          }
          people = people.filter((p) => !p.dead);
        },
        style(p) {
          const c = p.conf.toFixed(2);
          if (p.flagged) return { color: '#f87171', label: `ALERT P-${pad(p.id)} ${c}` };
          if (p.state === 'paying') return { color: '#2dd4bf', label: `paying ${c}` };
          if (p.wait > 0) return { color: '#fbbf24', label: `person ${c}` };
          return { color: '#7aa2ff', label: `person ${c}` };
        },
        bbox(p) {
          const r = 11 * env.S;
          return { x: p.x * env.W - r * 1.3, y: p.y * env.H - r * 1.3, w: r * 2.6, h: r * 2.6 };
        },
        info(p) {
          const s = Math.round(p.age * 20);
          return [
            ['t', `P-${pad(p.id)} · person`], ['confidence', p.conf.toFixed(3)], ['state', p.state],
            ['time in store', `${Math.floor(s / 60)}m ${pad(s % 60, 2)}s`], ['basket est.', `${p.items} items`],
            ['risk score', p.flagged ? '0.93 ▲' : (0.05 + (p.id % 7) * 0.02).toFixed(2)],
          ];
        },
        drawObj(p) {
          const r = 11 * env.S;
          ctx.save();
          ctx.translate(p.x * env.W, p.y * env.H);
          ctx.rotate(p.heading);
          ctx.fillStyle = 'rgba(0,0,0,.4)';
          ctx.beginPath(); ctx.ellipse(2, 3, r * 0.7, r * 1.05, 0, 0, TAU); ctx.fill();
          ctx.fillStyle = p.shirt;
          ctx.beginPath(); ctx.ellipse(0, 0, r * 0.5, r, 0, 0, TAU); ctx.fill();
          ctx.fillStyle = '#1b2232';
          ctx.strokeStyle = 'rgba(255,255,255,.3)';
          ctx.beginPath(); ctx.arc(r * 0.08, 0, r * 0.45, 0, TAU); ctx.fill(); ctx.stroke();
          ctx.restore();
        },
        drawBg() {
          const { W, H, S } = env;
          ctx.fillStyle = '#0d1526';
          ctx.fillRect(0, 0, W, H);
          ctx.strokeStyle = 'rgba(255,255,255,.03)';
          ctx.lineWidth = 1;
          const step = 40 * S;
          ctx.beginPath();
          for (let x = 0; x < W; x += step) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
          for (let y = 0; y < H; y += step) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
          ctx.stroke();
          ctx.font = `${env.FS - 1}px "JetBrains Mono", monospace`;
          ctx.textBaseline = 'alphabetic';
          shelves.forEach((s, i) => {
            ctx.fillStyle = '#141c2c';
            ctx.fillRect(s.x * W, s.y * H, s.w * W, s.h * H);
            ctx.strokeStyle = '#26324a';
            ctx.strokeRect(s.x * W + 0.5, s.y * H + 0.5, s.w * W, s.h * H);
            ctx.globalAlpha = 0.6;
            products[i].forEach((pr) => { ctx.fillStyle = pr.c; ctx.fillRect(pr.x * W, pr.y * H, pr.w * W, pr.h * H); });
            ctx.globalAlpha = 1;
            ctx.fillStyle = 'rgba(138,150,179,.55)';
            ctx.fillText(`AISLE ${i + 1}`, s.x * W, s.y * H - 5);
          });
          // checkout zone
          ctx.save();
          ctx.setLineDash([5, 5]);
          ctx.strokeStyle = 'rgba(45,212,191,.35)';
          ctx.strokeRect(0.71 * W, 0.12 * H, 0.2 * W, 0.56 * H);
          ctx.restore();
          ctx.fillStyle = 'rgba(45,212,191,.6)';
          ctx.fillText('CHECKOUT ZONE', 0.71 * W + 6, 0.12 * H + env.FS + 3);
          counters.forEach((c, i) => {
            ctx.fillStyle = '#1a2338';
            ctx.fillRect(c.x * W, c.y * H, c.w * W, c.h * H);
            ctx.strokeStyle = 'rgba(45,212,191,.45)';
            ctx.strokeRect(c.x * W + 0.5, c.y * H + 0.5, c.w * W, c.h * H);
            ctx.fillStyle = '#2b3550';
            ctx.beginPath(); ctx.arc((c.x + c.w * 0.6) * W, (c.y - 0.03) * H, 8 * S, 0, TAU); ctx.fill();
            ctx.fillStyle = 'rgba(138,150,179,.7)';
            ctx.fillText(`LANE ${i + 1}`, c.x * W + 4, (c.y + c.h) * H + env.FS + 2);
          });
          // door
          ctx.strokeStyle = 'rgba(122,162,255,.5)';
          ctx.lineWidth = 3;
          ctx.beginPath(); ctx.moveTo(W - 2, 0.82 * H); ctx.lineTo(W - 2, 0.99 * H); ctx.stroke();
          ctx.lineWidth = 1;
          ctx.fillStyle = 'rgba(122,162,255,.6)';
          ctx.textAlign = 'right';
          ctx.fillText('ENTRY / EXIT', W - 10, 0.8 * H);
          ctx.textAlign = 'left';
        },
        stats() {
          const inStore = people.filter((p) => p.x < 1).length;
          const avg = people.length ? (people.reduce((a, p) => a + p.age, 0) / people.length) * 20 : 0;
          return [
            { k: 'In store', v: inStore },
            { k: 'Avg dwell', v: `${Math.floor(avg / 60)}m ${pad(Math.round(avg % 60), 2)}s` },
            { k: 'Alerts', v: alerts, cls: alerts ? 'alert' : '' },
            { k: 'Checkouts', v: paid, cls: 'good' },
          ];
        },
      };
    }

    /* ---------- scene: sports tracking ---------- */
    function makeSports() {
      const F = { x0: 0.05, y0: 0.08, x1: 0.95, y1: 0.92 };
      const form = [[0.05, 0.5], [0.22, 0.22], [0.2, 0.5], [0.22, 0.78], [0.4, 0.3], [0.38, 0.7], [0.48, 0.5], [0.62, 0.35], [0.62, 0.65]];
      const roles = ['GK', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'FWD', 'FWD'];
      const nums = [[1, 4, 5, 3, 8, 6, 10, 9, 11], [1, 2, 4, 5, 6, 8, 10, 7, 9]];
      const teamName = ['Home', 'Away'];
      const players = [];
      [0, 1].forEach((team) => form.forEach(([fx, fy], i) => {
        const bx = team ? 1 - fx : fx;
        players.push({
          kind: 'player', team, num: nums[team][i], role: roles[i], gk: i === 0, base: [bx, fy],
          fx: bx + rand(-0.02, 0.02), fy: fy + rand(-0.02, 0.02), vx: 0, vy: 0, kmh: 0, top: 0, dist: 0,
          seed: Math.random() * 10, trail: [], conf: 0.95, x: 0, y: 0, sprintCd: 0,
        });
      }));
      const ball = { kind: 'ball', fx: 0.5, fy: 0.5, owner: players[6], receiver: null, tx: 0, ty: 0, spd: 0.5, passT: 1.5, shot: false, trail: [], conf: 0.85, x: 0, y: 0, from: null };
      const poss = [1, 1];
      let passes = 0, topSpeed = 0;
      const score = [0, 0];

      const toN = (o) => { o.x = F.x0 + o.fx * (F.x1 - F.x0); o.y = F.y0 + o.fy * (F.y1 - F.y0); };
      const meters = (ax, ay, bx, by) => Math.hypot((ax - bx) * 105, (ay - by) * 68);
      const label = (p) => `#${p.num} (${teamName[p.team]})`;

      function pass(o) {
        const dir = o.team === 0 ? 1 : -1;
        const mates = players.filter((p) => p.team === o.team && p !== o && !p.gk);
        let best = mates[0], bs = -Infinity;
        mates.forEach((m) => {
          const d = meters(o.fx, o.fy, m.fx, m.fy);
          const s = dir * (m.fx - o.fx) * 2 + rand(0, 0.8) - (d > 40 ? 1 : 0);
          if (s > bs) { bs = s; best = m; }
        });
        let recv = best;
        if (Math.random() < 0.15) {
          const midx = (o.fx + best.fx) / 2, midy = (o.fy + best.fy) / 2;
          recv = players.filter((p) => p.team !== o.team && !p.gk)
            .sort((a, b) => Math.hypot(a.fx - midx, a.fy - midy) - Math.hypot(b.fx - midx, b.fy - midy))[0];
        }
        ball.from = o; ball.receiver = recv; ball.owner = null; ball.shot = false; ball.spd = 0.5;
        ball.tx = recv.fx + recv.vx * 0.4; ball.ty = recv.fy + recv.vy * 0.4;
      }

      function shoot(o) {
        ball.from = o; ball.owner = null; ball.receiver = null; ball.shot = true; ball.spd = 0.85;
        ball.tx = o.team === 0 ? 1 : 0; ball.ty = 0.5 + rand(-0.07, 0.07);
        log('warn', 'SHOT', `${label(o)} · xG ${rand(0.05, 0.42).toFixed(2)}`);
      }

      function receive(p) {
        ball.owner = p; ball.receiver = null; ball.passT = rand(1.1, 2.6);
        const f = ball.from;
        if (f && f.team === p.team) { passes++; log('info', 'PASS', `#${f.num} → #${p.num} · ${Math.round(meters(f.fx, f.fy, p.fx, p.fy))}m`); }
        else if (f) log('warn', 'TURNOVER', `${label(p)} intercepts`);
      }

      return {
        name: 'sports', cam: 'TACTICAL WIDE', model: 'cs-track-v3',
        objects: () => [...players, ball],
        update(dt) {
          if (ball.owner) {
            const o = ball.owner;
            poss[o.team] += dt;
            const dir = o.team === 0 ? 1 : -1;
            ball.fx = o.fx + dir * 0.012; ball.fy = o.fy;
            ball.passT -= dt;
            if (ball.passT <= 0) {
              const ax = o.team === 0 ? o.fx : 1 - o.fx;
              if (ax > 0.7 && Math.random() < 0.55) shoot(o); else pass(o);
            }
          } else {
            const dx = ball.tx - ball.fx, dy = ball.ty - ball.fy;
            const d = Math.hypot(dx, dy), step = ball.spd * dt;
            if (ball.receiver && Math.hypot(ball.receiver.fx - ball.fx, ball.receiver.fy - ball.fy) < 0.02) receive(ball.receiver);
            else if (d <= step) {
              ball.fx = ball.tx; ball.fy = ball.ty;
              if (ball.shot) {
                const atk = ball.from.team, def = 1 - atk;
                if (Math.random() < 0.2) {
                  score[atk]++;
                  log('ok', 'GOAL', `${label(ball.from)} scores · ${score[0]}–${score[1]}`);
                  ball.from = null;
                  const kicker = players.find((p) => p.team === def && p.role === 'MID' && p.num === 10);
                  kicker.fx = 0.5; kicker.fy = 0.5; receive(kicker);
                } else {
                  const gk = players.find((p) => p.team === def && p.gk);
                  log('info', 'SAVE', `GK ${label(gk)}`);
                  ball.from = null; receive(gk);
                }
              } else receive(ball.receiver);
            } else { ball.fx += (dx / d) * step; ball.fy += (dy / d) * step; }
          }
          ball.conf = ball.owner ? clamp(0.82 + Math.sin(env.t * 5) * 0.08, 0, 1) : clamp(0.62 + Math.sin(env.t * 9) * 0.1, 0, 1);

          // chasers: closest outfield player of the team without the ball
          const holderTeam = ball.owner ? ball.owner.team : (ball.from ? ball.from.team : 0);
          const chaser = players.filter((p) => p.team !== holderTeam && !p.gk)
            .sort((a, b) => Math.hypot(a.fx - ball.fx, a.fy - ball.fy) - Math.hypot(b.fx - ball.fx, b.fy - ball.fy))[0];

          for (const p of players) {
            const dir = p.team === 0 ? 1 : -1;
            let tx = p.base[0] + (ball.fx - 0.5) * 0.45 + (holderTeam === p.team ? dir * 0.06 : -dir * 0.03);
            let ty = p.base[1] + (ball.fy - 0.5) * 0.3;
            let max = 0.035;
            if (p.gk) { tx = p.base[0] + (ball.fx - 0.5) * 0.05; ty = 0.5 + (ball.fy - 0.5) * 0.25; }
            if (p === chaser || p === ball.receiver) { tx = ball.fx; ty = ball.fy; max = 0.075; }
            if (p === ball.owner) { tx = p.fx + dir * 0.1; ty = p.fy + (0.5 - p.fy) * 0.15; max = 0.05; }
            tx += Math.sin(env.t * 0.7 + p.seed) * 0.02;
            ty += Math.cos(env.t * 0.6 + p.seed) * 0.02;
            let dvx = (tx - p.fx) * 1.5, dvy = (ty - p.fy) * 1.5;
            const m = Math.hypot(dvx, dvy);
            if (m > max) { dvx = (dvx / m) * max; dvy = (dvy / m) * max; }
            p.vx += (dvx - p.vx) * Math.min(1, dt * 3);
            p.vy += (dvy - p.vy) * Math.min(1, dt * 3);
            p.fx = clamp(p.fx + p.vx * dt, 0.01, 0.99);
            p.fy = clamp(p.fy + p.vy * dt, 0.02, 0.98);
            const ms = Math.hypot(p.vx * 105, p.vy * 68);
            p.dist += ms * dt;
            p.kmh += (ms * 3.6 - p.kmh) * Math.min(1, dt * 4);
            p.top = Math.max(p.top, p.kmh);
            topSpeed = Math.max(topSpeed, p.kmh);
            p.sprintCd -= dt;
            if (p.kmh > 25.5 && p.sprintCd <= 0) { log('ok', 'SPRINT', `${label(p)} ${p.kmh.toFixed(1)} km/h`); p.sprintCd = 12; }
            p.conf = clamp(0.9 + Math.sin(env.t * 2 + p.seed) * 0.07, 0, 0.99);
            toN(p);
          }
          toN(ball);
        },
        style(o) {
          if (o.kind === 'ball') return { color: '#2dd4bf', label: `ball ${o.conf.toFixed(2)}` };
          return { color: o.team === 0 ? '#7aa2ff' : '#fbbf24', label: `#${o.num} ${o.kmh.toFixed(1)} km/h` };
        },
        bbox(o) {
          const r = o.kind === 'ball' ? 4 * env.S + 1 : 7.5 * env.S + 1.5;
          const k = o.kind === 'ball' ? 2.4 : 1.7;
          return { x: o.x * env.W - r * k, y: o.y * env.H - r * k, w: r * k * 2, h: r * k * 2 };
        },
        info(o) {
          if (o.kind === 'ball') {
            return [['t', 'Ball'], ['confidence', o.conf.toFixed(3)], ['state', o.owner ? `with #${o.owner.num}` : (o.shot ? 'shot' : 'in flight')], ['position', `${(o.fx * 105).toFixed(1)}m, ${(o.fy * 68).toFixed(1)}m`]];
          }
          return [
            ['t', `#${o.num} · ${teamName[o.team]} · ${o.role}`], ['speed', `${o.kmh.toFixed(1)} km/h`],
            ['top speed', `${o.top.toFixed(1)} km/h`], ['distance', `${Math.round(o.dist)} m`],
            ['confidence', o.conf.toFixed(3)], ['position', `${(o.fx * 105).toFixed(1)}m, ${(o.fy * 68).toFixed(1)}m`],
          ];
        },
        drawObj(o) {
          const x = o.x * env.W, y = o.y * env.H;
          if (o.kind === 'ball') {
            const r = 4 * env.S + 1;
            ctx.fillStyle = 'rgba(0,0,0,.45)';
            ctx.beginPath(); ctx.arc(x + 2, y + 2, r, 0, TAU); ctx.fill();
            ctx.fillStyle = '#ffffff';
            ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
            return;
          }
          const r = 7.5 * env.S + 1.5;
          ctx.fillStyle = 'rgba(0,0,0,.4)';
          ctx.beginPath(); ctx.arc(x + 2, y + 3, r, 0, TAU); ctx.fill();
          ctx.fillStyle = o.gk ? (o.team ? '#d9b45a' : '#3dd6a0') : (o.team ? '#d8435f' : '#2f6bff');
          ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
          ctx.strokeStyle = 'rgba(255,255,255,.85)';
          ctx.lineWidth = 1.2;
          ctx.stroke();
          if (r > 7) {
            ctx.fillStyle = '#fff';
            ctx.font = `600 ${Math.round(r)}px "Space Grotesk", sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(o.num, x, y + 0.5);
            ctx.textAlign = 'left';
          }
        },
        drawBg() {
          const { W, H } = env;
          ctx.fillStyle = '#07130d';
          ctx.fillRect(0, 0, W, H);
          drawPitch(ctx, F.x0 * W, F.y0 * H, (F.x1 - F.x0) * W, (F.y1 - F.y0) * H, 0.45);
        },
        stats() {
          const pA = Math.round((poss[0] / (poss[0] + poss[1])) * 100);
          return [
            { k: 'Score', v: `${score[0]} – ${score[1]}` },
            { k: 'Possession', v: `${pA}% · ${100 - pA}%` },
            { k: 'Passes', v: passes, cls: 'good' },
            { k: 'Top speed', v: `${topSpeed.toFixed(1)}` },
          ];
        },
      };
    }

    /* ---------- scene: factory QC ---------- */
    function makeFactory() {
      const belts = [{ y: 0.33, h: 0.17, speed: 0.11, name: 'L1', pushT: -9 }, { y: 0.73, h: 0.17, speed: 0.09, name: 'L2', pushT: -9 }];
      const zone = { x0: 0.4, x1: 0.52 };
      const rejectX = 0.74;
      const defectsFor = { bottle: ['scratch', 'missing cap', 'label skew'], box: ['dent', 'crack', 'label skew'], can: ['dent', 'scratch'] };
      let items = [];
      let serial = 1000, inspected = 0, defects = 0;
      const spawnT = [0, 0.5];
      const passTimes = [];

      function spawn(bi) {
        const b = belts[bi];
        const type = pick(['bottle', 'box', 'can']);
        items.push({
          kind: 'item', id: `${b.name}-${serial++}`, belt: bi, type, x: -0.04, y: b.y + rand(-0.03, 0.03), size: rand(0.85, 1.1),
          rot: rand(0, TAU), defect: Math.random() < 0.13 ? pick(defectsFor[type]) : null, status: 'pending',
          conf: rand(0.7, 0.88), alpha: 1, rejecting: false, trail: [],
        });
      }

      return {
        name: 'factory', cam: 'LINE 1+2 GATE', model: 'cs-qc-v7',
        objects: () => items,
        update(dt) {
          belts.forEach((b, i) => { spawnT[i] -= dt; if (spawnT[i] <= 0) { spawn(i); spawnT[i] = rand(0.7, 1.3); } });
          for (const it of items) {
            const b = belts[it.belt];
            if (it.rejecting) {
              it.x += b.speed * dt * 0.3;
              it.y += 0.22 * dt;
              if (it.y > b.y + b.h / 2 + 0.06) it.alpha -= dt * 1.4;
              if (it.alpha <= 0) it.dead = true;
            } else it.x += b.speed * dt;
            if (it.status === 'pending' && it.x > (zone.x0 + zone.x1) / 2) {
              inspected++;
              passTimes.push(env.t);
              if (it.defect) {
                it.status = 'defect'; it.conf = rand(0.86, 0.97); defects++;
                log('bad', 'DEFECT', `#${it.id} ${it.defect} · ${it.conf.toFixed(2)} → reject`);
              } else {
                it.status = 'ok'; it.conf = rand(0.95, 0.995);
                if (inspected % 6 === 0) log('ok', 'PASS', `#${it.id} ${it.type} · ${it.conf.toFixed(2)}`);
              }
            }
            if (it.status === 'defect' && !it.rejecting && it.x >= rejectX) { it.rejecting = true; b.pushT = env.t; }
            if (it.x > 1.06) it.dead = true;
            if (it.status === 'pending') it.conf = clamp(it.conf + (Math.random() - 0.5) * 0.02, 0.55, 0.92);
          }
          items = items.filter((i) => !i.dead);
          while (passTimes.length && env.t - passTimes[0] > 15) passTimes.shift();
          if (Math.random() < dt * 0.02) log('warn', 'DRIFT', `Belt ${pick(['L1', 'L2'])} speed ${pick(['+', '−'])}${(rand(1, 4)).toFixed(1)}% · auto-calibrated`);
        },
        style(it) {
          const c = it.conf.toFixed(2);
          if (it.status === 'ok') return { color: '#2dd4bf', label: `OK ${c}` };
          if (it.status === 'defect') return { color: '#f87171', label: `DEFECT·${it.defect} ${c}` };
          return { color: '#7aa2ff', label: `${it.type} ${c}` };
        },
        bbox(it) {
          const s = 22 * env.S * it.size;
          return { x: it.x * env.W - s * 0.75, y: it.y * env.H - s * 0.75, w: s * 1.5, h: s * 1.5 };
        },
        info(it) {
          return [
            ['t', `#${it.id} · ${it.type}`], ['status', it.status], ['confidence', it.conf.toFixed(3)],
            ['defect', it.status === 'pending' ? 'awaiting gate' : (it.defect || 'none')],
            ['size', `${(62 * it.size).toFixed(1)} mm`], ['line', belts[it.belt].name],
          ];
        },
        drawObj(it) {
          const s = 22 * env.S * it.size;
          ctx.save();
          ctx.globalAlpha = Math.max(0, it.alpha);
          ctx.translate(it.x * env.W, it.y * env.H);
          ctx.rotate(it.rot);
          ctx.fillStyle = 'rgba(0,0,0,.45)';
          ctx.fillRect(-s / 2 + 3, -s / 2 + 3, s, s);
          if (it.type === 'box') {
            ctx.fillStyle = '#a7845a';
            ctx.fillRect(-s / 2, -s / 2, s, s);
            ctx.fillStyle = '#d6c08f';
            ctx.fillRect(-s / 2, -s * 0.08, s, s * 0.16);
          } else {
            ctx.fillStyle = it.type === 'bottle' ? '#2d8bb0' : '#9aa7c0';
            ctx.beginPath(); ctx.arc(0, 0, s / 2, 0, TAU); ctx.fill();
            ctx.strokeStyle = 'rgba(255,255,255,.35)';
            ctx.lineWidth = 1.5;
            ctx.beginPath(); ctx.arc(0, 0, s * 0.38, 0, TAU); ctx.stroke();
            if (it.type === 'bottle') {
              ctx.fillStyle = it.defect === 'missing cap' ? '#0b1220' : '#e8eefc';
              ctx.beginPath(); ctx.arc(0, 0, s * 0.18, 0, TAU); ctx.fill();
            }
          }
          if (it.defect) {
            ctx.strokeStyle = 'rgba(20,10,12,.85)';
            ctx.fillStyle = 'rgba(20,10,12,.55)';
            ctx.lineWidth = 1.6;
            if (it.defect === 'scratch') { ctx.beginPath(); ctx.moveTo(-s * 0.3, -s * 0.2); ctx.lineTo(s * 0.28, s * 0.15); ctx.stroke(); }
            if (it.defect === 'dent') { ctx.beginPath(); ctx.arc(s * 0.15, -s * 0.12, s * 0.16, 0, TAU); ctx.fill(); }
            if (it.defect === 'crack') { ctx.beginPath(); ctx.moveTo(-s * 0.4, -s * 0.3); ctx.lineTo(-s * 0.1, -s * 0.05); ctx.lineTo(-s * 0.2, s * 0.1); ctx.lineTo(s * 0.2, s * 0.35); ctx.stroke(); }
            if (it.defect === 'label skew') { ctx.save(); ctx.rotate(0.5); ctx.fillStyle = 'rgba(232,238,252,.8)'; ctx.fillRect(-s * 0.3, -s * 0.12, s * 0.6, s * 0.24); ctx.restore(); }
          }
          ctx.restore();
        },
        drawBg() {
          const { W, H, S, t } = env;
          ctx.fillStyle = '#0d1526';
          ctx.fillRect(0, 0, W, H);
          ctx.font = `${env.FS - 1}px "JetBrains Mono", monospace`;
          ctx.textBaseline = 'alphabetic';
          belts.forEach((b) => {
            const y0 = (b.y - b.h / 2) * H, bh = b.h * H;
            ctx.fillStyle = '#131a27';
            ctx.fillRect(0, y0, W, bh);
            ctx.strokeStyle = 'rgba(255,255,255,.05)';
            ctx.lineWidth = 1;
            const step = 22 * S;
            const off = (t * b.speed * W) % step;
            ctx.beginPath();
            for (let x = off - step; x < W; x += step) { ctx.moveTo(x, y0); ctx.lineTo(x, y0 + bh); }
            ctx.stroke();
            ctx.strokeStyle = '#2a3448';
            ctx.lineWidth = 2;
            ctx.beginPath(); ctx.moveTo(0, y0); ctx.lineTo(W, y0); ctx.moveTo(0, y0 + bh); ctx.lineTo(W, y0 + bh); ctx.stroke();
            ctx.fillStyle = 'rgba(138,150,179,.6)';
            ctx.fillText(`LINE ${b.name}`, 10, y0 - 6);
            // reject bin
            ctx.save();
            ctx.setLineDash([4, 4]);
            ctx.strokeStyle = 'rgba(248,113,113,.5)';
            ctx.lineWidth = 1;
            const bx = (rejectX - 0.05) * W, by = y0 + bh + 4;
            ctx.strokeRect(bx, by, 0.14 * W, 0.08 * H);
            ctx.restore();
            ctx.fillStyle = 'rgba(248,113,113,.7)';
            ctx.fillText('REJECT', bx + 6, by + 0.08 * H - 6);
            // pusher
            const pe = clamp(1 - Math.abs(t - b.pushT - 0.2) / 0.2, 0, 1);
            ctx.fillStyle = '#3a4560';
            ctx.fillRect((rejectX - 0.02) * W, y0 - 14 * S, 0.04 * W, 10 * S + pe * bh * 0.45);
            ctx.fillStyle = pe > 0 ? '#f87171' : '#55617d';
            ctx.fillRect((rejectX - 0.02) * W, y0 - 4 * S + pe * bh * 0.45, 0.04 * W, 4 * S);
          });
          // vision gate
          const gx = zone.x0 * W, gw = (zone.x1 - zone.x0) * W;
          ctx.fillStyle = 'rgba(122,162,255,.05)';
          ctx.fillRect(gx, 0.12 * H, gw, 0.82 * H);
          ctx.strokeStyle = 'rgba(122,162,255,.3)';
          ctx.lineWidth = 1;
          ctx.strokeRect(gx + 0.5, 0.12 * H + 0.5, gw, 0.82 * H);
          const beam = gx + (Math.sin(t * 3) * 0.5 + 0.5) * gw;
          ctx.save();
          ctx.shadowColor = '#7aa2ff';
          ctx.shadowBlur = 12;
          ctx.strokeStyle = 'rgba(122,162,255,.7)';
          ctx.lineWidth = 2;
          ctx.beginPath(); ctx.moveTo(beam, 0.12 * H); ctx.lineTo(beam, 0.94 * H); ctx.stroke();
          ctx.restore();
          ctx.fillStyle = 'rgba(122,162,255,.75)';
          ctx.fillText('VISION GATE', gx + 4, 0.12 * H - 6);
        },
        stats() {
          const rate = inspected ? ((1 - defects / inspected) * 100).toFixed(1) : '100.0';
          return [
            { k: 'Throughput /min', v: Math.round(passTimes.length * 4) },
            { k: 'Inspected', v: inspected },
            { k: 'Defects', v: defects, cls: defects ? 'alert' : '' },
            { k: 'Yield', v: `${rate}%`, cls: 'good' },
          ];
        },
      };
    }

    /* ---------- loop + controls ---------- */
    const makers = { retail: makeRetail, sports: makeSports, factory: makeFactory };
    let scene = null, running = false, last = 0, frameN = 0;
    let fpsAcc = 0, fpsN = 0, fpsT = 0, statT = 0;

    function setMode(mode) {
      scene = makers[mode]();
      heat.fill(0);
      logEl.innerHTML = '';
      statsEl.dataset.mode = '';
      env.t = 0;
      env.silent = true;
      for (let i = 0; i < 360; i++) { env.t += 1 / 30; scene.update(1 / 30); }
      env.silent = false;
      $('#camName').textContent = scene.cam;
      $('#modelName').textContent = scene.model;
      log('info', 'MODEL', `${scene.model} loaded · TensorRT FP16`);
      renderStats();
      draw();
    }

    function step(dt) {
      env.t += dt;
      scene.update(dt);
      frameN++;
      const objs = scene.objects();
      for (const o of objs) {
        if (frameN % 3 === 0) {
          o.trail.push([o.x, o.y]);
          if (o.trail.length > 24) o.trail.shift();
        }
        addHeat(o.x, o.y);
      }
      for (let i = 0; i < heat.length; i++) heat[i] *= 0.9975;
    }

    function frame(now) {
      if (!running) return;
      const dt = Math.min(0.05, (now - last) / 1000 || 1 / 60);
      last = now;
      step(dt);
      draw();
      fpsAcc += 1 / dt; fpsN++;
      fpsT += dt; statT += dt;
      if (fpsT > 0.5) {
        $('#feedFps').textContent = Math.round(fpsAcc / fpsN);
        $('#feedClock').textContent = new Date().toTimeString().slice(0, 8);
        fpsAcc = fpsN = fpsT = 0;
      }
      if (statT > 0.25) { renderStats(); statT = 0; }
      requestAnimationFrame(frame);
    }

    function start() { if (running) return; running = true; last = performance.now(); requestAnimationFrame(frame); }
    function stop() { running = false; }

    let inView = false;
    new IntersectionObserver(([en]) => {
      inView = en.isIntersecting;
      if (inView && !document.hidden) start(); else stop();
    }, { threshold: 0.05 }).observe(wrap);
    document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); else if (inView) start(); });

    $$('.tab').forEach((tab) => tab.addEventListener('click', () => {
      $$('.tab').forEach((t) => { t.classList.toggle('active', t === tab); t.setAttribute('aria-selected', t === tab); });
      setMode(tab.dataset.mode);
    }));
    $('#optBoxes').addEventListener('change', (e) => { opts.boxes = e.target.checked; if (!running) draw(); });
    $('#optTrails').addEventListener('change', (e) => { opts.trails = e.target.checked; if (!running) draw(); });
    $('#optHeat').addEventListener('change', (e) => { opts.heat = e.target.checked; if (!running) draw(); });
    $('#optConf').addEventListener('input', (e) => {
      opts.conf = parseFloat(e.target.value);
      $('#confOut').textContent = opts.conf.toFixed(2);
      if (!running) draw();
    });

    new ResizeObserver(resize).observe(wrap);
    resize();
    setMode('retail');
  }

  /* ================================================================
     SPORTS SECTION — interactive heatmap
     ================================================================ */
  function initPitch() {
    const c = $('#pitch');
    if (!c) return;
    const ctx = c.getContext('2d');
    const GW = 105, GH = 68;
    const grid = new Float32Array(GW * GH);
    const off = document.createElement('canvas');
    off.width = GW; off.height = GH;
    const octx = off.getContext('2d');
    const img = octx.createImageData(GW, GH);
    const stat = $('#pitchStat');
    const head = $('.pitch-head span');
    const profiles = {
      10: { name: 'MATCH HEATMAP · #10', dist: '11.2 km', zones: [[0.5, 0.5, 0.14, 0.2, 1], [0.66, 0.35, 0.07, 0.08, 0.5], [0.38, 0.62, 0.08, 0.1, 0.4]] },
      9: { name: 'MATCH HEATMAP · #9', dist: '9.6 km', zones: [[0.8, 0.5, 0.09, 0.16, 1], [0.9, 0.42, 0.04, 0.08, 0.7], [0.62, 0.5, 0.08, 0.15, 0.3]] },
      4: { name: 'MATCH HEATMAP · #4', dist: '10.1 km', zones: [[0.22, 0.32, 0.08, 0.14, 1], [0.36, 0.45, 0.1, 0.12, 0.45], [0.12, 0.5, 0.05, 0.1, 0.3]] },
    };
    let W = 0, H = 0, pending = false;

    const gauss = () => { let u = 0, v = 0; while (!u) u = Math.random(); while (!v) v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(TAU * v); };

    function splat(gx, gy, sigma, amt) {
      const R = Math.ceil(sigma * 2.5);
      for (let y = Math.max(0, Math.floor(gy - R)); y <= Math.min(GH - 1, gy + R); y++) {
        for (let x = Math.max(0, Math.floor(gx - R)); x <= Math.min(GW - 1, gx + R); x++) {
          const d2 = (x - gx) ** 2 + (y - gy) ** 2;
          grid[y * GW + x] += amt * Math.exp(-d2 / (2 * sigma * sigma));
        }
      }
    }

    function load(id) {
      const p = profiles[id];
      grid.fill(0);
      p.zones.forEach(([cx, cy, sx, sy, w]) => {
        for (let i = 0; i < 900 * w; i++) splat((cx + gauss() * sx) * GW, (cy + gauss() * sy) * GH, 2.2, 0.08);
      });
      head.textContent = p.name;
      stat.textContent = `Distance ${p.dist}`;
      render();
    }

    function render() {
      pending = false;
      let max = 0;
      for (let i = 0; i < grid.length; i++) if (grid[i] > max) max = grid[i];
      const d = img.data;
      for (let i = 0; i < grid.length; i++) {
        const col = heatColor(max ? grid[i] / max : 0);
        d[i * 4] = col[0]; d[i * 4 + 1] = col[1]; d[i * 4 + 2] = col[2]; d[i * 4 + 3] = col[3];
      }
      octx.putImageData(img, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = '#07130d';
      ctx.fillRect(0, 0, W, H);
      const m = 10;
      drawPitch(ctx, m, m, W - m * 2, H - m * 2, 0.4);
      ctx.save();
      ctx.imageSmoothingEnabled = true;
      ctx.globalAlpha = 0.85;
      ctx.drawImage(off, m, m, W - m * 2, H - m * 2);
      ctx.restore();
    }

    function resize() {
      const r = c.getBoundingClientRect();
      const dpr = Math.min(2, devicePixelRatio || 1);
      W = r.width; H = r.height;
      c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      render();
    }

    let painted = false;
    c.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse' && e.buttons === 0) return;
      const r = c.getBoundingClientRect();
      const m = 10;
      const gx = ((e.clientX - r.left - m) / (r.width - m * 2)) * GW;
      const gy = ((e.clientY - r.top - m) / (r.height - m * 2)) * GH;
      splat(gx, gy, 2.6, 0.9);
      if (!painted) { painted = true; stat.textContent = 'Painting live movement…'; }
      if (!pending) { pending = true; requestAnimationFrame(render); }
    });

    $$('.chip-btn').forEach((b) => b.addEventListener('click', () => {
      $$('.chip-btn').forEach((x) => x.classList.toggle('active', x === b));
      painted = false;
      load(b.dataset.player);
    }));

    new ResizeObserver(resize).observe(c);
    resize();
    load(10);
  }

  /* ================================================================
     ROI CALCULATOR
     ================================================================ */
  function initROI() {
    const rev = $('#rev'), shrink = $('#shrink'), red = $('#red');
    if (!rev) return;
    const money = (v) => {
      if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
      if (v >= 1e6) return `$${(v / 1e6).toFixed(v >= 1e7 ? 1 : 2)}M`;
      return `$${Math.round(v / 1e3)}K`;
    };
    const update = () => {
      const R = +rev.value * 1e6, s = +shrink.value, r = +red.value;
      const loss = (R * s) / 100, save = (loss * r) / 100;
      $('#revOut').textContent = money(R);
      $('#shrinkOut').textContent = `${s.toFixed(1)}%`;
      $('#redOut').textContent = `${r}%`;
      $('#lossNow').textContent = money(loss);
      $('#saveNow').textContent = money(save);
      $('#roiBar').style.width = `${r}%`;
    };
    [rev, shrink, red].forEach((el) => el.addEventListener('input', update));
    update();
  }

  /* ================================================================
     INDUSTRIES — accessible tabs
     ================================================================ */
  function initIndustries() {
    const tabs = $$('.ind-tab');
    if (!tabs.length) return;
    const select = (tab, focus) => {
      tabs.forEach((t) => {
        const on = t === tab;
        t.classList.toggle('active', on);
        t.setAttribute('aria-selected', on);
        t.tabIndex = on ? 0 : -1;
        $(`#${t.getAttribute('aria-controls')}`).hidden = !on;
      });
      if (focus) tab.focus();
      tab.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reduceMotion ? 'auto' : 'smooth' });
    };
    tabs.forEach((t, i) => {
      t.addEventListener('click', () => select(t));
      t.addEventListener('keydown', (e) => {
        const dir = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
        if (dir) { e.preventDefault(); select(tabs[(i + dir + tabs.length) % tabs.length], true); }
        if (e.key === 'Home') { e.preventDefault(); select(tabs[0], true); }
        if (e.key === 'End') { e.preventDefault(); select(tabs[tabs.length - 1], true); }
      });
    });
  }

  /* ================================================================
     DEVELOPERS — code tabs, copy, streamed JSON response
     ================================================================ */
  function initDev() {
    const out = $('#respOut');
    if (!out) return;
    const responses = {
      python: {
        status: '200 OK · webhook',
        body: { event: 'concealment', stream: 'cam-04', track_id: 'P-012', confidence: 0.93, bbox: [412, 188, 466, 301], zone: 'aisle-2', clip_url: 'https://cdn.computesight.com/clips/7f3a.mp4', ts: '2026-11-18T14:02:11Z' },
      },
      js: {
        status: '200 OK · stream event',
        body: { event: 'sprint', player: { team: 'home', number: 10 }, speed_kmh: 31.4, distance_m: 42.7, confidence: 0.96, position_m: [64.2, 21.8], match_clock: '63:12' },
      },
      curl: {
        status: '200 OK · 41 ms',
        body: { image: 'part_1043.jpg', verdict: 'reject', detections: [{ label: 'scratch', confidence: 0.94, bbox: [118, 62, 171, 90] }], inference_ms: 41, model: 'qc-defects@7.2' },
      },
    };

    const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const highlight = (s) => esc(s).replace(
      /("(?:[^"\\]|\\.)*")(\s*:)?|\b(-?\d+(?:\.\d+)?)\b|\b(true|false|null)\b/g,
      (m, str, colon, num, kw) => {
        if (str) return colon ? `<span class="p">${str}</span>${colon}` : `<span class="s">${str}</span>`;
        if (num) return `<span class="n">${num}</span>`;
        return `<span class="k">${kw}</span>`;
      },
    );

    let lang = 'python', timer = 0, inView = false, started = false;
    const type = () => {
      cancelAnimationFrame(timer);
      const r = responses[lang];
      $('#respStatus').textContent = r.status;
      const text = JSON.stringify(r.body, null, 2);
      if (reduceMotion) { out.innerHTML = highlight(text); return; }
      let i = 0;
      const tick = () => {
        i = Math.min(text.length, i + 4);
        out.innerHTML = highlight(text.slice(0, i));
        if (i < text.length) timer = requestAnimationFrame(tick);
      };
      tick();
    };

    new IntersectionObserver(([en]) => {
      inView = en.isIntersecting;
      if (inView && !started) { started = true; setTimeout(type, 400); }
    }, { threshold: 0.3 }).observe(out);

    const tabs = $$('.code-tab');
    tabs.forEach((t) => t.addEventListener('click', () => {
      lang = t.dataset.lang;
      tabs.forEach((x) => { x.classList.toggle('active', x === t); x.setAttribute('aria-selected', x === t); });
      $$('.code-win pre.code:not(.resp)').forEach((p) => { p.hidden = p.dataset.lang !== lang; });
      started = true;
      type();
    }));

    const copyBtn = $('#copyCode');
    copyBtn.addEventListener('click', async () => {
      const pre = $(`.code-win pre.code[data-lang="${lang}"]`);
      try {
        await navigator.clipboard.writeText(pre.textContent);
        copyBtn.textContent = 'Copied ✓';
      } catch {
        copyBtn.textContent = 'Press ⌘C';
        const range = document.createRange();
        range.selectNodeContents(pre);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
      }
      copyBtn.classList.add('done');
      setTimeout(() => { copyBtn.textContent = 'Copy'; copyBtn.classList.remove('done'); }, 1800);
    });
  }

  /* ================================================================
     NAV — highlight the section currently in view
     ================================================================ */
  function initNavSpy() {
    const links = $$('.nav-links a[href^="#"]:not(.btn)');
    const map = new Map();
    links.forEach((a) => { const s = $(a.getAttribute('href')); if (s) map.set(s, a); });
    const io = new IntersectionObserver((entries) => entries.forEach((en) => {
      if (!en.isIntersecting) return;
      links.forEach((a) => a.classList.remove('current'));
      map.get(en.target).classList.add('current');
    }), { rootMargin: '-45% 0px -50% 0px' });
    map.forEach((_, s) => io.observe(s));
    // clear highlight when back at the hero
    addEventListener('scroll', () => { if (scrollY < innerHeight * 0.5) links.forEach((a) => a.classList.remove('current')); }, { passive: true });
  }

  /* ================================================================
     CONTACT FORM
     - data-endpoint set  → POSTs FormData to it (Formspree/Basin/Getform/your API)
     - data-endpoint empty → opens the visitor's email app addressed to data-email
     ================================================================ */
  function initForm() {
    const form = $('#contactForm');
    if (!form) return;
    const status = $('#formStatus');
    const btn = $('button[type="submit"]', form);
    const say = (cls, msg) => { status.className = `form-status mono ${cls}`; status.textContent = msg; };
    form.addEventListener('input', (e) => e.target.classList.remove('invalid'));

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      let ok = true;
      $$('[required]', form).forEach((el) => {
        const bad = !el.value.trim() || (el.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(el.value.trim()));
        el.classList.toggle('invalid', bad);
        if (bad) ok = false;
      });
      if (!ok) { say('err', '✕ Please fill in the highlighted fields.'); $('.invalid', form).focus(); return; }

      const name = form.elements.name.value.trim().split(/\s+/)[0];
      const thanks = `✓ Thanks ${name}! We'll reply within 48 hours.`;
      if (form.elements.website.value) { say('ok', thanks); form.reset(); return; } // honeypot: silently drop bots

      const endpoint = (form.dataset.endpoint || CFG.formEndpoint || '').trim();
      if (endpoint) {
        btn.disabled = true;
        say('', 'Sending…');
        try {
          const res = await fetch(endpoint, { method: 'POST', body: new FormData(form), headers: { Accept: 'application/json' } });
          if (!res.ok) throw new Error(res.status);
          say('ok', thanks);
          form.reset();
        } catch {
          say('err', `✕ Couldn't send. Please email ${form.dataset.email || CFG.contactEmail} directly.`);
        } finally {
          btn.disabled = false;
        }
        return;
      }

      const interests = $$('input[name="interest"]:checked', form).map((i) => i.nextElementSibling.textContent).join(', ') || '—';
      const body = [
        `Name: ${form.elements.name.value.trim()}`,
        `Email: ${form.elements.email.value.trim()}`,
        `Company: ${form.elements.company.value.trim() || '—'}`,
        `Interested in: ${interests}`,
        '',
        form.elements.message.value.trim(),
      ].join('\n');
      location.href = `mailto:${form.dataset.email || CFG.contactEmail}?subject=${encodeURIComponent(`Project enquiry: ${form.elements.company.value.trim() || name}`)}&body=${encodeURIComponent(body)}`;
      say('ok', '✓ Opening your email app to send…');
    });
  }

  /* ================================================================
     NAV DROPDOWN (click / keyboard; hover handled in CSS on desktop)
     ================================================================ */
  function initDropdown() {
    $$('.dd').forEach((dd) => {
      const btn = $('.dd-btn', dd);
      const set = (open) => { dd.classList.toggle('open', open); btn.setAttribute('aria-expanded', open); };
      btn.addEventListener('click', (e) => { e.stopPropagation(); set(!dd.classList.contains('open')); });
      dd.addEventListener('keydown', (e) => { if (e.key === 'Escape') { set(false); btn.focus(); } });
      document.addEventListener('click', (e) => { if (!dd.contains(e.target)) set(false); });
    });
  }

  /* ================================================================
     BACK TO TOP
     ================================================================ */
  function initToTop() {
    const b = document.createElement('button');
    b.className = 'to-top-btn';
    b.type = 'button';
    b.setAttribute('aria-label', 'Back to top');
    b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
    b.addEventListener('click', () => scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' }));
    document.body.appendChild(b);
    const upd = () => b.classList.toggle('show', scrollY > 700);
    addEventListener('scroll', upd, { passive: true });
    upd();
  }

  /* ================================================================
     COOKIE CONSENT + ANALYTICS (analytics load only after consent)
     ================================================================ */
  function initConsent() {
    const KEY = 'cs-consent';
    const get = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
    const put = (v) => { try { localStorage.setItem(KEY, v); } catch { /* storage blocked */ } };
    const a = CFG.analytics || {};
    let loaded = false;
    const loadAnalytics = () => {
      if (loaded) return;
      loaded = true;
      if (a.provider === 'plausible' && a.domain) {
        const s = document.createElement('script');
        s.defer = true; s.dataset.domain = a.domain; s.src = a.src || 'https://plausible.io/js/script.js';
        document.head.appendChild(s);
      } else if (a.provider === 'ga4' && a.id) {
        const s = document.createElement('script');
        s.async = true; s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(a.id)}`;
        document.head.appendChild(s);
        window.dataLayer = window.dataLayer || [];
        window.gtag = function () { window.dataLayer.push(arguments); };
        window.gtag('js', new Date());
        window.gtag('config', a.id, { anonymize_ip: true });
      }
    };
    const rootEl = document.querySelector('[data-root]');
    const base = rootEl ? rootEl.dataset.root : '';
    const show = () => {
      if ($('.cookie')) return;
      const el = document.createElement('div');
      el.className = 'cookie';
      el.setAttribute('role', 'dialog');
      el.setAttribute('aria-labelledby', 'cookie-title');
      el.innerHTML = `<h2 id="cookie-title">Your privacy</h2>
        <p>We use essential storage to run this site and, with your permission, privacy-friendly analytics to understand how it's used. See our <a href="${base}legal/cookies/index.html">cookie policy</a>.</p>
        <div class="cookie-actions"><button class="btn btn-ghost" data-c="essential">Essential only</button><button class="btn" data-c="all">Accept all</button></div>`;
      el.addEventListener('click', (e) => {
        const c = e.target.closest('[data-c]');
        if (!c) return;
        put(c.dataset.c);
        if (c.dataset.c === 'all') loadAnalytics();
        el.hidden = true;
        el.parentNode.removeChild(el);
      });
      document.body.appendChild(el);
    };
    const choice = get();
    if (choice === 'all') loadAnalytics();
    if (!choice && CFG.cookieBanner !== false) setTimeout(show, 900);
    $$('[data-cookie-settings]').forEach((b) => b.addEventListener('click', show));
  }

  /* ================================================================
     NEWSLETTER (footer)
     ================================================================ */
  function initNewsletter() {
    $$('.newsletter').forEach((form) => {
      const status = $('.newsletter-status', form);
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = form.elements.email.value.trim();
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { status.textContent = 'Please enter a valid email.'; return; }
        const endpoint = (CFG.newsletterEndpoint || '').trim();
        if (endpoint) {
          try {
            const res = await fetch(endpoint, { method: 'POST', body: new FormData(form), headers: { Accept: 'application/json' } });
            if (!res.ok) throw new Error(res.status);
            status.textContent = '✓ Subscribed. Watch your inbox for the next issue.';
            form.reset();
          } catch { status.textContent = 'Something went wrong. Please try again later.'; }
        } else {
          location.href = `mailto:${CFG.contactEmail}?subject=${encodeURIComponent('Newsletter subscription')}&body=${encodeURIComponent(`Please subscribe ${email} to ComputeSight Insights.`)}`;
          status.textContent = '✓ Opening your email app to confirm…';
        }
      });
    });
  }

  initDropdown();
  initToTop();
  initConsent();
  initNewsletter();
  initFeed();
  initPitch();
  initROI();
  initIndustries();
  initDev();
  initNavSpy();
  initForm();
})();
