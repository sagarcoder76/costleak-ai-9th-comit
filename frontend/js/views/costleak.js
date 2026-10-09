/* Cost-leak findings, calculator, subscription analyzer, reports. */
import { api, cached, state, inr, inrShort, pct, num, esc, fdate, CAT_ICON, PRIO } from '../core.js';
import { shell, setBody, kpi, table, chartCard, empty, alert, toast, modal } from '../ui.js';
import * as ch from '../charts.js';

/* ================================================ FINDINGS ========== */
export async function costLeaks() {
  shell('Cost leaks', 'Every finding shows its evidence and the exact formula behind the rupees.',
    '<div class="skel" style="height:340px"></div>',
    `<a class="btn btn-ghost btn-sm" href="/app/upload">📤 New upload</a>
     <a class="btn btn-primary btn-sm" href="/app/reports">📄 Export PDF</a>`);

  const data = await api('/api/analysis/latest').catch(() => null);
  if (!data) {
    return setBody(empty('🔍', 'No analysis yet',
      'Upload an expense workbook (or run the built-in sample company) to detect duplicate payments, unused seats, overlapping tools, price hikes and manual work.',
      '<a class="btn btn-teal" href="/app/upload">Upload data →</a>'));
  }

  const r = data.result, all = r.findings, k = r.kpis;
  let prio = '', cat = '', q = '';

  function paint() {
    const list = all.filter(f =>
      (!prio || f.priority === prio) &&
      (!cat || f.category === cat) &&
      (!q || (f.title + f.vendor + f.department).toLowerCase().includes(q.toLowerCase())));

    document.getElementById('list').innerHTML = list.length ? list.map((f, i) => `
      <div class="card finding p-${f.priority.toLowerCase()}">
        <div class="row-b" style="align-items:flex-start;gap:14px">
          <div style="min-width:0;flex:1">
            <div class="row" style="gap:7px;flex-wrap:wrap">
              <span class="badge ${PRIO[f.priority]}">${f.priority}</span>
              <span class="badge b-grey">${CAT_ICON[f.category] || '•'} ${esc(f.category)}</span>
              ${f.vendor ? `<span class="xs muted">${esc(f.vendor)}</span>` : ''}
              ${f.department ? `<span class="xs muted">· ${esc(f.department)}</span>` : ''}
            </div>
            <h3 style="font-size:15.5px;margin:8px 0 5px">${esc(f.title)}</h3>
            <p class="sm muted">${esc(f.explanation || '')}</p>
            <div class="card pad-s mt-s" style="box-shadow:none;background:var(--line-2);border:none">
              <div class="xs muted" style="font-weight:700;letter-spacing:.05em">HOW THIS WAS CALCULATED</div>
              <div class="sm mono" style="margin-top:4px;word-break:break-word">${esc(f.calculation)}</div>
            </div>
            <div class="row mt-s" style="gap:8px">
              <strong class="sm">Recommended action:</strong><span class="sm">${esc(f.recommended_action || '')}</span></div>
            ${f.evidence?.length ? `<details class="mt-s"><summary class="sm" style="cursor:pointer;color:var(--teal-ink);font-weight:650">
                View ${f.evidence.length} evidence row${f.evidence.length > 1 ? 's' : ''}</summary>
              <div class="mt-s">${table(
                Object.keys(f.evidence[0]).map(key => ({ label: key.replace(/_/g, ' '),
                  render: row => typeof row[key] === 'number' ? inr(row[key]) : esc(String(row[key] ?? '')) })),
                f.evidence)}</div></details>` : ''}
          </div>
          <div class="right" style="white-space:nowrap">
            <div class="xs muted">ESTIMATED SAVINGS</div>
            <div style="font-size:21px;font-weight:800;color:var(--red)">${inr(f.monthly_waste)}</div>
            <div class="xs muted">per month</div>
            <div class="sm" style="margin-top:6px;color:var(--green);font-weight:700">${inr(f.annual_waste || f.monthly_waste * 12)}/yr</div>
            <div class="xs muted" style="margin-top:7px">confidence</div>
            <span class="badge ${f.confidence === 'High' ? 'b-green' : f.confidence === 'Medium' ? 'b-orange' : 'b-grey'}">${esc(f.confidence)}</span>
          </div>
        </div>
      </div>`).join('')
      : empty('🎯', 'No findings match these filters', 'Try clearing the filters.');
  }

  setBody(`
    <div class="grid g4">
      ${kpi('Monthly spend analysed', inrShort(k.monthly_spend), `${k.months_covered || 1} month(s) of data`, 'teal')}
      ${kpi('Estimated monthly waste', inrShort(k.monthly_waste), pct(k.waste_pct) + ' of spend', 'red')}
      ${kpi('Annual opportunity', inrShort(k.annual_savings), 'if every action is taken', 'green')}
      ${kpi('Findings', all.length, `${all.filter(f => f.priority === 'Critical').length} critical`, 'orange')}
    </div>

    <div class="grid g2 mt">
      ${chartCard('Waste by category', 'c1', { height: 250 })}
      ${chartCard('Top vendors by monthly spend', 'c2', { height: 250 })}
    </div>

    <div class="card pad mt">
      <div class="card-h">
        <div class="row">
          <select id="p" style="width:140px"><option value="">All priorities</option>
            ${['Critical', 'High', 'Medium', 'Low'].map(x => `<option>${x}</option>`).join('')}</select>
          <select id="c" style="width:170px"><option value="">All categories</option>
            ${[...new Set(all.map(f => f.category))].map(x => `<option>${esc(x)}</option>`).join('')}</select>
        </div>
        <input id="q" placeholder="Search findings…" style="width:220px">
      </div>
      <div class="xs muted">Analysis run ${fdate(data.created_at)} · source: ${esc(data.source || 'upload')}</div>
    </div>

    <div class="col mt" style="gap:11px" id="list"></div>`);

  document.getElementById('p').onchange = e => { prio = e.target.value; paint(); };
  document.getElementById('c').onchange = e => { cat = e.target.value; paint(); };
  document.getElementById('q').oninput = e => { q = e.target.value; paint(); };
  paint();

  ch.clearCharts();
  ch.draw(() => ch.donut('c1', r.charts.waste_by_category, { centerLabel: 'monthly waste' }));
  ch.draw(() => ch.hbar('c2', r.charts.top_vendors.slice(0, 8)));
}

