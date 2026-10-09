/* Bootstrap: theme → session → routes → first render. */
import { route, render, initTheme, restoreSession, go, state } from './core.js';

initTheme();
restoreSession();

/* Views are code-split: each route imports its module on first visit, so the
   landing page ships almost nothing and the app pages load in a few KB. */
const V = (mod, name) => async (params) => (await import(mod))[name](params);

// public
route('/',        V('./views/landing.js', 'landing'),  { public: true });
route('/login',   V('./views/auth.js', 'login'),       { public: true });
route('/signup',  V('./views/auth.js', 'signup'),      { public: true });

// app (auth required)
route('/app',                  V('./views/dashboard.js', 'dashboard'),   { auth: true });
route('/app/cost-leaks',       V('./views/costleak.js', 'costLeaks'),    { auth: true });
route('/app/upload',           V('./views/upload.js', 'upload'),         { auth: true });
route('/app/calculator',       V('./views/costleak.js', 'calculator'),   { auth: true });
route('/app/subscriptions',    V('./views/costleak.js', 'subscriptions'),{ auth: true });
route('/app/reports',          V('./views/costleak.js', 'reports'),      { auth: true });
route('/app/invoices',         V('./views/invoices.js', 'invoiceList'),  { auth: true });
route('/app/invoices/new',     V('./views/invoices.js', 'invoiceNew'),   { auth: true });
route('/app/invoices/:id',     V('./views/invoices.js', 'invoiceDetail'),{ auth: true });
route('/app/products',         V('./views/products.js', 'products'),     { auth: true });
route('/app/customers',        V('./views/products.js', 'customers'),    { auth: true });
route('/app/gst',              V('./views/gst.js', 'gst'),               { auth: true });
route('/app/plans',            V('./views/plans.js', 'plans'),           { auth: true });
route('/app/settings',         V('./views/settings.js', 'settings'),     { auth: true });

// platform owner
route('/admin', V('./views/admin.js', 'admin'), { auth: true, admin: true });

// 404
route('*', () => {
  document.getElementById('app').innerHTML = `
    <div style="min-height:100vh;display:grid;place-items:center;background:#060F1E;color:#C2D4E8;text-align:center">
      <div><div style="font-size:52px;font-weight:800;color:#0FB5A0">404</div>
        <p style="margin:10px 0 20px;color:#9DB6D2">That page does not exist.</p>
        <a class="btn btn-teal" href="${state.token ? '/app' : '/'}">${state.token ? 'Back to dashboard' : 'Back to home'}</a>
      </div></div>`;
}, { public: true });

// Signed-in users landing on "/" go straight to the dashboard.
if (state.token && location.pathname === '/') go('/app', { replace: true });
else render();

// Warm the most likely next view once the browser is idle.
(window.requestIdleCallback || setTimeout)(() => {
  if (state.token) import('./views/dashboard.js');
  else import('./views/auth.js');
}, 1200);
