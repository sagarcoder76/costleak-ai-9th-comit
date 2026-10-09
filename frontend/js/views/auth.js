/* Login / signup for companies. */
import { api, setSession, go, esc, STATE_LIST } from '../core.js';
import { busy, formData, alert as alertBox } from '../ui.js';

const art = (title, sub, bullets) => `
<div class="auth-art" style="background:radial-gradient(900px 500px at 10% 0%,rgba(15,181,160,.2),transparent 58%),
     radial-gradient(700px 500px at 90% 90%,rgba(124,92,255,.22),transparent 60%),#060F1E">
  <a href="/" class="row" style="gap:9px;font-weight:800;font-size:17px;color:#fff;letter-spacing:-.03em">
    <span class="logo">◈</span> CostLeak<span style="color:var(--teal)">AI</span></a>
  <div>
    <h2 style="font-size:30px;color:#fff;letter-spacing:-.035em;max-width:420px">${title}</h2>
    <p style="color:#A7BCD6;margin-top:12px;max-width:420px">${sub}</p>
    <div class="col" style="gap:12px;margin-top:26px">
      ${bullets.map(b => `<div class="row" style="gap:10px;align-items:flex-start">
        <span style="color:#5FE3CF">✓</span><span class="sm" style="color:#C2D4E8">${b}</span></div>`).join('')}
    </div>
  </div>
  <div class="xs" style="color:#6E87A6">Savings are estimates based on uploaded data. GST summaries must be
    reconciled with your books before filing.</div>
</div>`;

export async function login() {
  let demo = { email: '', password: '' };
  try { demo = (await api('/api/public/plans')).demo; } catch {}

  document.getElementById('app').innerHTML = `<div class="auth-wrap">
    ${art('Welcome back.', 'Sign in to see where your money went this month.',
      ['8 cost-leak detection engines', 'GST invoicing with auto CGST/SGST/IGST', 'Product cost & margin tracking'])}
    <div class="auth-form"><div class="auth-box">
      <h1 style="font-size:25px">Sign in</h1>
      <p class="muted sm" style="margin:6px 0 22px">New here?
        <a href="/signup" style="color:var(--teal-ink);font-weight:650">Create a company account →</a></p>
      <div id="msg"></div>
      <form id="f" class="mt">
        <div class="fr"><label class="field">Work email</label>
          <input name="email" type="email" required autocomplete="email" placeholder="you@company.in"></div>
        <div class="fr"><label class="field">Password</label>
          <input name="password" type="password" required autocomplete="current-password" placeholder="••••••••"></div>
        <button class="btn btn-primary btn-block btn-lg" type="submit">Sign in</button>
      </form>
      <div class="row" style="margin:18px 0;gap:10px"><div style="flex:1;height:1px;background:var(--line)"></div>
        <span class="xs muted">OR</span><div style="flex:1;height:1px;background:var(--line)"></div></div>
      <button class="btn btn-ghost btn-block" id="demo">▶ Open the demo company</button>
      <p class="xs muted center" style="margin-top:12px">Demo login — ${esc(demo.email)} / ${esc(demo.password)}</p>
    </div></div></div>`;

  const msg = document.getElementById('msg');
  const ended = sessionStorage.getItem('cl.signedout');
  if (ended) { msg.innerHTML = alertBox('warn', esc(ended)); sessionStorage.removeItem('cl.signedout'); }
  document.getElementById('f').onsubmit = async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    busy(btn, true, 'Signing in');
    msg.innerHTML = '';
    try {
      setSession(await api('/api/auth/login', { method: 'POST', body: formData(e.target) }));
      go('/app');
    } catch (err) {
      msg.innerHTML = alertBox('err', esc(err.message));
      busy(btn, false);
    }
  };
  document.getElementById('demo').onclick = async (e) => {
    busy(e.target, true, 'Loading demo');
    try { setSession(await api('/api/auth/login', { method: 'POST', body: demo })); go('/app'); }
    catch (err) { msg.innerHTML = alertBox('err', esc(err.message)); busy(e.target, false); }
  };
}

