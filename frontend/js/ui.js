/* Shared UI components and the authenticated app shell. */
import { state, esc, inr, inrShort, logout, toggleTheme, go } from './core.js';

/* ------------------------------------------------------------ toast -- */
export function toast(msg, kind = '') {
  let wrap = document.querySelector('.toast-wrap');
  if (!wrap) { wrap = document.createElement('div'); wrap.className = 'toast-wrap'; document.body.appendChild(wrap); }
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateY(8px)'; }, 2800);
  setTimeout(() => el.remove(), 3200);
}

/* ------------------------------------------------------------ modal -- */
export function modal(title, html, { wide = false, onMount } = {}) {
  close();
  const bg = document.createElement('div');
  bg.className = 'modal-bg';
  bg.innerHTML = `<div class="modal" style="${wide ? 'width:min(1000px,100%)' : ''}">
    <div class="pad" style="border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:12px;position:sticky;top:0;background:var(--card);z-index:2;border-radius:18px 18px 0 0">
      <h3 style="font-size:17px">${esc(title)}</h3>
      <button class="btn btn-soft btn-icon" data-x>✕</button></div>
    <div class="pad" data-body>${html}</div></div>`;
  bg.addEventListener('click', e => { if (e.target === bg || e.target.closest('[data-x]')) close(); });
  document.body.appendChild(bg);
  document.body.style.overflow = 'hidden';
  onMount?.(bg.querySelector('[data-body]'), close);
  return close;
  function close() {
    document.querySelectorAll('.modal-bg').forEach(m => m.remove());
    document.body.style.overflow = '';
  }
}
export const closeModal = () => {
  document.querySelectorAll('.modal-bg').forEach(m => m.remove());
  document.body.style.overflow = '';
};
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

export function confirmDialog(title, message, onYes, yesLabel = 'Confirm') {
  modal(title, `<p class="body-c">${esc(message)}</p>
    <div class="row mt" style="justify-content:flex-end">
      <button class="btn btn-ghost" data-no>Cancel</button>
      <button class="btn btn-danger" data-yes>${esc(yesLabel)}</button></div>`,
    { onMount(box, close) {
      box.querySelector('[data-no]').onclick = close;
      box.querySelector('[data-yes]').onclick = () => { close(); onYes(); };
    } });
}

/* ------------------------------------------------------- primitives -- */
export const kpi = (label, value, sub = '', tone = '') =>
  `<div class="kpi ${tone}"><div class="kl">${esc(label)}</div>
   <div class="kv">${value}</div>${sub ? `<div class="ks">${sub}</div>` : ''}</div>`;

export const card = (title, body, actions = '') =>
  `<div class="card pad">${title ? `<div class="card-h"><div class="card-t">${title}</div>${actions}</div>` : ''}${body}</div>`;

export const chartCard = (title, id, { height = 250, note = '', actions = '' } = {}) =>
  `<div class="card pad"><div class="card-h"><div class="card-t">${title}</div>
   ${actions || (note ? `<span class="xs muted">${note}</span>` : '')}</div>
   <div style="height:${height}px;position:relative"><canvas id="${id}"></canvas></div></div>`;

export const empty = (icon, title, sub, cta = '') =>
  `<div class="empty"><div class="big">${icon}</div><h3 style="font-size:17px">${esc(title)}</h3>
   <p class="sm" style="max-width:420px;margin:7px auto 15px">${sub}</p>${cta}</div>`;

export const loading = (n = 4) =>
  `<div class="grid g4">${'<div class="skel" style="height:86px"></div>'.repeat(n)}</div>
   <div class="skel" style="height:280px;margin-top:16px"></div>`;

export const alert = (kind, html) => {
  const ic = { err: '⚠️', warn: '⚠️', info: 'ℹ️', ok: '✅' }[kind] || 'ℹ️';
  return `<div class="alert a-${kind}"><span>${ic}</span><div>${html}</div></div>`;
};

export const statusBadge = (s) => {
  const m = { paid: 'b-green', unpaid: 'b-orange', partial: 'b-medium', cancelled: 'b-low',
              draft: 'b-low', active: 'b-green', trialing: 'b-teal', past_due: 'b-red',
              none: 'b-low', suspended: 'b-red' };
  return `<span class="badge ${m[s] || 'b-low'}"><span class="dot"></span>${esc(String(s || '—').replace('_', ' '))}</span>`;
};

