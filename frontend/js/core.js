/* CostLeak AI — core: state, API client, router, formatting.
   No framework, no build step. Views are plain functions returning HTML. */

/* ----------------------------------------------------------- state --- */
const LS = {
  token: 'cl.token', theme: 'cl.theme', analysis: 'cl.analysis',
};
export const state = {
  user: null, company: null, subscription: null, usage: null, plans: [],
  token: localStorage.getItem(LS.token) || '',
  cache: new Map(),
};

export function setSession(data) {
  if (data.token) { state.token = data.token; localStorage.setItem(LS.token, data.token); }
  state.user = data.user || state.user;
  state.company = data.company || state.company;
  state.subscription = data.subscription || state.subscription;
  state.usage = data.usage || state.usage;
  state.plans = data.plans || state.plans;
}
export function logout() {
  state.token = ''; state.user = null; state.company = null; state.cache.clear();
  localStorage.removeItem(LS.token); localStorage.removeItem(LS.analysis);
  // Expired sessions land on the sign-in page (with an explanation); a
  // deliberate sign-out goes to the marketing site.
  go(sessionStorage.getItem('cl.signedout') ? '/login' : '/');
}

/* ------------------------------------------------------------- api --- */
export async function api(path, { method = 'GET', body, raw, headers = {} } = {}) {
  const opts = { method, headers: { ...headers } };
  if (state.token) opts.headers.Authorization = `Bearer ${state.token}`;
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (raw) return res;
  const ct = res.headers.get('content-type') || '';
  const data = ct.includes('json') ? await res.json() : await res.text();
  if (!res.ok) {
    if (res.status === 401 && state.token) {
      // Session no longer valid (expired, or the server restarted). Say so
      // instead of silently bouncing the user back to the landing page.
      sessionStorage.setItem('cl.signedout', data?.error || 'Your session has ended. Please sign in again.');
      logout();
    }
    const err = new Error((data && (data.error || data.message)) || `Request failed (${res.status})`);
    err.status = res.status; err.data = data;
    throw err;
  }
  return data;
}

/** GET with a short in-memory cache — makes back/forward navigation instant. */
export async function cached(path, ttl = 20000) {
  const hit = state.cache.get(path);
  if (hit && Date.now() - hit.t < ttl) return hit.v;
  const v = await api(path);
  state.cache.set(path, { t: Date.now(), v });
  return v;
}
export const bust = (prefix = '') => {
  [...state.cache.keys()].forEach(k => { if (!prefix || k.startsWith(prefix)) state.cache.delete(k); });
};

/* -------------------------------------------------------- formatting - */
const nfINR = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
const nfINR2 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nfN = new Intl.NumberFormat('en-IN');

export const inr = (n) => nfINR.format(Number(n || 0));
export const inr2 = (n) => nfINR2.format(Number(n || 0));
export const num = (n) => nfN.format(Number(n || 0));
export function inrShort(n) {
  const v = Math.abs(Number(n || 0)), s = Number(n) < 0 ? '-' : '';
  if (v >= 1e7) return `${s}₹${(v / 1e7).toFixed(2)} Cr`;
  if (v >= 1e5) return `${s}₹${(v / 1e5).toFixed(2)} L`;
  if (v >= 1e3) return `${s}₹${(v / 1e3).toFixed(1)}K`;
  return `${s}₹${v.toFixed(0)}`;
}
export const pct = (n, dp = 1) => `${Number(n || 0).toFixed(dp)}%`;
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export function fdate(d, opts = {}) {
  if (!d) return '—';
  const dt = new Date(d);
  if (isNaN(dt)) return String(d);
  return dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', ...opts });
}
export function ago(d) {
  if (!d) return 'never';
  const s = (Date.now() - new Date(d).getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 2592000) return `${Math.floor(s / 86400)}d ago`;
  return fdate(d);
}
export const todayISO = () => new Date().toISOString().slice(0, 10);
export const monthISO = () => new Date().toISOString().slice(0, 7);
export const debounce = (fn, ms = 350) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

/* ----------------------------------------------------------- router -- */
const routes = [];
export const route = (path, handler, opts = {}) => routes.push({ path, handler, ...opts });

function match(pathname) {
  for (const r of routes) {
    if (r.path === pathname) return { r, params: {} };
    if (r.path.includes(':')) {
      const a = r.path.split('/'), b = pathname.split('/');
      if (a.length !== b.length) continue;
      const params = {};
      let ok = true;
      for (let i = 0; i < a.length; i++) {
        if (a[i].startsWith(':')) params[a[i].slice(1)] = decodeURIComponent(b[i]);
        else if (a[i] !== b[i]) { ok = false; break; }
      }
      if (ok) return { r, params };
    }
  }
  return null;
}