export async function signup() {
  const preset = new URLSearchParams(location.search).get('plan') || '';
  document.getElementById('app').innerHTML = `<div class="auth-wrap">
    ${art('Start finding leaks in 2 minutes.', 'A 14-day free trial of the Growth plan. No card required.',
      ['Unlimited cost-leak findings during trial', 'GST-compliant invoices from day one',
       'Your data stays in your own database'])}
    <div class="auth-form"><div class="auth-box">
      <h1 style="font-size:25px">Create your company account</h1>
      <p class="muted sm" style="margin:6px 0 20px">Already registered?
        <a href="/login" style="color:var(--teal-ink);font-weight:650">Sign in →</a></p>
      <div id="msg"></div>
      <form id="f" class="mt">
        <div class="fr"><label class="field">Company name *</label>
          <input name="company_name" required placeholder="Nexa Solutions Pvt. Ltd."></div>
        <div class="grid g2" style="gap:12px">
          <div class="fr"><label class="field">Your name *</label><input name="name" required placeholder="Rohit Mehra"></div>
          <div class="fr"><label class="field">Phone</label><input name="phone" placeholder="+91 98100 00000"></div>
        </div>
        <div class="fr"><label class="field">Work email *</label>
          <input name="email" type="email" required autocomplete="email" placeholder="you@company.in"></div>
        <div class="fr"><label class="field">Password *</label>
          <input name="password" type="password" required autocomplete="new-password" placeholder="At least 8 characters">
          <div class="help">Minimum 8 characters, with at least one letter and one number.</div></div>
        <div class="grid g2" style="gap:12px">
          <div class="fr"><label class="field">GSTIN (optional)</label>
            <input name="gstin" placeholder="06AABCN4567P1Z5" style="text-transform:uppercase">
            <div class="help" id="gsthelp">We validate it and detect your state.</div></div>
          <div class="fr"><label class="field">State</label>
            <select name="state_code">${Object.entries(STATE_LIST).map(([c, n]) =>
              `<option value="${c}" ${c === '06' ? 'selected' : ''}>${n}</option>`).join('')}</select></div>
        </div>
        <div class="grid g2" style="gap:12px">
          <div class="fr"><label class="field">Industry</label>
            <select name="industry">${['IT Services & Consulting', 'Agency / Marketing', 'Manufacturing',
              'Retail & E-commerce', 'Logistics', 'Professional Services', 'Healthcare', 'Other']
              .map(i => `<option>${i}</option>`).join('')}</select></div>
          <div class="fr"><label class="field">Team size</label>
            <select name="team_size">${['1-10', '11-50', '51-200', '200+'].map(i => `<option>${i}</option>`).join('')}</select></div>
        </div>
        <button class="btn btn-teal btn-block btn-lg" type="submit">Start free trial →</button>
        <p class="xs muted center" style="margin-top:11px">
          ${preset ? `Selected plan: <strong>${esc(preset)}</strong> · ` : ''}14-day trial, cancel anytime.</p>
      </form>
    </div></div></div>`;

  const msg = document.getElementById('msg');
  const gstin = document.querySelector('[name=gstin]');
  gstin.addEventListener('blur', async () => {
    const v = gstin.value.trim();
    const help = document.getElementById('gsthelp');
    if (!v) { help.textContent = 'We validate it and detect your state.'; gstin.classList.remove('inp-err'); return; }
    try {
      const r = await api(`/api/gst/validate?gstin=${encodeURIComponent(v)}`);
      gstin.classList.toggle('inp-err', !r.valid);
      help.textContent = r.valid ? `✓ Valid — ${r.state} (PAN ${r.pan})` : `✗ ${r.message}`;
      help.style.color = r.valid ? 'var(--green)' : 'var(--red)';
      if (r.valid) document.querySelector('[name=state_code]').value = r.state_code;
    } catch {}
  });

  document.getElementById('f').onsubmit = async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type=submit]');
    busy(btn, true, 'Creating account');
    msg.innerHTML = '';
    const data = formData(e.target);
    if (!data.gstin) delete data.gstin;
    try {
      setSession(await api('/api/auth/signup', { method: 'POST', body: data }));
      go('/app');
    } catch (err) {
      msg.innerHTML = alertBox('err', esc(err.message));
      busy(btn, false);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };
}
