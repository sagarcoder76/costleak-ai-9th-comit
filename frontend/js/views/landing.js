/* Public marketing site — dark, 3D, animated. Loaded only on the landing route. */
import { api, esc, inr, state, go } from '../core.js';

let raf = null;

export async function landing() {
  const app = document.getElementById('app');
  let plans = [];
  try { plans = (await api('/api/public/plans')).plans; } catch {}

  app.innerHTML = `
  <div class="landing" id="land">
    <nav class="nav"><div class="nav-in">
      <a href="/" style="display:flex;align-items:center;gap:9px;font-weight:800;font-size:16.5px;color:#fff;letter-spacing:-.03em">
        <span class="logo">◈</span> CostLeak<span style="color:var(--teal)">AI</span></a>
      <div class="row" style="gap:2px" id="navlinks">
        <a class="lnk" href="#features">Features</a>
        <a class="lnk" href="#how">How it works</a>
        <a class="lnk" href="#gst">GST & Invoicing</a>
        <a class="lnk" href="#pricing">Pricing</a>
      </div>
      <div class="row" style="gap:8px">
        <a class="btn btn-glass btn-sm" href="/login">Sign in</a>
        <a class="btn btn-teal btn-sm" href="/signup">Start free trial</a>
      </div>
    </div></nav>

    <header class="hero">
      <canvas id="bg3d"></canvas>
      <div class="wrap grid g2" style="gap:46px;align-items:center">
        <div>
          <span class="chip-glow">◈ Built for Indian SMBs · GST ready</span>
          <h1 class="h1" style="margin:18px 0 16px">Find hidden money leaks<br>
            <span class="grad">before they become annual losses.</span></h1>
          <p class="sub">Upload your company expenses in Excel. CostLeak AI finds duplicate payments,
            unused software seats and overlapping tools — then runs your GST invoicing, cost database
            and profit margins in the same place.</p>
          <div class="row" style="margin-top:28px;gap:11px">
            <a class="btn btn-teal btn-lg" href="/signup">Start 14-day free trial →</a>
            <button class="btn btn-glass btn-lg" id="demo-btn">▶ Try the live demo</button>
          </div>
          <p class="xs" style="color:#7E95B4;margin-top:13px">No card required · Demo account pre-loaded with a real Indian dataset</p>
          <div class="row" style="margin-top:30px;gap:26px">
            <div><div style="font-size:22px;font-weight:800;color:#5FE3CF">₹3.0 L</div>
              <div class="xs" style="color:#7E95B4">waste found / month</div></div>
            <div><div style="font-size:22px;font-weight:800;color:#fff">8</div>
              <div class="xs" style="color:#7E95B4">detection engines</div></div>
            <div><div style="font-size:22px;font-weight:800;color:#fff">&lt;60s</div>
              <div class="xs" style="color:#7E95B4">upload to report</div></div>
          </div>
        </div>

        <div class="scene"><div class="tilt float">
          <div class="glass" style="padding:20px">
            <div class="row-b" style="margin-bottom:14px">
              <strong style="color:#fff;font-size:14px">Nexa Solutions Pvt. Ltd.</strong>
              <span class="badge b-teal">Live demo</span></div>
            <div class="grid g2" style="gap:11px">
              <div class="lift" style="background:rgba(255,255,255,.07);border-radius:13px;padding:13px">
                <div class="xs" style="color:#9DB6D2">MONTHLY SPEND</div>
                <div style="font-size:21px;font-weight:800;color:#fff">₹9.02 L</div></div>
              <div class="lift" style="background:rgba(226,85,85,.18);border-radius:13px;padding:13px">
                <div class="xs" style="color:#FFC2C2">ESTIMATED WASTE</div>
                <div style="font-size:21px;font-weight:800;color:#FF9C9C">₹3.03 L</div></div>
            </div>
            <div class="lift-2" style="margin-top:13px;display:grid;gap:8px">
              ${[['🧾', 'Duplicate payment — Tata Communications', '₹19,800', '#FF9C9C'],
                 ['🧩', 'Overlapping cloud storage tools', '₹12,200/mo', '#5FE3CF'],
                 ['⏱️', 'Invoice data entry automation', '₹81,000/mo', '#5FE3CF']].map(([i, t, v, c]) =>
                `<div style="background:rgba(255,255,255,.07);border-radius:10px;padding:10px 12px;
                     display:flex;justify-content:space-between;gap:10px;font-size:12.5px;color:#DCE8F4">
                   <span>${i} ${t}</span><strong style="color:${c}">${v}</strong></div>`).join('')}
            </div>
            <div class="lift" style="margin-top:13px;background:rgba(15,181,160,.12);border:1px solid rgba(15,181,160,.3);
                 border-radius:11px;padding:11px 13px;font-size:12.5px;color:#9FF0E2">
              ✅ GSTR-1 ready · 36 invoices · ₹1.24 L tax collected this quarter</div>
          </div>
        </div></div>
      </div>
    </header>

    <section class="sec" id="features">
      <div class="wrap">
        <div class="center reveal" style="max-width:640px;margin-inline:auto">
          <span class="chip-glow">WHAT IT FINDS</span>
          <h2 style="margin:14px 0 10px;color:#fff">Six silent money leaks, found automatically</h2>
          <p style="color:#A7BCD6">Every finding shows the evidence rows, the exact formula and a rupee impact
            per month and per year. Deterministic maths — not an AI guess.</p>
        </div>
        <div class="grid g3 reveal" style="margin-top:34px">
          ${[['🧾', 'Duplicate payments', 'Same vendor, matching amount, paid twice inside the window. Usually recoverable as a refund.'],
             ['🎫', 'Unused software seats', 'Seats paid minus seats used × cost per seat. The most repeatable monthly saving in any stack.'],
             ['🧩', 'Overlapping tools', 'Canva + Adobe Express. Zoom + Meet. Slack + Teams. Jira + Asana + Trello. Drive + Dropbox.'],
             ['📈', 'Silent price hikes', 'Any vendor billing above 20% of its own recent average, flagged before the renewal locks in.'],
             ['⏱️', 'Manual-work cost', 'Tasks × minutes × hourly cost ÷ 60. Turns invisible salary time into a number you can act on.'],
             ['🌙', 'Overtime & idle spend', 'Repeated departmental overtime and under-utilised paid resources, costed month by month.']
            ].map(([i, t, d]) => `<div class="feat"><div class="ic">${i}</div>
              <h3 style="font-size:16px;color:#fff;margin-bottom:6px">${t}</h3>
              <p class="sm" style="color:#9DB6D2">${d}</p></div>`).join('')}
        </div>
      </div>
    </section>

    <section class="sec" id="gst" style="background:linear-gradient(180deg,transparent,rgba(124,92,255,.07),transparent)">
      <div class="wrap grid g2" style="gap:44px;align-items:center">
        <div class="reveal">
          <span class="chip-glow">GST · INVOICING · MARGINS</span>
          <h2 style="margin:14px 0 14px;color:#fff">Your CA charges ₹5,000 a month to tell you this.</h2>
          <p style="color:#A7BCD6;margin-bottom:20px">Record what each product costs you and what you charge.
            CostLeak AI handles the GST maths, generates compliant tax invoices and tells you which products
            are quietly losing money.</p>
          <div class="col" style="gap:11px">
            ${[['Auto CGST / SGST / IGST', 'Place-of-supply logic applied automatically from the customer GSTIN.'],
               ['GSTIN validation', 'Format, state code and checksum verified before you bill anyone.'],
               ['GSTR-1 & HSN exports', 'Monthly summaries, rate-wise breakup and CSV export for your filing.'],
               ['Input tax credit', 'Purchase bills tracked so net GST payable is calculated, not guessed.'],
               ['Margin alerts', '"You are selling this below cost" — before the year-end, not after.']
              ].map(([t, d]) => `<div class="row" style="gap:11px;align-items:flex-start">
                 <span style="color:#5FE3CF;font-size:15px">✓</span>
                 <div><strong style="color:#fff;font-size:14px">${t}</strong>
                 <div class="sm" style="color:#9DB6D2">${d}</div></div></div>`).join('')}
          </div>
        </div>
        <div class="scene reveal"><div class="tilt glass" style="padding:18px;transform:rotateX(7deg) rotateY(9deg)">
          <div class="row-b" style="margin-bottom:12px"><strong style="color:#fff">TAX INVOICE</strong>
            <span class="badge b-green">Intra-state</span></div>
          <table style="font-size:11.5px;color:#C7D9EC">
            <tr style="color:#8FA9C4"><td style="padding:5px">Item</td><td class="r">Taxable</td><td class="r">CGST 9%</td><td class="r">SGST 9%</td></tr>
            <tr><td style="padding:5px">Website Design</td><td class="r">45,000</td><td class="r">4,050</td><td class="r">4,050</td></tr>
            <tr><td style="padding:5px">AMC (annual)</td><td class="r">24,000</td><td class="r">2,160</td><td class="r">2,160</td></tr>
            <tr><td style="padding:5px">Cloud Hosting ×12</td><td class="r">30,000</td><td class="r">2,700</td><td class="r">2,700</td></tr>
          </table>
          <div class="row-b" style="margin-top:12px;padding-top:11px;border-top:1px solid rgba(255,255,255,.15)">
            <span class="sm" style="color:#9DB6D2">Total payable</span>
            <strong style="font-size:19px;color:#fff">₹1,16,820</strong></div>
          <div class="lift" style="margin-top:12px;background:rgba(31,169,113,.14);border:1px solid rgba(31,169,113,.3);
               border-radius:10px;padding:10px 12px;font-size:12px;color:#86E3B8">
            📊 Cost ₹42,400 · Profit ₹56,600 · Margin 57.2%</div>
        </div></div>
      </div>
    </section>

    <section class="sec" id="how">
      <div class="wrap">
        <div class="center reveal"><span class="chip-glow">HOW IT WORKS</span>
          <h2 style="margin:14px 0 8px;color:#fff">Four steps, under five minutes</h2></div>
        <div class="grid g4 reveal" style="margin-top:32px">
          ${[['01', 'Create your company', 'Sign up, add your GSTIN. We detect your state automatically.'],
             ['02', 'Add products & costs', 'What each item costs you, what you sell it for, its GST rate and HSN.'],
             ['03', 'Upload or invoice', 'Drop in an expense sheet for leak detection, or raise GST invoices directly.'],
             ['04', 'Act on the findings', 'Ranked savings, margin alerts, GST summary and a one-page PDF for the board.']
            ].map(([n, t, d]) => `<div class="feat">
              <div style="font-size:26px;font-weight:800;color:rgba(15,181,160,.5);letter-spacing:-.04em">${n}</div>
              <h3 style="font-size:15.5px;color:#fff;margin:7px 0 6px">${t}</h3>
              <p class="sm" style="color:#9DB6D2">${d}</p></div>`).join('')}
        </div>
      </div>
    </section>

    <section class="sec" id="pricing">
      <div class="wrap">
        <div class="center reveal"><span class="chip-glow">PRICING</span>
          <h2 style="margin:14px 0 8px;color:#fff">Costs less than the leaks it finds</h2>
          <p style="color:#A7BCD6">Every plan starts with a 14-day free trial. No card required.</p></div>
        <div class="grid g3 reveal" style="margin-top:32px">
          ${plans.map(p => `<div class="price ${p.popular ? 'pop' : ''}">
            ${p.popular ? '<span class="badge b-teal" style="position:absolute;top:-11px;left:24px">MOST POPULAR</span>' : ''}
            <h3 style="color:#fff;font-size:19px">${esc(p.name)}</h3>
            <p class="sm" style="color:#9DB6D2;min-height:38px;margin-top:5px">${esc(p.tagline)}</p>
            <div style="margin:14px 0 6px"><span style="font-size:33px;font-weight:800;color:#fff">₹${p.price_monthly.toLocaleString('en-IN')}</span>
              <span class="sm" style="color:#8FA9C4">/month</span></div>
            <div class="xs" style="color:#7E95B4;margin-bottom:16px">or ₹${p.price_yearly.toLocaleString('en-IN')}/year — 2 months free</div>
            <a class="btn ${p.popular ? 'btn-teal' : 'btn-glass'} btn-block" href="/signup?plan=${p.code}">Start free trial</a>
            <div class="col" style="gap:8px;margin-top:17px">
              ${p.features.map(f => `<div class="sm" style="color:#B9CCE2">✓ ${esc(f)}</div>`).join('')}
            </div>
            <div class="xs" style="color:#6E87A6;margin-top:14px;padding-top:12px;border-top:1px solid rgba(255,255,255,.08)">
              ${p.limits.users} users · ${p.limits.invoices_per_month.toLocaleString('en-IN')} invoices/mo · ${p.limits.products.toLocaleString('en-IN')} products</div>
          </div>`).join('')}
        </div>
      </div>
    </section>

    <section class="sec" style="padding-top:20px">
      <div class="wrap center reveal">
        <div class="glass" style="padding:46px 28px">
          <h2 style="color:#fff">Stop paying for what you don't use.</h2>
          <p style="color:#A7BCD6;margin:12px auto 24px;max-width:520px">
            Try the demo company first — it is pre-loaded with expenses, subscriptions, invoices and GST data.</p>
          <div class="row" style="justify-content:center;gap:11px">
            <a class="btn btn-teal btn-lg" href="/signup">Create your free account</a>
            <button class="btn btn-glass btn-lg" id="demo-btn-2">▶ Open the demo</button>
          </div>
        </div>
      </div>
    </section>

    <footer><div class="wrap row-b">
      <div>© ${new Date().getFullYear()} CostLeak AI · Made for Indian businesses</div>
      <div class="xs">Savings are estimates based on uploaded data. GST summaries must be reconciled before filing.</div>
    </div></footer>
  </div>`;

  // demo login
  const demo = async () => {
    try {
      const info = await api('/api/public/plans');
      const r = await api('/api/auth/login', { method: 'POST', body: info.demo });
      const { setSession } = await import('../core.js');
      setSession(r);
      go('/app');
    } catch (e) { alert(e.message); }
  };
  document.getElementById('demo-btn').onclick = demo;
  document.getElementById('demo-btn-2').onclick = demo;

  // smooth in-page anchors
  document.querySelectorAll('#navlinks a').forEach(a => a.onclick = (e) => {
    e.preventDefault();
    document.querySelector(a.getAttribute('href'))?.scrollIntoView({ behavior: 'smooth' });
  });

  initReveal();
  initBackground();
  return () => { if (raf) cancelAnimationFrame(raf); raf = null; };
}

