/* GST & tax reports — "replace the CA" view. */
import { api, cached, state, inr, inr2, inrShort, pct, esc, monthISO, fdate } from '../core.js';
import { shell, setBody, kpi, table, chartCard, alert, empty, toast } from '../ui.js';
import * as ch from '../charts.js';

export async function gst() {
  let month = monthISO();
  let tab = 'summary';

  shell('GST & tax reports', 'Output tax, input credit, net payable and GSTR-1 style exports.',
    '<div class="skel" style="height:340px"></div>',
    `<input type="month" id="mon" value="${month}" style="width:160px">
     <a class="btn btn-ghost btn-sm" id="csv">⬇ GSTR-1 CSV</a>`);

  const setMonthHandlers = () => {
    document.getElementById('mon').onchange = e => { month = e.target.value; load(); };
    document.getElementById('csv').onclick = () => {
      window.open(`/api/exports/gstr1.csv?month=${month}&t=${state.token}`, '_blank');
    };
  };
  setMonthHandlers();

  async function load() {
    const [s, p] = await Promise.all([
      api(`/api/gst/summary?month=${month}`),
      api(`/api/gst/profit?month=${month}`),
    ]);
    const o = s.output_tax, i = s.input_tax;

    setBody(`
      <div class="tabs">
        ${[['summary', 'Tax summary'], ['gstr1', 'GSTR-1 (B2B / B2C)'], ['hsn', 'HSN summary'], ['profit', 'Profit & margins']]
          .map(([k, l]) => `<button data-tab="${k}" class="${tab === k ? 'on' : ''}">${l}</button>`).join('')}
      </div>
      <div id="tabbody" class="mt"></div>`);

    document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => { tab = b.dataset.tab; paint(); });
    paint();

    function paint() {
      document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
      const tb = document.getElementById('tabbody');
      ch.clearCharts();

      if (tab === 'summary') {
        tb.innerHTML = `
          <div class="grid g4">
            ${kpi('Output tax (on sales)', inrShort(o.total), `${s.sales_count} invoices · taxable ${inrShort(s.taxable_sales)}`, 'teal')}
            ${kpi('Input tax credit', inrShort(i.total), `${s.purchase_count} purchase bills`, 'violet')}
            ${kpi('Net GST payable', inrShort(s.net_payable), s.net_payable > 0 ? 'pay before the 20th' : 'credit carried forward',
                  s.net_payable > 0 ? 'orange' : 'green')}
            ${kpi('Effective tax rate', pct(s.effective_rate), 'tax ÷ taxable sales', 'grey')}
          </div>

          ${alert('info', `<strong>How this is calculated.</strong> Output tax = GST charged on ${s.sales_count} sales invoices
            dated in ${month}. Input tax credit = GST paid on ${s.purchase_count} purchase bills in the same period.
            Net payable = output − ITC, head by head. Reconcile with GSTR-2B before filing.`)}

          <div class="grid g2 mt">
            <div class="card pad">
              <div class="card-t" style="margin-bottom:10px">Head-wise liability</div>
              ${table([
                { label: 'Head', render: r => `<strong>${r.head}</strong>` },
                { label: 'Output', align: 'right', mono: true, render: r => inr2(r.out) },
                { label: 'ITC', align: 'right', mono: true, render: r => inr2(r.itc) },
                { label: 'Net payable', align: 'right', mono: true,
                  render: r => `<strong style="color:${r.out - r.itc > 0 ? 'var(--navy)' : 'var(--green)'}">${inr2(Math.max(0, r.out - r.itc))}</strong>` },
              ], [
                { head: 'CGST', out: o.cgst, itc: i.cgst },
                { head: 'SGST', out: o.sgst, itc: i.sgst },
                { head: 'IGST', out: o.igst, itc: i.igst },
                { head: 'CESS', out: 0, itc: 0 },
              ])}
              <div class="stat-line" style="border-top:2px solid var(--navy);margin-top:8px;padding-top:10px">
                <strong>Total net payable</strong><strong style="font-size:20px">${inr(s.net_payable)}</strong></div>
            </div>
            ${chartCard('Output tax vs input credit — last 6 months', 'c-gst', { height: 280 })}
          </div>

          <div class="card pad mt">
            <div class="card-t" style="margin-bottom:10px">Rate-wise breakup</div>
            ${table([
              { label: 'GST rate', render: r => `${r.gst_rate}%` },
              { label: 'Taxable value', align: 'right', mono: true, render: r => inr2(r.taxable) },
              { label: 'CGST', align: 'right', mono: true, render: r => inr2(r.cgst) },
              { label: 'SGST', align: 'right', mono: true, render: r => inr2(r.sgst) },
              { label: 'IGST', align: 'right', mono: true, render: r => inr2(r.igst) },
              { label: 'Total tax', align: 'right', mono: true, render: r => `<strong>${inr2(r.cgst + r.sgst + r.igst)}</strong>` },
            ], s.rate_wise, { empty: 'No taxable supplies in this period.' })}
          </div>`;
        ch.draw(() => ch.bar('c-gst', (s.net_trend || []).map(t => ({ label: t.month, value: Math.round(t.net) }))));
      }

      if (tab === 'gstr1') {
        tb.innerHTML = `
          ${alert('warn', `<strong>GSTR-1 style export.</strong> This reproduces the B2B and B2C summary tables for ${month}.
            Download the CSV and reconcile it against your books before uploading to the GST portal.`)}
          <div class="card pad mt">
            <div class="card-h"><div class="card-t">B2B supplies (registered customers)</div>
              <span class="badge b-teal">${s.b2b_invoices.length} invoices</span></div>
            ${table([
              { label: 'GSTIN', render: r => `<span class="mono sm">${esc(r.customer_gstin)}</span>` },
              { label: 'Customer', render: r => esc(r.customer_name) },
              { label: 'Invoice', render: r => `${esc(r.number)}<div class="xs muted">${fdate(r.invoice_date)}</div>` },
              { label: 'POS', render: r => `<span class="sm">${esc(r.place_of_supply)}</span>` },
              { label: 'Taxable', align: 'right', mono: true, render: r => inr2(r.taxable_total) },
              { label: 'Tax', align: 'right', mono: true, render: r => inr2(r.cgst + r.sgst + r.igst) },
              { label: 'Total', align: 'right', mono: true, render: r => `<strong>${inr2(r.total)}</strong>` },
            ], s.b2b_invoices, { empty: 'No B2B supplies this month.' })}
          </div>
          <div class="card pad mt">
            <div class="card-h"><div class="card-t">B2C supplies (unregistered — consolidated)</div>
              <span class="badge b-violet">${s.b2c_count} invoices</span></div>
            ${table([
              { label: 'Place of supply', render: r => esc(r.pos_name) },
              { label: 'Rate', render: r => `${r.gst_rate}%` },
              { label: 'Taxable value', align: 'right', mono: true, render: r => inr2(r.taxable) },
              { label: 'Tax', align: 'right', mono: true, render: r => inr2(r.tax) },
            ], s.b2c_rows, { empty: 'No B2C supplies this month.' })}
          </div>`;
      }

      if (tab === 'hsn') {
        tb.innerHTML = `
          <div class="card pad">
            <div class="card-h"><div class="card-t">HSN / SAC summary — ${month}</div>
              <span class="xs muted">Required in Table 12 of GSTR-1</span></div>
            ${table([
              { label: 'HSN/SAC', render: r => `<span class="mono">${esc(r.hsn || '—')}</span>` },
              { label: 'Description', render: r => esc(r.description) },
              { label: 'UQC', render: r => `<span class="sm">${esc(r.unit || 'NOS')}</span>` },
              { label: 'Qty', align: 'right', mono: true, render: r => r.qty },
              { label: 'Taxable value', align: 'right', mono: true, render: r => inr2(r.taxable) },
              { label: 'Rate', align: 'right', render: r => `${r.gst_rate}%` },
              { label: 'Total tax', align: 'right', mono: true, render: r => inr2(r.tax) },
            ], s.hsn_detail, { empty: 'No line items with HSN codes this month. Add HSN/SAC codes on your products.' })}
          </div>`;
      }

      if (tab === 'profit') {
        tb.innerHTML = `
          <div class="grid g4">
            ${kpi('Revenue (taxable)', inrShort(p.revenue), `${p.invoice_count} invoices`, 'teal')}
            ${kpi('Cost of sales', inrShort(p.cost), 'from your product cost database', 'orange')}
            ${kpi('Gross profit', inrShort(p.gross_profit), pct(p.margin_pct) + ' margin',
                  p.gross_profit >= 0 ? 'green' : 'red')}
            ${kpi('Avg. profit / invoice', inrShort(p.avg_profit), 'this month', 'violet')}
          </div>
          ${(p.alerts || []).length ? `<div class="col mt" style="gap:9px">
            ${p.alerts.map(a => alert(a.level === 'critical' ? 'err' : a.level === 'warning' ? 'warn' : 'info',
              `<strong>${esc(a.title)}</strong><div class="sm" style="opacity:.9">${esc(a.detail)}</div>`)).join('')}
          </div>` : alert('ok', '<strong>No margin problems detected this month.</strong> Every product sold above cost.')}
          <div class="grid g2 mt">
            ${chartCard('Profit by product', 'c-pp', { height: 270 })}
            ${chartCard('Revenue vs cost by product', 'c-rc', { height: 270 })}
          </div>
          <div class="card pad mt">
            <div class="card-t" style="margin-bottom:10px">Product profitability — ${month}</div>
            ${table([
              { label: 'Product', render: r => `<strong>${esc(r.name)}</strong>` },
              { label: 'Units sold', align: 'right', mono: true, render: r => r.qty },
              { label: 'Revenue', align: 'right', mono: true, render: r => inr(r.revenue) },
              { label: 'Cost', align: 'right', mono: true, render: r => inr(r.cost) },
              { label: 'Profit', align: 'right', mono: true,
                render: r => `<strong style="color:${r.profit >= 0 ? 'var(--green)' : 'var(--red)'}">${inr(r.profit)}</strong>` },
              { label: 'Margin', align: 'right', render: r => `<span class="badge ${r.margin_pct >= 30 ? 'b-green' : r.margin_pct >= 10 ? 'b-orange' : 'b-red'}">${r.margin_pct.toFixed(1)}%</span>` },
            ], p.by_product, { empty: 'No sales recorded this month.' })}
          </div>`;
        ch.draw(() => ch.hbar('c-pp', (p.by_product || []).slice(0, 8)
          .map(r => ({ label: r.name, value: Math.round(r.profit) }))));
        ch.draw(() => ch.bar('c-rc', (p.by_product || []).slice(0, 7)
          .map(r => ({ label: r.name, value: Math.round(r.revenue) }))));
      }
    }
  }
  await load();
}
