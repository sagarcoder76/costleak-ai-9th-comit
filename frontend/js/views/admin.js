/* Platform owner console — who signed up, who pays, how they use it. */
import { api, inr, inrShort, num, pct, esc, fdate, ago } from '../core.js';
import { shell, setBody, kpi, table, chartCard, alert, statusBadge, modal, toast } from '../ui.js';
import * as ch from '../charts.js';

export async function admin() {
  let tab = 'overview';
  shell('Platform admin', 'Every company on CostLeak AI — subscriptions, revenue and usage.',
    '<div class="skel" style="height:340px"></div>');

  const d = await api('/api/admin/dashboard');

  function paint() {
    setBody(`
      ${alert('info', `<strong>Owner view.</strong> You are signed in as a platform superadmin. This page aggregates
        every tenant; it is not visible to company users.`)}
      <div class="grid g5 mt">
        ${kpi('Companies', num(d.kpis.companies), `${d.kpis.new_30d} joined in 30 days`, 'teal')}
        ${kpi('Paying', num(d.kpis.paying), `${pct(d.kpis.conversion)} trial→paid`, 'green')}
        ${kpi('MRR', inrShort(d.kpis.mrr), `ARR ${inrShort(d.kpis.mrr * 12)}`, 'violet')}
        ${kpi('Total collected', inrShort(d.kpis.revenue_total), `${d.kpis.payment_count} payments`, 'orange')}
        ${kpi('Active trials', num(d.kpis.trialing), `${d.kpis.expiring_soon} expiring this week`, 'grey')}
      </div>

      <div class="tabs mt">
        ${[['overview', 'Growth & revenue'], ['companies', 'Companies'], ['usage', 'Product usage'], ['payments', 'Payments']]
          .map(([k, l]) => `<button data-tab="${k}" class="${tab === k ? 'on' : ''}">${l}</button>`).join('')}
      </div>
      <div id="tb" class="mt"></div>`);

    document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => { tab = b.dataset.tab; paint(); });
    const tb = document.getElementById('tb');
    ch.clearCharts();

    if (tab === 'overview') {
      tb.innerHTML = `
        <div class="grid g2">
          ${chartCard('New companies per month', 'a1', { height: 260 })}
          ${chartCard('Revenue collected per month', 'a2', { height: 260 })}
        </div>
        <div class="grid g3 mt">
          ${chartCard('Companies by plan', 'a3', { height: 250 })}
          ${chartCard('Subscription status', 'a4', { height: 250 })}
          ${chartCard('Companies by industry', 'a5', { height: 250 })}
        </div>
        <div class="grid g2 mt">
          <div class="card pad">
            <div class="card-t" style="margin-bottom:10px">Plan economics</div>
            ${table([
              { label: 'Plan', render: r => `<strong>${esc(r.name)}</strong>` },
              { label: 'Companies', align: 'right', mono: true, render: r => r.companies },
              { label: 'Price', align: 'right', mono: true, render: r => inr(r.price_monthly) },
              { label: 'MRR', align: 'right', mono: true, render: r => `<strong>${inr(r.mrr)}</strong>` },
              { label: 'Share', align: 'right', render: r => `<span class="badge b-teal">${pct(r.share)}</span>` },
            ], d.by_plan)}
          </div>
          <div class="card pad">
            <div class="card-t" style="margin-bottom:10px">Trials ending soon</div>
            ${table([
              { label: 'Company', render: r => esc(r.name) },
              { label: 'Signed up', render: r => fdate(r.created_at) },
              { label: 'Trial ends', render: r => `<strong>${fdate(r.trial_ends_at)}</strong>` },
              { label: 'Activity', align: 'right', render: r => `<span class="sm">${r.events} events</span>` },
            ], d.expiring, { empty: 'No trials ending in the next 7 days.' })}
          </div>
        </div>`;
      ch.draw(() => ch.bar('a1', d.charts.signups.map(x => ({ label: x.month, value: x.count }))));
      ch.draw(() => ch.line('a2', d.charts.revenue.map(x => ({ label: x.month, value: Math.round(x.amount) }))));
      ch.draw(() => ch.donut('a3', d.charts.by_plan, { centerLabel: 'companies' }));
      ch.draw(() => ch.donut('a4', d.charts.by_status, { centerLabel: 'accounts' }));
      ch.draw(() => ch.hbar('a5', d.charts.by_industry));
    }

    if (tab === 'companies') {
      tb.innerHTML = `
        <div class="card pad">
          <div class="card-h"><div class="card-t">All companies</div>
            <input id="q" placeholder="Search company…" style="width:220px"></div>
          <div id="ct"></div>
        </div>`;
      const render = (q = '') => {
        document.getElementById('ct').innerHTML = table([
          { label: 'Company', render: c => `<strong>${esc(c.name)}</strong>
              <div class="xs muted">${esc(c.owner_email || '')} · ${esc(c.industry || '—')}</div>` },
          { label: 'Plan', render: c => `<span class="badge ${c.subscription_status === 'active' ? 'b-green' : 'b-orange'}">${esc(c.plan_name)}</span>
              <div class="xs muted">${esc(c.subscription_status)}</div>` },
          { label: 'Joined', render: c => `${fdate(c.created_at)}<div class="xs muted">${ago(c.created_at)}</div>` },
          { label: 'Users', align: 'right', mono: true, render: c => c.users },
          { label: 'Invoices', align: 'right', mono: true, render: c => c.invoices },
          { label: 'Analyses', align: 'right', mono: true, render: c => c.analyses },
          { label: 'Invoiced value', align: 'right', mono: true, render: c => inrShort(c.invoiced_value) },
          { label: 'Paid us', align: 'right', mono: true, render: c => `<strong style="color:var(--green)">${inr(c.paid_total)}</strong>` },
          { label: 'Last active', align: 'right', render: c => `<span class="sm">${c.last_event_at ? ago(c.last_event_at) : '—'}</span>` },
          { label: '', align: 'right', render: c => `<button class="btn btn-soft btn-sm" data-c="${c.id}">View</button>` },
        ], d.companies.filter(c => !q || c.name.toLowerCase().includes(q.toLowerCase())));
        document.querySelectorAll('[data-c]').forEach(b => b.onclick = () => detail(b.dataset.c));
      };
      render();
      document.getElementById('q').oninput = e => render(e.target.value);
    }

    if (tab === 'usage') {
      tb.innerHTML = `
        <div class="grid g4">
          ${kpi('Invoices created', num(d.usage.invoices), 'across all tenants', 'teal')}
          ${kpi('Analyses run', num(d.usage.analyses), `${d.usage.findings} findings produced`, 'violet')}
          ${kpi('Products tracked', num(d.usage.products), 'in cost databases', 'green')}
          ${kpi('Waste identified', inrShort(d.usage.waste_found), 'for our customers, per month', 'red')}
        </div>
        <div class="grid g2 mt">
          ${chartCard('Feature usage — events in the last 30 days', 'u1', { height: 280 })}
          ${chartCard('Daily active companies', 'u2', { height: 280 })}
        </div>
        <div class="card pad mt">
          <div class="card-t" style="margin-bottom:10px">Most used features</div>
          ${table([
            { label: 'Feature', render: r => `<strong>${esc(r.feature)}</strong>` },
            { label: 'Events', align: 'right', mono: true, render: r => num(r.count) },
            { label: 'Companies using it', align: 'right', mono: true, render: r => r.companies },
            { label: 'Adoption', align: 'right', render: r => `<span class="badge ${r.adoption >= 60 ? 'b-green' : r.adoption >= 30 ? 'b-orange' : 'b-red'}">${pct(r.adoption)}</span>` },
          ], d.usage.features)}
          <div class="help mt-s">Adoption = share of companies that used the feature at least once.
            Low adoption on a paid feature usually means it is hard to find, not unwanted.</div>
        </div>
        <div class="card pad mt">
          <div class="card-t" style="margin-bottom:10px">Recent activity</div>
          ${table([
            { label: 'When', render: r => `${ago(r.created_at)}<div class="xs muted">${fdate(r.created_at)}</div>` },
            { label: 'Company', render: r => esc(r.company_name) },
            { label: 'Event', render: r => `<span class="badge b-grey">${esc(r.event)}</span>` },
            { label: 'Detail', render: r => `<span class="sm muted">${esc(r.detail || '')}</span>` },
          ], d.usage.recent)}
        </div>`;
      ch.draw(() => ch.hbar('u1', d.usage.features.map(f => ({ label: f.feature, value: f.count }))));
      ch.draw(() => ch.line('u2', d.usage.daily.map(x => ({ label: x.date.slice(5), value: x.companies })), { color: '#7C5CFF' }));
    }

    if (tab === 'payments') {
      tb.innerHTML = `
        <div class="card pad">
          <div class="card-t" style="margin-bottom:10px">All payments</div>
          ${table([
            { label: 'Date', render: p => `${fdate(p.created_at)}<div class="xs muted">${ago(p.created_at)}</div>` },
            { label: 'Company', render: p => `<strong>${esc(p.company_name)}</strong>` },
            { label: 'Plan', render: p => `${esc(p.plan_name)} <span class="xs muted">${esc(p.billing_cycle)}</span>` },
            { label: 'Reference', render: p => `<span class="mono xs">${esc(p.reference || p.id)}</span>` },
            { label: 'Mode', render: p => `<span class="badge ${p.method === 'simulated' ? 'b-grey' : 'b-teal'}">${esc(p.method || 'razorpay')}</span>` },
            { label: 'Amount', align: 'right', mono: true, render: p => `<strong>${inr(p.amount)}</strong>` },
            { label: 'Status', align: 'right', render: p => statusBadge(p.status) },
          ], d.payments, { empty: 'No payments recorded yet.' })}
        </div>`;
    }
  }

  async function detail(id) {
    modal('Company', '<div class="skel" style="height:220px"></div>');
    try {
      const c = await api('/api/admin/companies/' + id);
      document.querySelector('.modal-body').innerHTML = `
        <h3 style="font-size:19px">${esc(c.company.name)}</h3>
        <div class="sm muted">${esc(c.company.gstin || 'No GSTIN')} · ${esc(c.company.industry || '—')} ·
          joined ${fdate(c.company.created_at)}</div>
        <div class="grid g3 mt">
          ${kpi('Plan', esc(c.company.plan_name), esc(c.company.subscription_status), 'teal')}
          ${kpi('Paid us', inr(c.paid_total), `${c.payments.length} payments`, 'green')}
          ${kpi('Waste found', inrShort(c.waste_found), 'for this tenant', 'red')}
        </div>
        <div class="grid g2 mt">
          <div><div class="card-t" style="margin-bottom:8px">Users</div>
            ${table([{ label: 'Name', render: u => esc(u.name) },
                     { label: 'Role', render: u => `<span class="badge b-grey">${esc(u.role)}</span>` },
                     { label: 'Last seen', align: 'right', render: u => u.last_login_at ? ago(u.last_login_at) : '—' }], c.users)}</div>
          <div><div class="card-t" style="margin-bottom:8px">Usage</div>
            <div class="stat-line"><span>Invoices</span><strong>${num(c.stats.invoices)}</strong></div>
            <div class="stat-line"><span>Invoiced value</span><strong>${inr(c.stats.invoiced_value)}</strong></div>
            <div class="stat-line"><span>Products</span><strong>${num(c.stats.products)}</strong></div>
            <div class="stat-line"><span>Customers</span><strong>${num(c.stats.customers)}</strong></div>
            <div class="stat-line"><span>Analyses run</span><strong>${num(c.stats.analyses)}</strong></div>
            <div class="stat-line"><span>Events (30d)</span><strong>${num(c.stats.events_30d)}</strong></div>
          </div>
        </div>`;
    } catch (e) { toast(e.message, 'err'); }
  }

  paint();
}