let bar;
export function progress(on) {
  if (!bar) { bar = document.createElement('div'); bar.className = 'nprogress'; document.body.appendChild(bar); }
  if (on) { bar.classList.add('go'); bar.style.width = '72%'; }
  else { bar.style.width = '100%'; setTimeout(() => { bar.classList.remove('go'); bar.style.width = '0'; }, 220); }
}

export function go(path, replace = false) {
  if (location.pathname === path) return render();
  history[replace ? 'replaceState' : 'pushState']({}, '', path);
  render();
}

let currentCleanup = null;
export async function render() {
  const hit = match(location.pathname) || match('/404');
  const app = document.getElementById('app');
  if (!hit) { app.innerHTML = '<div class="empty"><div class="big">🧭</div><h3>Page not found</h3></div>'; return; }
  const { r, params } = hit;

  if (r.auth && !state.token) return go('/login', true);
  if (r.admin && state.user?.role !== 'superadmin') return go('/app', true);

  if (currentCleanup) { try { currentCleanup(); } catch {} currentCleanup = null; }
  progress(true);
  try {
    const out = await r.handler(params);
    if (typeof out === 'function') currentCleanup = out;
  } catch (e) {
    console.error(e);
    if (e.status !== 401) {
      document.getElementById('view')?.insertAdjacentHTML('afterbegin',
        `<div class="alert a-err mt"><span>⚠️</span><div><strong>Something went wrong.</strong><br>${esc(e.message)}</div></div>`);
    }
  } finally { progress(false); window.scrollTo({ top: 0 }); }
}

/* Intercept internal links so navigation never does a full page reload. */
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href^="/"]');
  if (!a || a.target === '_blank' || a.hasAttribute('download') || e.metaKey || e.ctrlKey) return;
  e.preventDefault();
  go(a.getAttribute('href'));
});
window.addEventListener('popstate', render);

/* ------------------------------------------------------------ theme -- */
export function initTheme() {
  const saved = localStorage.getItem(LS.theme);
  if (saved) document.documentElement.dataset.theme = saved;
}
export function toggleTheme() {
  const now = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = now;
  localStorage.setItem(LS.theme, now);
  render();
}

/* --------------------------------------------------------- analysis -- */
export const setAnalysisId = (id) => localStorage.setItem(LS.analysis, id);
export const getAnalysisId = () => localStorage.getItem(LS.analysis);

/* ---------------------------------------------------------- session -- */
export async function restoreSession() {
  if (!state.token) return false;
  try { setSession(await api('/api/auth/me')); return true; }
  catch { return false; }
}

/* --------------------------------------------------------- constants - */
export const PRIO = { Critical: 'b-critical', High: 'b-high', Medium: 'b-medium', Low: 'b-low' };
export const CAT_ICON = {
  'Duplicate Payment': '🧾', 'Unused License': '🎫', 'Duplicate Software': '🧩',
  'Price Increase': '📈', 'Manual Work': '⏱️', 'Overtime': '🌙', 'Unused Resource': '📦',
};
export const STATUSES = ['Identified', 'In Review', 'Approved', 'Actioned', 'Verified'];
export const STATE_LIST = {
  '01': 'Jammu & Kashmir', '02': 'Himachal Pradesh', '03': 'Punjab', '04': 'Chandigarh',
  '05': 'Uttarakhand', '06': 'Haryana', '07': 'Delhi', '08': 'Rajasthan', '09': 'Uttar Pradesh',
  '10': 'Bihar', '11': 'Sikkim', '12': 'Arunachal Pradesh', '13': 'Nagaland', '14': 'Manipur',
  '15': 'Mizoram', '16': 'Tripura', '17': 'Meghalaya', '18': 'Assam', '19': 'West Bengal',
  '20': 'Jharkhand', '21': 'Odisha', '22': 'Chhattisgarh', '23': 'Madhya Pradesh', '24': 'Gujarat',
  '26': 'Dadra & Nagar Haveli and Daman & Diu', '27': 'Maharashtra', '29': 'Karnataka', '30': 'Goa',
  '31': 'Lakshadweep', '32': 'Kerala', '33': 'Tamil Nadu', '34': 'Puducherry',
  '35': 'Andaman & Nicobar', '36': 'Telangana', '37': 'Andhra Pradesh', '38': 'Ladakh', '97': 'Other',
};
export const GST_RATES = [0, 0.25, 3, 5, 12, 18, 28];
