/* AgentPulse site — pulse-network canvas, scroll reveal, nav, live chat demo */
document.documentElement.classList.add('js');

const reduceMotion = window.matchMedia(
  '(prefers-reduced-motion: reduce)',
).matches;

/* ── release assets + privacy-friendly download analytics ── */
(() => {
  const links = [...document.querySelectorAll('[data-download]')];
  const primary = document.getElementById('primary-download');
  const isWindows = /Windows/i.test(navigator.userAgent);
  const recordEvent = (event) => {
    fetch('https://api.agentpulse.cc/api/telemetry/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event }),
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
      keepalive: true,
    }).catch(() => {
      // Telemetry must never interfere with downloads or install help.
    });
  };

  if (isWindows && primary) {
    primary.href =
      'https://github.com/Clycheng/agentpulse-releases/releases/latest/download/AgentPulse-windows-x64.exe';
    primary.dataset.download = 'windows';
    primary.firstChild.textContent = 'Download for Windows ';
  }

  for (const link of links) {
    link.addEventListener('click', () => {
      const platform =
        link.dataset.download === 'windows' ? 'windows' : 'macos';
      recordEvent(`download_${platform}`);
    });
  }

  for (const details of document.querySelectorAll('[data-install-help]')) {
    details.addEventListener('toggle', () => {
      if (details.open) {
        recordEvent(`install_help_${details.dataset.installHelp}`);
      }
    });
  }

  fetch(
    'https://github.com/Clycheng/agentpulse-releases/releases/latest/download/latest.json',
  )
    .then((response) => {
      if (!response.ok) throw new Error('release manifest unavailable');
      return response.json();
    })
    .then((manifest) => {
      document.querySelectorAll('[data-release-version]').forEach((element) => {
        element.textContent = manifest.version;
      });
      const macSha = document.querySelector('[data-sha="macos"]');
      const windowsSha = document.querySelector('[data-sha="windows"]');
      if (macSha && manifest.platforms?.macos_arm64?.dmg_sha256) {
        macSha.textContent = manifest.platforms.macos_arm64.dmg_sha256;
      }
      if (windowsSha && manifest.platforms?.windows_x64?.sha256) {
        windowsSha.textContent = manifest.platforms.windows_x64.sha256;
      }
    })
    .catch(() => {
      // The first release may not exist yet; stable download URLs stay valid
      // as soon as the tagged release workflow publishes the assets.
    });
})();

/* ── nav: condense on scroll ── */
const nav = document.getElementById('nav');
const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 12);
onScroll();
window.addEventListener('scroll', onScroll, { passive: true });

/* ── scroll reveal ──
   Content must NEVER stay hidden: CSS transitions freeze on hidden tabs /
   headless renderers, so a reveal that gates opacity can ship blank. We add
   `.in` on intersection, with a hard failsafe that force-reveals (transition
   off, so opacity can't get stuck mid-animation) after a short delay. */
(() => {
  const items = [...document.querySelectorAll('[data-reveal]')];
  const forceShow = (el) => {
    el.style.transition = 'none';
    el.classList.add('in');
  };
  if (reduceMotion || !('IntersectionObserver' in window)) {
    items.forEach(forceShow);
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('in');
          io.unobserve(e.target);
        }
      });
    },
    { threshold: 0.1, rootMargin: '0px 0px -6% 0px' },
  );
  items.forEach((el) => io.observe(el));
  // failsafe: after 1.8s force every item fully visible (transition off), so a
  // frozen mid-transition item can never stay dim/blank.
  setTimeout(() => items.forEach(forceShow), 1800);
})();

/* ── pulse-network canvas ── */
(() => {
  const canvas = document.getElementById('pulse-canvas');
  if (!canvas || reduceMotion) return;
  const ctx = canvas.getContext('2d');
  let w, h, dpr, nodes, edges, pulses, raf;

  const rand = (a, b) => a + Math.random() * (b - a);

  function build() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const count = Math.max(18, Math.min(46, Math.floor((w * h) / 46000)));
    nodes = Array.from({ length: count }, () => ({
      x: rand(0, w),
      y: rand(0, h),
      vx: rand(-0.12, 0.12),
      vy: rand(-0.12, 0.12),
      r: rand(1, 2.4),
    }));
    edges = [];
    const maxD = Math.min(w, h) * 0.24;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const d = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
        if (d < maxD) edges.push({ a: i, b: j });
      }
    }
    pulses = [];
  }

  function spawnPulse() {
    if (!edges.length) return;
    const e = edges[(Math.random() * edges.length) | 0];
    pulses.push({ a: e.a, b: e.b, t: 0, speed: rand(0.006, 0.016) });
  }

  let last = 0;
  function frame(ts) {
    raf = requestAnimationFrame(frame);
    ctx.clearRect(0, 0, w, h);

    // drift nodes
    for (const n of nodes) {
      n.x += n.vx;
      n.y += n.vy;
      if (n.x < 0 || n.x > w) n.vx *= -1;
      if (n.y < 0 || n.y > h) n.vy *= -1;
    }

    // edges
    ctx.lineWidth = 1;
    for (const e of edges) {
      const a = nodes[e.a];
      const b = nodes[e.b];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const alpha = Math.max(0, 0.1 * (1 - d / (Math.min(w, h) * 0.24)));
      if (alpha <= 0) continue;
      ctx.strokeStyle = `rgba(45, 212, 191, ${alpha})`;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }

    // nodes
    for (const n of nodes) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(147, 197, 189, 0.5)';
      ctx.fill();
    }

    // traveling pulses
    for (let i = pulses.length - 1; i >= 0; i--) {
      const p = pulses[i];
      p.t += p.speed;
      if (p.t >= 1) {
        pulses.splice(i, 1);
        continue;
      }
      const a = nodes[p.a];
      const b = nodes[p.b];
      const x = a.x + (b.x - a.x) * p.t;
      const y = a.y + (b.y - a.y) * p.t;
      const g = ctx.createRadialGradient(x, y, 0, x, y, 7);
      g.addColorStop(0, 'rgba(45, 212, 191, 0.9)');
      g.addColorStop(1, 'rgba(45, 212, 191, 0)');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(x, y, 7, 0, Math.PI * 2);
      ctx.fill();
    }

    if (ts - last > 520) {
      last = ts;
      if (pulses.length < 8) spawnPulse();
    }
  }

  build();
  raf = requestAnimationFrame(frame);
  let rt;
  window.addEventListener('resize', () => {
    clearTimeout(rt);
    rt = setTimeout(build, 200);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(raf);
    else raf = requestAnimationFrame(frame);
  });
})();