/* ============================================== CALCULATOR ========== */
export async function calculator() {
  shell('Savings calculator', 'A quick estimate before you upload anything — adjust the inputs and watch the numbers move.', `
    <div class="grid" style="grid-template-columns:1fr 1fr;gap:16px;align-items:start">
      <div class="card pad-l">
        <div class="card-t" style="margin-bottom:14px">Your numbers</div>
        <div id="inputs"></div>
        <div class="help mt">Defaults are conservative industry benchmarks for Indian SMBs. Replace them with
          your own figures — nothing here is stored.</div>
      </div>
      <div class="col" style="gap:16px">
        <div class="card pad-l center" style="background:linear-gradient(135deg,var(--navy),#16416F);color:#fff">
          <div class="xs" style="color:#9DB6D2;letter-spacing:.08em">ESTIMATED ANNUAL SAVINGS</div>
          <div id="big" style="font-size:42px;font-weight:800;letter-spacing:-.04em;margin:6px 0">₹0</div>
          <div class="sm" id="monthly" style="color:#A7BCD6">₹0 per month</div>
        </div>
        <div class="card pad"><div class="card-t" style="margin-bottom:10px">Breakdown</div>
          <div id="bd"></div></div>
        ${chartCard('Where the savings come from', 'c-calc', { height: 230 })}
      </div>
    </div>`);

  const F = [
    { k: 'seats_paid', label: 'Software seats you pay for', v: 60, min: 1, max: 500, step: 1 },
    { k: 'seats_used', label: 'Seats actually in use', v: 42, min: 1, max: 500, step: 1 },
    { k: 'cost_per_seat', label: 'Average cost per seat (₹/month)', v: 850, min: 100, max: 10000, step: 50 },
    { k: 'tools', label: 'Number of SaaS tools', v: 24, min: 1, max: 200, step: 1 },
    { k: 'tool_cost', label: 'Average tool cost (₹/month)', v: 4200, min: 500, max: 100000, step: 100 },
    { k: 'overlap_pct', label: 'Estimated tool overlap (%)', v: 15, min: 0, max: 60, step: 1 },
    { k: 'manual_hours', label: 'Manual data-entry hours / month', v: 120, min: 0, max: 2000, step: 5 },
    { k: 'hourly_cost', label: 'Blended hourly cost (₹)', v: 450, min: 100, max: 5000, step: 25 },
    { k: 'automatable', label: 'Automatable share of that work (%)', v: 60, min: 0, max: 100, step: 5 },
    { k: 'monthly_spend', label: 'Total monthly vendor spend (₹)', v: 900000, min: 10000, max: 50000000, step: 10000 },
    { k: 'dup_rate', label: 'Typical duplicate-payment rate (%)', v: 1.2, min: 0, max: 5, step: 0.1 },
  ];

  document.getElementById('inputs').innerHTML = F.map(f => `
    <div class="fr">
      <div class="row-b"><label class="field">${f.label}</label>
        <strong class="sm mono" id="v-${f.k}">${f.v}</strong></div>
      <input type="range" id="${f.k}" min="${f.min}" max="${f.max}" step="${f.step}" value="${f.v}" style="width:100%">
    </div>`).join('');

  const calc = () => {
    const g = k => parseFloat(document.getElementById(k).value);
    F.forEach(f => document.getElementById('v-' + f.k).textContent =
      f.k.includes('cost') || f.k === 'monthly_spend' ? inr(g(f.k)) : g(f.k));

    const unused = Math.max(0, g('seats_paid') - g('seats_used')) * g('cost_per_seat');
    const overlap = g('tools') * g('tool_cost') * (g('overlap_pct') / 100) * 0.5;
    const manual = g('manual_hours') * g('hourly_cost') * (g('automatable') / 100);
    const dup = g('monthly_spend') * (g('dup_rate') / 100);
    const rows = [
      ['Unused software seats', unused, '(paid − used) × cost per seat'],
      ['Overlapping tools', overlap, 'tools × cost × overlap% × 50% consolidation'],
      ['Automatable manual work', manual, 'hours × hourly cost × automatable%'],
      ['Recoverable duplicate payments', dup, 'monthly spend × duplicate rate'],
    ];
    const total = rows.reduce((s, r) => s + r[1], 0);

    document.getElementById('big').textContent = inr(total * 12);
    document.getElementById('monthly').textContent = inr(total) + ' per month';
    document.getElementById('bd').innerHTML = rows.map(([l, v, how]) => `
      <div class="stat-line"><div><div class="sm">${l}</div><div class="xs muted mono">${how}</div></div>
        <strong class="mono">${inr(v)}</strong></div>`).join('') +
      `<div class="stat-line" style="border-top:2px solid var(--navy);padding-top:9px">
        <strong>Total per month</strong><strong style="font-size:18px">${inr(total)}</strong></div>`;
    ch.draw(() => ch.donut('c-calc', rows.map(([l, v]) => ({ label: l, value: Math.round(v) })),
      { centerLabel: 'per month' }));
  };
  F.forEach(f => document.getElementById(f.k).oninput = calc);
  ch.clearCharts();
  calc();
}