export function table(cols, rows, { empty: emptyMsg = 'Nothing here yet.' } = {}) {
  if (!rows.length) return `<div class="empty sm">${esc(emptyMsg)}</div>`;
  return `<div class="tw"><table><thead><tr>${cols.map(c =>
    `<th class="${c.align === 'right' ? 'r' : ''}">${esc(c.label)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r => `<tr${r._click ? ` style="cursor:pointer" data-click="${esc(r._click)}"` : ''}>
      ${cols.map(c => `<td class="${c.align === 'right' ? 'r' : ''} ${c.mono ? 'mono' : ''}">${c.render(r)}</td>`).join('')}
    </tr>`).join('')}</tbody></table></div>`;
}

/* --------------------------------------------------------- app shell - */
const NAV = [
  { s: 'Overview' },
  { h: '/app', i: '◳', t: 'Dashboard' },
  { h: '/app/cost-leaks', i: '🔍', t: 'Cost Leaks' },
  { h: '/app/upload', i: '📤', t: 'Upload Data' },
  { s: 'Billing & GST' },
  { h: '/app/invoices', i: '🧾', t: 'Invoices' },
  { h: '/app/products', i: '📦', t: 'Products & Cost' },
  { h: '/app/customers', i: '👥', t: 'Customers' },
  { h: '/app/gst', i: '🏛️', t: 'GST & Profit' },
  { s: 'Tools' },
  { h: '/app/calculator', i: '⏱️', t: 'Manual Cost' },
  { h: '/app/subscriptions', i: '💳', t: 'SaaS Analyzer' },
  { h: '/app/reports', i: '📄', t: 'Reports' },
  { s: 'Account' },
  { h: '/app/plans', i: '⚡', t: 'Plan & Billing' },
  { h: '/app/settings', i: '⚙️', t: 'Settings' },
];

export function shell(title, subtitle, body, actions = '') {
  const u = state.user || {};
  const sub = state.subscription;
  const isAdmin = u.role === 'superadmin';
  const initials = (u.name || 'U').split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase();
  const here = location.pathname;

  const nav = NAV.map(n => n.s
    ? `<div class="side-sec">${n.s}</div>`
    : `<a href="${n.h}" class="${here === n.h ? 'on' : ''}"><span class="ic">${n.i}</span>${n.t}</a>`).join('');

  const trialBanner = sub && sub.status === 'trialing'
    ? `<a href="/app/plans" class="badge b-teal" style="padding:5px 11px">⏳ Trial · ${sub.days_left} days left</a>` : '';

  document.getElementById('app').innerHTML = `
  <div class="app">
    <aside class="side" id="side">
      <div class="side-brand"><span class="logo">◈</span> CostLeak<span style="color:var(--teal)">AI</span></div>
      ${nav}
      ${isAdmin ? `<div class="side-sec">Platform</div>
        <a href="/admin" class="${here.startsWith('/admin') ? 'on' : ''}"><span class="ic">🛡️</span>Admin Console</a>` : ''}
      <div class="side-foot">
        <div class="row" style="gap:9px">
          <div class="avatar">${esc(initials)}</div>
          <div style="min-width:0;flex:1">
            <div class="sm" style="color:#fff;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(u.name || '')}</div>
            <div class="xs" style="color:#8098B6;text-transform:capitalize">${esc(u.role || '')}</div>
          </div>
          <button class="btn btn-icon" style="background:rgba(255,255,255,.08);color:#C9D9EE" title="Sign out" data-logout>⎋</button>
        </div>
      </div>
    </aside>
    <div class="main">
      <div class="topbar">
        <div class="row">
          <button class="btn btn-soft btn-icon burger" data-burger>☰</button>
          <div>
            <div style="font-weight:720;font-size:15px">${esc(state.company?.name || 'CostLeak AI')}</div>
            <div class="xs muted">${esc(state.company?.gstin || 'GSTIN not set')} · ${esc(sub?.plan?.name || 'No plan')}</div>
          </div>
        </div>
        <div class="row">${trialBanner}
          <button class="btn btn-soft btn-icon" data-theme-btn title="Toggle theme">◐</button>
          <a class="btn btn-teal btn-sm" href="/app/invoices/new">+ New Invoice</a>
        </div>
      </div>
      <div class="page view-enter" id="view">
        <div class="page-h row-b">
          <div><h1>${esc(title)}</h1>${subtitle ? `<p>${subtitle}</p>` : ''}</div>
          <div class="row no-print">${actions}</div>
        </div>
        <div id="body">${body}</div>
      </div>
    </div>
  </div>`;

  document.querySelector('[data-logout]').onclick = logout;
  document.querySelector('[data-theme-btn]').onclick = toggleTheme;
  document.querySelector('[data-burger]').onclick = () =>
    document.getElementById('side').classList.toggle('open');
  document.querySelectorAll('.side a').forEach(a =>
    a.addEventListener('click', () => document.getElementById('side').classList.remove('open')));
  return document.getElementById('body');
}

/* Replace just the body of the current shell (keeps the sidebar untouched). */
export const setBody = (html) => { const b = document.getElementById('body'); if (b) b.innerHTML = html; return b; };

/* Serialise a form into an object. */
export function formData(root) {
  const out = {};
  root.querySelectorAll('[name]').forEach(el => {
    out[el.name] = el.type === 'checkbox' ? el.checked
      : el.type === 'number' ? (el.value === '' ? 0 : parseFloat(el.value))
      : el.value;
  });
  return out;
}

export function busy(btn, on, label) {
  if (!btn) return;
  if (on) {
    btn.dataset.label = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spin"></span>${label ? ' ' + label : ''}`;
  } else {
    btn.disabled = false;
    if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
  }
}

export const money = (n) => `<span class="num">${inr(n)}</span>`;
export const moneyShort = (n) => `<span class="num">${inrShort(n)}</span>`;