/* ------------------------------------------------ scroll reveal ----- */
function initReveal() {
  const io = new IntersectionObserver((entries) => {
    entries.forEach(en => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
  }, { threshold: 0.12 });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
}

/* ------------------------------------- lightweight 3D background ---- */
/* A rotating wireframe mesh + particle field drawn on a 2D canvas.
   Gives real depth without shipping a 600 KB WebGL library.          */
function initBackground() {
  const cv = document.getElementById('bg3d');
  if (!cv) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const ctx = cv.getContext('2d');
  let W, H, dpr;
  const resize = () => {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = cv.parentElement.clientWidth; H = cv.parentElement.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  window.addEventListener('resize', resize);

  // grid mesh points
  const GRID = 13, SPREAD = 150;
  const pts = [];
  for (let i = 0; i < GRID; i++)
    for (let j = 0; j < GRID; j++)
      pts.push({ x: (i - GRID / 2) * SPREAD / 6, z: (j - GRID / 2) * SPREAD / 6, i, j });

  const stars = Array.from({ length: 54 }, () => ({
    x: (Math.random() - 0.5) * 420, y: (Math.random() - 0.5) * 240,
    z: Math.random() * 420 + 60, s: Math.random() * 1.6 + 0.4,
  }));

  let t = 0, mx = 0, my = 0;
  window.addEventListener('mousemove', (e) => {
    mx = (e.clientX / window.innerWidth - 0.5) * 0.34;
    my = (e.clientY / window.innerHeight - 0.5) * 0.22;
  }, { passive: true });

  const project = (x, y, z) => {
    const f = 330 / (z + 330);
    return { X: W / 2 + x * f * 2.1, Y: H / 2 + y * f * 2.1 + 48, f };
  };

  function frame() {
    ctx.clearRect(0, 0, W, H);
    t += 0.0055;
    const ry = t + mx, rx = 0.52 + my;

    // --- particles
    stars.forEach(s => {
      s.z -= 0.55;
      if (s.z < 40) { s.z = 480; s.x = (Math.random() - 0.5) * 420; s.y = (Math.random() - 0.5) * 240; }
      const p = project(s.x, s.y, s.z);
      const a = Math.max(0, 1 - s.z / 480) * 0.55;
      ctx.fillStyle = `rgba(150,220,255,${a})`;
      ctx.beginPath(); ctx.arc(p.X, p.Y, s.s * p.f * 2, 0, 7); ctx.fill();
    });

    // --- wave mesh
    const proj = pts.map(p => {
      const wave = Math.sin(p.x * 0.055 + t * 2.1) * 7 + Math.cos(p.z * 0.06 + t * 1.5) * 7;
      let x = p.x, y = wave, z = p.z;
      let x1 = x * Math.cos(ry) - z * Math.sin(ry);
      let z1 = x * Math.sin(ry) + z * Math.cos(ry);
      let y1 = y * Math.cos(rx) - z1 * Math.sin(rx);
      let z2 = y * Math.sin(rx) + z1 * Math.cos(rx);
      return { ...project(x1, y1, z2 + 190), i: p.i, j: p.j, w: wave };
    });

    ctx.lineWidth = 1;
    for (let i = 0; i < GRID; i++) {
      for (let j = 0; j < GRID; j++) {
        const a = proj[i * GRID + j];
        const right = j < GRID - 1 ? proj[i * GRID + j + 1] : null;
        const down = i < GRID - 1 ? proj[(i + 1) * GRID + j] : null;
        const alpha = Math.max(0, Math.min(0.42, a.f * 0.42));
        const hue = 168 + a.w * 2.6;
        ctx.strokeStyle = `hsla(${hue},72%,58%,${alpha * 0.55})`;
        if (right) { ctx.beginPath(); ctx.moveTo(a.X, a.Y); ctx.lineTo(right.X, right.Y); ctx.stroke(); }
        if (down) { ctx.beginPath(); ctx.moveTo(a.X, a.Y); ctx.lineTo(down.X, down.Y); ctx.stroke(); }
        ctx.fillStyle = `hsla(${hue},85%,68%,${alpha})`;
        ctx.beginPath(); ctx.arc(a.X, a.Y, a.f * 1.7, 0, 7); ctx.fill();
      }
    }
    raf = requestAnimationFrame(frame);
  }
  frame();
}