/* =========================================== SUBSCRIPTIONS ========== */
export async function subscriptions() {
  shell('Subscription analyzer', 'Seat utilisation, renewals and the tools you are paying for twice.',
    '<div class="skel" style="height:320px"></div>');

  const d = await api('/api/subscriptions/analysis').catch(() => null);
  if (!d || !d.subscriptions?.length) {
    return setBody(empty('🧾', 'No subscription data',
      'Upload a workbook containing a Subscriptions sheet to analyse seats, renewals and overlaps.',
      '<a class="btn btn-teal" href="/app/upload">Upload data →</a>'));
  }
  const s = d.subscriptions, sum = d.summary;

  setBody(`
    <div class="grid g4">
      ${kpi('Tools', s.length, `${inrShort(sum.monthly_cost)} per month`, 'teal')}
      ${kpi('Seat utilisation', pct(sum.utilisation), `${sum.seats_used} of ${sum.seats_paid} seats`,
            sum.utilisation >= 85 ? 'green' : 'orange')}
      ${kpi('Wasted on empty seats', inrShort(sum.wasted_seats), 'per month', 'red')}
      ${kpi('Renewals in 30 days', sum.renewals_30d, inrShort(sum.renewal_value) + ' at stake', 'violet')}
    </div>
    <div class="grid g2 mt">
      ${chartCard('Monthly cost by tool', 'c-sub', { height: 260 })}
      ${chartCard('Seat utilisation by tool', 'c-util', { height: 260, note: '%' })}
    </div>
    ${d.overlaps?.length ? `<div class="card pad mt">
      <div class="card-t" style="margin-bottom:10px">Overlapping tool groups</div>
      ${d.overlaps.map(o => `<div class="alert a-warn" style="margin-bottom:8px"><span>🧩</span><div>
        <strong>${esc(o.group)}</strong> — ${o.tools.map(esc).join(' + ')}
        <div class="sm">Consolidating could save about <strong>${inr(o.monthly_saving)}</strong> per month.</div>
      </div></div>`).join('')}</div>` : ''}
    <div class="card pad mt">
      <div class="card-t" style="margin-bottom:10px">All subscriptions</div>
      ${table([
        { label: 'Tool', render: r => `<strong>${esc(r.tool)}</strong><div class="xs muted">${esc(r.vendor || '')}</div>` },
        { label: 'Category', render: r => `<span class="sm">${esc(r.category || '—')}</span>` },
        { label: 'Monthly', align: 'right', mono: true, render: r => inr(r.monthly_cost) },
        { label: 'Seats', align: 'right', mono: true, render: r => `${r.seats_used}/${r.seats_paid}` },
        { label: 'Utilisation', align: 'right', render: r => `<span class="badge ${r.utilisation >= 85 ? 'b-green' : r.utilisation >= 60 ? 'b-orange' : 'b-red'}">${r.utilisation.toFixed(0)}%</span>` },
        { label: 'Wasted', align: 'right', mono: true, render: r => `<span style="color:var(--red)">${inr(r.wasted)}</span>` },
        { label: 'Renews', align: 'right', render: r => `<span class="sm">${fdate(r.renewal_date)}</span>
            ${r.days_to_renewal <= 30 ? `<div class="xs" style="color:var(--orange)">in ${r.days_to_renewal}d</div>` : ''}` },
      ], s)}
    </div>`);

  ch.clearCharts();
  ch.draw(() => ch.hbar('c-sub', s.slice(0, 10).map(r => ({ label: r.tool, value: Math.round(r.monthly_cost) }))));
  ch.draw(() => ch.bar('c-util', s.slice(0, 10).map(r => ({ label: r.tool, value: Math.round(r.utilisation) })), { suffix: '%' }));
}

