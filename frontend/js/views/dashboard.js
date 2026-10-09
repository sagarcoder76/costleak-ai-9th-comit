/* Unified company dashboard: cost leaks + GST/revenue in one view. */
import { api, cached, state, inr, inrShort, pct, esc, fdate, monthISO, go } from '../core.js';
import { shell, kpi, chartCard, card, empty, loading, alert, money, table, statusBadge } from '../ui.js';
import * as ch from '../charts.js';

export async function dashboard() {
  shell('Dashboard', 'Everything that matters this month, in one place.',
    loading(5),
    `<a class="btn btn-ghost btn-sm" href="/app/upload">📤 Upload expenses</a>
     <a class="btn btn-primary btn-sm" href="/app/reports">📄 Executive report</a>`);

  const [leak, inv, gst, profit] = await Promise.all([
    api('/api/analysis/latest').catch(() => null),
    cached('/api/invoices?limit=400').catch(() => ({ invoices: [], summary: {} })),
    cached(`/api/gst/summary?month=${monthISO()}`).catch(() => null),
    cached(`/api/gst/profit?month=${monthISO()}`).catch(() => null),
  ]);

  const k = leak?.result?.kpis;
  const findings = leak?.result?.findings || [];
  const sales = (inv.invoices || []).filter(i => i.doc_type === 'sale' && i.status !== 'cancelled');
  const outstanding = inv.summary?.outstanding || 0;

  const body = document.getElementById('body');
  body.innerHTML = `
  ${!leak ? alert('info', `<strong>No cost-leak analysis yet.</strong> Upload your expense workbook or
      <a href="/app/upload" style="font-weight:700">load the sample company data</a> to populate the leak side of this dashboard.`) + '<div class="mt"></div>' : ''}

  <div class="grid g5">
    ${kpi('Revenue this month', inrShort(profit?.revenue || 0),
          `${profit?.invoice_count || 0} invoices raised`, 'teal')}
    ${kpi('Gross profit', inrShort(profit?.gross_profit || 0),
          `${pct(profit?.margin_pct || 0)} margin`, 'green')}
    ${kpi('Estimated monthly waste', inrShort(k?.monthly_waste || 0),
          k ? `${pct(k.waste_pct)} of monthly spend` : 'no analysis yet', 'red')}
    ${kpi('Net GST payable', inrShort(gst?.net_payable || 0),
          `output ${inrShort(gst?.output_tax?.total || 0)} − ITC ${inrShort(gst?.input_tax?.total || 0)}`, 'violet')}
    ${kpi('Outstanding receivables', inrShort(outstanding),
          `${sales.filter(i => ['unpaid', 'partial'].includes(i.status)).length} unpaid invoices`, 'orange')}
  </div>

  <div class="grid g2 mt">
    ${chartCard('Revenue vs cost — last 6 months', 'c-rev', { height: 250 })}
    ${chartCard('Estimated waste by leak type', 'c-waste', { height: 250, note: 'per month' })}
  </div>

  <div class="grid mt" style="grid-template-columns:1.35fr 1fr">
    <div class="card pad">
      <div class="card-h"><div class="card-t">Top savings opportunities</div>
        <a class="btn btn-ghost btn-sm" href="/app/cost-leaks">View all ${findings.length} →</a></div>
      ${findings.length ? `<div class="col" style="gap:9px">
        ${findings.slice(0, 5).map((f, i) => `
          <div class="card finding p-${f.priority.toLowerCase()}" style="box-shadow:none;padding:11px 13px">
            <div class="row-b" style="align-items:flex-start;gap:10px">
              <div style="min-width:0">
                <div class="row" style="gap:6px">
                  <span class="badge ${{Critical:'b-critical',High:'b-high',Medium:'b-medium',Low:'b-low'}[f.priority]}">${f.priority}</span>
                  <span class="xs muted">${esc(f.category)} · ${esc(f.department)}</span></div>
                <div style="font-weight:620;font-size:13.6px;margin-top:5px">${i + 1}. ${esc(f.title)}</div>
              </div>
              <div class="right" style="white-space:nowrap">
                <div style="font-weight:800;color:var(--red)">${inr(f.monthly_waste)}</div>
                <div class="xs muted">per month</div></div>
            </div></div>`).join('')}</div>`
        : empty('🔍', 'No findings yet', 'Upload an expense workbook to detect duplicate payments, unused seats and overlapping tools.',
                '<a class="btn btn-primary btn-sm" href="/app/upload">Upload data</a>')}
    </div>

    <div class="col" style="gap:16px">
      <div class="card pad">
        <div class="card-h"><div class="card-t">Margin alerts</div>
          <a class="btn btn-ghost btn-sm" href="/app/gst">Details →</a></div>
        ${(profit?.alerts || []).length ? `<div class="col" style="gap:8px">
          ${profit.alerts.slice(0, 4).map(a => `
            <div class="alert a-${a.level === 'critical' ? 'err' : a.level === 'warning' ? 'warn' : 'info'}" style="padding:9px 11px">
              <span>${a.level === 'critical' ? '🔴' : a.level === 'warning' ? '🟠' : 'ℹ️'}</span>
              <div><strong class="sm">${esc(a.title)}</strong>
                <div class="xs" style="opacity:.85">${esc(a.detail)}</div></div></div>`).join('')}</div>`
          : `<div class="empty sm" style="padding:24px">✅ Every product is selling above cost this month.</div>`}
      </div>
      <div class="card pad">
        <div class="card-t" style="margin-bottom:10px">Recent invoices</div>
        ${table([
          { label: 'Number', render: r => `<a href="/app/invoices/${r.id}" style="font-weight:650">${esc(r.number)}</a>` },
          { label: 'Customer', render: r => `<span class="sm">${esc((r.customer_name || '').slice(0, 20))}</span>` },
          { label: 'Amount', align: 'right', mono: true, render: r => inr(r.total) },
          { label: '', align: 'right', render: r => statusBadge(r.status) },
        ], sales.slice(0, 6), { empty: 'No invoices yet.' })}
        <a class="btn btn-soft btn-sm btn-block mt-s" href="/app/invoices">All invoices →</a>
      </div>
    </div>
  </div>

  <div class="grid g2 mt">
    ${chartCard('Spend by category (from uploaded expenses)', 'c-cat', { height: 240 })}
    ${chartCard('Top vendors by monthly cost', 'c-vendor', { height: 240 })}
  </div>`;

  // ---- charts
  const months = {};
  sales.forEach(i => {
    const m = (i.invoice_date || '').slice(0, 7);
    if (!m) return;
    months[m] = months[m] || { rev: 0, cost: 0 };
    months[m].rev += i.taxable_total || 0;
    months[m].cost += i.cost_total || 0;
  });
  const trend = Object.entries(months).sort().slice(-6)
    .map(([m, v]) => ({ label: m, value: Math.round(v.rev) }));

  ch.clearCharts();
  ch.draw(() => ch.line('c-rev', trend, { color: '#0FB5A0' }));
  ch.draw(() => ch.donut('c-waste', (leak?.result?.charts?.waste_by_category || []), { centerLabel: 'monthly waste' }));
  ch.draw(() => ch.donut('c-cat', (leak?.result?.charts?.spend_by_category || []).slice(0, 7), { centerLabel: 'monthly spend' }));
  ch.draw(() => ch.hbar('c-vendor', (leak?.result?.charts?.top_vendors || []).slice(0, 8)));
}