/* ── live group-chat demo ── */
(() => {
  const body = document.getElementById('chat-body');
  if (!body) return;

  const people = {
    you: { name: 'You', tag: 'boss', bg: '#2b3138' },
    nova: { name: 'Nova', tag: 'data analyst', bg: '#7c5cff' },
    aria: { name: 'Aria', tag: 'content lead', bg: '#c0563a' },
    mira: { name: 'Mira', tag: 'secretary', bg: '#3b74d6' },
  };

  const script = [
    { who: 'you', text: 'Plan next week’s content for us.' },
    {
      who: 'nova',
      text: 'Last week “office gear” posts got 2.3× the saves of skincare. Lead with office scenes?',
    },
    { who: 'you', text: 'Yes. Feature our own desk shelf. No paid promos.' },
    {
      who: 'aria',
      text: 'Got it — 5 topics, 2 spotlighting the shelf. Video, or image-only?',
    },
    { who: 'you', text: 'Image-only for now.' },
    {
      who: 'mira',
      text: 'Aligned. Wrapping the discussion into a brief for your sign-off.',
    },
    { type: 'brief' },
    { type: 'approve' },
  ];

  function avatar(p) {
    const el = document.createElement('span');
    el.className = 'msg-av';
    el.style.background = p.bg;
    el.textContent = p.name[0];
    return el;
  }

  function addMsg({ who, text }) {
    const p = people[who];
    const row = document.createElement('div');
    row.className = 'msg' + (who === 'you' ? ' me' : '');
    const main = document.createElement('div');
    main.className = 'msg-main';
    main.innerHTML =
      `<div class="msg-name"><b>${p.name}</b>${who === 'you' ? '' : p.tag}</div>` +
      `<div class="msg-text"></div>`;
    row.appendChild(avatar(p));
    row.appendChild(main);
    body.appendChild(row);
    main.querySelector('.msg-text').textContent = text;
    scroll();
  }

  function addBrief() {
    const c = document.createElement('div');
    c.className = 'card brief';
    c.innerHTML =
      '<div class="card-h">\u{1F4CB} Consensus brief · awaiting confirm</div>' +
      '<div class="card-row"><b>Goal:</b> 5 Xiaohongshu “office gear” posts; 2 spotlight our desk shelf.</div>' +
      '<div class="card-row"><b>Scope:</b> topics, copy, shots, schedule. No paid promos.</div>' +
      '<div class="card-row"><b>Owner:</b> Aria</div>' +
      '<div class="card-actions"><span class="mini p">Confirm &amp; create tasks</span><span class="mini s">Keep discussing</span></div>';
    body.appendChild(c);
    scroll();
  }

  function addApprove() {
    const c = document.createElement('div');
    c.className = 'card approve';
    c.innerHTML =
      '<div class="card-h">⚠ High-risk action · needs you</div>' +
      '<div class="card-row">Aria wants to publish 5 posts to the live account.</div>' +
      '<div class="card-actions"><span class="mini p">Allow once</span><span class="mini s">Allow always</span><span class="mini s">Deny</span></div>';
    body.appendChild(c);
    scroll();
  }

  function typing() {
    const row = document.createElement('div');
    row.className = 'msg';
    row.dataset.typing = '1';
    row.innerHTML =
      '<span class="msg-av" style="background:#1a2226"></span>' +
      '<div class="msg-text"><span class="typing"><i></i><i></i><i></i></span></div>';
    body.appendChild(row);
    scroll();
    return row;
  }

  function scroll() {
    body.scrollTop = body.scrollHeight;
  }
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  async function play() {
    body.innerHTML = '';
    for (const step of script) {
      if (step.type === 'brief') {
        await wait(700);
        addBrief();
        await wait(1600);
        continue;
      }
      if (step.type === 'approve') {
        await wait(700);
        addApprove();
        await wait(1600);
        continue;
      }
      if (step.who !== 'you') {
        const t = typing();
        await wait(900 + step.text.length * 12);
        t.remove();
      } else {
        await wait(650);
      }
      addMsg(step);
      await wait(500);
    }
    await wait(3600);
    body.style.transition = 'opacity .5s';
    body.style.opacity = '0';
    await wait(500);
    body.style.opacity = '1';
    play();
  }

  // start when the chat scrolls into view
  if (reduceMotion || !('IntersectionObserver' in window)) {
    // static fallback: render the whole thread once
    script.forEach((s) =>
      s.type === 'brief'
        ? addBrief()
        : s.type === 'approve'
          ? addApprove()
          : addMsg(s),
    );
    return;
  }
  const io = new IntersectionObserver(
    (entries, obs) => {
      if (entries[0].isIntersecting) {
        obs.disconnect();
        play();
      }
    },
    { threshold: 0.3 },
  );
  io.observe(body);
})();