/* ================================================= REPORTS ========== */
export async function reports() {
  shell('Reports', 'Board-ready PDFs and spreadsheet exports.', `
    <div class="grid g3">
      ${[['📄', 'Cost-leak executive report',
          'Every finding, ranked by rupee impact, with the calculation logic and evidence. 1–2 pages per section.',
          `/api/exports/report.pdf?t=${state.token}`, 'Download PDF'],
         ['📊', 'Findings spreadsheet',
          'All findings as CSV — priority, category, vendor, monthly and annual impact, recommended action.',
          `/api/exports/findings.csv?t=${state.token}`, 'Download CSV'],
         ['🧾', 'GSTR-1 export (current month)',
          'B2B and B2C tables plus HSN summary for the current period, formatted for your filing.',
          `/api/exports/gstr1.csv?t=${state.token}`, 'Download CSV'],
         ['💹', 'Product profitability',
          'Cost, selling price, units sold, profit and margin for every product in your database.',
          `/api/exports/products.csv?t=${state.token}`, 'Download CSV'],
         ['📑', 'Invoice register',
          'Every invoice with taxable value, CGST/SGST/IGST, total, status and margin.',
          `/api/exports/invoices.csv?t=${state.token}`, 'Download CSV'],
         ['🗂', 'Blank data template',
          'The expected workbook structure — Expenses, Subscriptions, Manual_Tasks and Attendance sheets.',
          `/api/exports/template.xlsx?t=${state.token}`, 'Download XLSX']]
        .map(([i, t, d, href, cta]) => `
          <div class="card pad-l">
            <div style="font-size:30px">${i}</div>
            <h3 style="font-size:16px;margin:9px 0 6px">${t}</h3>
            <p class="sm muted" style="min-height:66px">${d}</p>
            <a class="btn btn-primary btn-block" href="${href}" target="_blank">${cta}</a>
          </div>`).join('')}
    </div>
    ${alert('info', `<strong>A note on the numbers.</strong> All savings are <em>estimates</em> derived from the data
      you uploaded, computed by deterministic rules — not predictions. Each finding carries its formula so your
      finance team can verify it line by line. GST exports must be reconciled with your books before filing.`)}`);
}
