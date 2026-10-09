/* Invoice list, GST invoice builder and invoice detail. */
import { api, cached, bust, state, inr, inr2, inrShort, esc, fdate, todayISO, monthISO,
         STATE_LIST, GST_RATES, debounce, go } from '../core.js';
import { shell, setBody, kpi, table, statusBadge, empty, alert, busy, toast, modal,
         confirmDialog, loading } from '../ui.js';

/* ====================================================== LIST ========= */
export async function invoiceList() {
  shell('Invoices', 'GST-compliant tax invoices, purchase bills and payment status.',
    '<div class="skel" style="height:300px"></div>',
    `<a class="btn btn-ghost btn-sm" href="/app/invoices/new?type=purchase">+ Purchase bill</a>
     <a class="btn btn-teal btn-sm" href="/app/invoices/new">+ New invoice</a>`);

  const filters = { doc_type: 'sale', status: '', month: '', search: '' };

  async function load() {
    const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
    const data = await api('/api/invoices?' + qs);
    const s = data.summary;
    setBody(`
      <div class="grid g4">
        ${kpi('Invoiced', inrShort(s.total_sales), `${s.count} documents`, 'teal')}
        ${kpi('Tax collected', inrShort(s.tax_collected), 'CGST + SGST + IGST', 'violet')}
        ${kpi('Outstanding', inrShort(s.outstanding), 'unpaid + partial', 'orange')}
        ${kpi('Gross profit', inrShort(s.profit), 'revenue − product cost', 'green')}
      </div>
      <div class="card pad mt">
        <div class="card-h">
          <div class="row">
            <div class="seg">
              <button data-t="sale" class="${filters.doc_type === 'sale' ? 'on' : ''}">Sales</button>
              <button data-t="purchase" class="${filters.doc_type === 'purchase' ? 'on' : ''}">Purchases</button>
              <button data-t="" class="${filters.doc_type === '' ? 'on' : ''}">All</button>
            </div>
          </div>
          <div class="row">
            <input id="q" placeholder="Search number or customer…" style="width:210px" value="${esc(filters.search)}">
            <input id="m" type="month" value="${esc(filters.month)}" style="width:150px">
            <select id="st" style="width:130px">
              <option value="">All statuses</option>
              ${['unpaid', 'partial', 'paid', 'cancelled'].map(x =>
                `<option ${filters.status === x ? 'selected' : ''}>${x}</option>`).join('')}
            </select>
          </div>
        </div>
        ${table([
          { label: 'Number', render: r => `<a href="/app/invoices/${r.id}" style="font-weight:650;color:var(--teal-ink)">${esc(r.number)}</a>
              <div class="xs muted">${fdate(r.invoice_date)}</div>` },
          { label: 'Customer', render: r => `${esc(r.customer_name)}
              <div class="xs muted">${r.customer_gstin ? esc(r.customer_gstin) : 'Unregistered / B2C'}</div>` },
          { label: 'Supply', render: r => `<span class="badge ${r.supply_type === 'intra' ? 'b-teal' : 'b-violet'}">${r.supply_type === 'intra' ? 'CGST+SGST' : 'IGST'}</span>
              <div class="xs muted">${esc(STATE_LIST[r.place_of_supply] || '')}</div>` },
          { label: 'Taxable', align: 'right', mono: true, render: r => inr(r.taxable_total) },
          { label: 'Tax', align: 'right', mono: true, render: r => inr(r.cgst + r.sgst + r.igst) },
          { label: 'Total', align: 'right', mono: true, render: r => `<strong>${inr(r.total)}</strong>` },
          { label: 'Status', align: 'right', render: r => statusBadge(r.status) },
        ], data.invoices, { empty: 'No invoices for this filter yet.' })}
      </div>`);

    document.querySelectorAll('[data-t]').forEach(b => b.onclick = () => {
      filters.doc_type = b.dataset.t; load();
    });
    document.getElementById('q').oninput = debounce(e => { filters.search = e.target.value; load(); }, 380);
    document.getElementById('m').onchange = e => { filters.month = e.target.value; load(); };
    document.getElementById('st').onchange = e => { filters.status = e.target.value; load(); };
  }
  await load();
}

/* ==================================================== BUILDER ======== */
export async function invoiceNew() {
  const docType = new URLSearchParams(location.search).get('type') || 'sale';
  shell(docType === 'purchase' ? 'New purchase bill' : 'New tax invoice',
    'Totals, CGST/SGST/IGST split and margin update as you type.',
    '<div class="skel" style="height:360px"></div>');

  const [{ products }, { customers }, company] = await Promise.all([
    cached('/api/products'), cached('/api/customers'), cached('/api/company'),
  ]);

  let lines = [blankLine()];
  function blankLine() {
    return { product_id: '', name: '', hsn: '', unit: 'NOS', qty: 1, rate: 0,
             discount_pct: 0, gst_rate: 18, cost_price: 0 };
  }

  setBody(`
    <div class="grid" style="grid-template-columns:1fr 330px;gap:16px;align-items:start">
      <div class="col" style="gap:16px">
        <div class="card pad">
          <div class="card-t" style="margin-bottom:12px">${docType === 'purchase' ? 'Vendor' : 'Customer'} & details</div>
          <div class="grid g2" style="gap:12px">
            <div class="fr"><label class="field">${docType === 'purchase' ? 'Vendor' : 'Customer'} *</label>
              <select id="cust"><option value="">— Select —</option>
                ${customers.filter(c => docType === 'purchase' ? c.is_vendor : !c.is_vendor)
                  .map(c => `<option value="${c.id}" data-state="${c.state_code}" data-gstin="${esc(c.gstin || '')}">
                    ${esc(c.name)}${c.gstin ? ` · ${esc(c.gstin)}` : ' · B2C'}</option>`).join('')}
              </select>
              <div class="help"><a href="/app/customers" style="color:var(--teal-ink)">+ Add a new one</a></div></div>
            <div class="fr"><label class="field">Place of supply</label>
              <select id="pos">${Object.entries(STATE_LIST).map(([c, n]) =>
                `<option value="${c}" ${c === company.state_code ? 'selected' : ''}>${c} — ${n}</option>`).join('')}</select>
              <div class="help" id="supply-note"></div></div>
            <div class="fr"><label class="field">Invoice date</label>
              <input id="idate" type="date" value="${todayISO()}"></div>
            <div class="fr"><label class="field">Payment due in (days)</label>
              <input id="due" type="number" value="15" min="0"></div>
          </div>
        </div>

        <div class="card pad">
          <div class="card-h"><div class="card-t">Line items</div>
            <button class="btn btn-soft btn-sm" id="add">+ Add line</button></div>
          <div id="lines"></div>
        </div>

        <div class="card pad">
          <div class="grid g2" style="gap:12px">
            <div class="fr"><label class="field">Notes (printed on the invoice)</label>
              <textarea id="notes" rows="2" placeholder="Thank you for your business."></textarea></div>
            <div class="fr"><label class="field">Terms</label>
              <textarea id="terms" rows="2" placeholder="Payment due within 15 days. Interest @18% p.a. on delayed payments."></textarea></div>
          </div>
        </div>
      </div>

      <div class="card pad" style="position:sticky;top:76px">
        <div class="card-t" style="margin-bottom:10px">Summary</div>
        <div id="totals"><div class="skel" style="height:180px"></div></div>
        <button class="btn btn-teal btn-block mt" id="save">Create ${docType === 'purchase' ? 'bill' : 'invoice'}</button>
        <div class="help center mt-s">Figures follow GST place-of-supply rules automatically.</div>
      </div>
    </div>`);

  const el = id => document.getElementById(id);

  function renderLines() {
    el('lines').innerHTML = lines.map((l, i) => `
      <div class="card pad-s" style="box-shadow:none;margin-bottom:9px;background:var(--line-2);border:none">
        <div class="grid" style="grid-template-columns:2.1fr .8fr .7fr 1fr .7fr .8fr 34px;gap:8px;align-items:end">
          <div><label class="field">Item</label>
            <select data-i="${i}" data-k="product_id">
              <option value="">— custom —</option>
              ${products.map(p => `<option value="${p.id}" ${l.product_id === p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}
            </select>
            ${!l.product_id ? `<input data-i="${i}" data-k="name" value="${esc(l.name)}" placeholder="Description" style="margin-top:5px">` : ''}
          </div>
          <div><label class="field">HSN</label><input data-i="${i}" data-k="hsn" value="${esc(l.hsn)}"></div>
          <div><label class="field">Qty</label><input data-i="${i}" data-k="qty" type="number" step="0.01" value="${l.qty}"></div>
          <div><label class="field">Rate (₹)</label><input data-i="${i}" data-k="rate" type="number" step="0.01" value="${l.rate}"></div>
          <div><label class="field">Disc %</label><input data-i="${i}" data-k="discount_pct" type="number" step="0.1" value="${l.discount_pct}"></div>
          <div><label class="field">GST %</label>
            <select data-i="${i}" data-k="gst_rate">${GST_RATES.map(r =>
              `<option value="${r}" ${Number(l.gst_rate) === r ? 'selected' : ''}>${r}%</option>`).join('')}</select></div>
          <button class="btn btn-soft btn-icon" data-del="${i}" ${lines.length === 1 ? 'disabled' : ''}>✕</button>
        </div>
        ${l.cost_price ? `<div class="xs muted" style="margin-top:6px">Cost ${inr(l.cost_price)}/unit ·
          margin ${(((l.rate - l.cost_price) / (l.rate || 1)) * 100).toFixed(1)}%
          ${l.rate < l.cost_price ? '<span class="badge b-red" style="margin-left:6px">below cost</span>' : ''}</div>` : ''}
      </div>`).join('');

    el('lines').querySelectorAll('[data-k]').forEach(inp => {
      inp.onchange = () => {
        const i = +inp.dataset.i, k = inp.dataset.k;
        if (k === 'product_id') {
          const p = products.find(x => x.id === inp.value);
          lines[i] = p ? { ...lines[i], product_id: p.id, name: p.name, hsn: p.hsn || '',
                           unit: p.unit, rate: p.selling_price, gst_rate: p.gst_rate,
                           cost_price: p.cost_price }
                       : { ...blankLine(), qty: lines[i].qty };
          renderLines();
        } else {
          lines[i][k] = inp.type === 'number' ? parseFloat(inp.value || 0) : inp.value;
        }
        preview();
      };
    });
    el('lines').querySelectorAll('[data-del]').forEach(b => b.onclick = () => {
      lines.splice(+b.dataset.del, 1); renderLines(); preview();
    });
  }

  const previewNow = async () => {
    const valid = lines.filter(l => (l.name || l.product_id) && l.rate > 0);
    if (!valid.length) {
      el('totals').innerHTML = `<div class="empty sm" style="padding:20px">Add an item to see the totals.</div>`;
      return;
    }
    try {
      const r = await api('/api/invoices/preview', { method: 'POST',
        body: { doc_type: docType, items: valid, place_of_supply: el('pos').value, customer_name: 'preview' } });
      const intra = r.supply_type === 'intra';
      el('supply-note').innerHTML = intra
        ? `Same state as you → <strong>CGST + SGST</strong>`
        : `Different state → <strong>IGST</strong>`;
      el('totals').innerHTML = `
        <div class="stat-line"><span>Subtotal</span><span class="mono">${inr2(r.subtotal)}</span></div>
        ${r.discount_total ? `<div class="stat-line"><span>Discount</span><span class="mono">− ${inr2(r.discount_total)}</span></div>` : ''}
        <div class="stat-line"><span>Taxable value</span><span class="mono">${inr2(r.taxable_total)}</span></div>
        ${intra ? `<div class="stat-line"><span>CGST</span><span class="mono">${inr2(r.cgst)}</span></div>
                   <div class="stat-line"><span>SGST</span><span class="mono">${inr2(r.sgst)}</span></div>`
                : `<div class="stat-line"><span>IGST</span><span class="mono">${inr2(r.igst)}</span></div>`}
        ${r.round_off ? `<div class="stat-line"><span>Round off</span><span class="mono">${inr2(r.round_off)}</span></div>` : ''}
        <div class="stat-line" style="border-top:2px solid var(--navy);margin-top:6px;padding-top:9px">
          <strong>Total</strong><strong style="font-size:19px">${inr(r.total)}</strong></div>
        <div class="xs muted" style="margin-top:4px">${esc(r.amount_in_words)}</div>
        ${r.cost_total ? `<div class="card pad-s mt" style="box-shadow:none;background:var(--line-2);border:none">
          <div class="xs muted">MARGIN ON THIS INVOICE</div>
          <div class="row-b"><strong style="color:${r.profit >= 0 ? 'var(--green)' : 'var(--red)'};font-size:16px">${inr(r.profit)}</strong>
            <span class="badge ${r.margin_pct >= 25 ? 'b-green' : r.margin_pct >= 10 ? 'b-orange' : 'b-red'}">${r.margin_pct.toFixed(1)}%</span></div>
          <div class="xs muted">cost ${inr(r.cost_total)} · revenue ${inr(r.taxable_total)}</div></div>` : ''}`;
    } catch (e) { el('totals').innerHTML = alert('err', esc(e.message)); }
  };
  const preview = debounce(previewNow, 260);

  el('cust').onchange = () => {
    const opt = el('cust').selectedOptions[0];
    if (opt?.dataset.state) el('pos').value = opt.dataset.state;
    previewNow();
  };
  el('pos').onchange = previewNow;
  el('add').onclick = () => { lines.push(blankLine()); renderLines(); };

  el('save').onclick = async (e) => {
    const valid = lines.filter(l => (l.name || l.product_id) && l.rate > 0);
    if (!el('cust').value) return toast('Select a customer first', 'err');
    if (!valid.length) return toast('Add at least one line item', 'err');
    busy(e.target, true, 'Saving');
    try {
      const r = await api('/api/invoices', { method: 'POST', body: {
        doc_type: docType, customer_id: el('cust').value, place_of_supply: el('pos').value,
        invoice_date: el('idate').value, due_days: parseInt(el('due').value || 15),
        items: valid, notes: el('notes').value, terms: el('terms').value,
      } });
      bust('/api/invoices'); bust('/api/gst');
      toast('Invoice created', 'ok');
      go('/app/invoices/' + r.invoice.id);
    } catch (err) {
      busy(e.target, false);
      if (err.data?.code === 'plan_limit') {
        modal('Plan limit reached', `<p>${esc(err.data.message)}</p>
          <a class="btn btn-teal mt" href="/app/plans">See plans →</a>`);
      } else toast(err.message, 'err');
    }
  };

  renderLines();
  previewNow();
}

/* ==================================================== DETAIL ========= */
export async function invoiceDetail({ id }) {
  shell('Invoice', '', '<div class="skel" style="height:420px"></div>');
  const d = await api('/api/invoices/' + id);
  const inv = d.invoice, items = d.items, co = d.company;
  const intra = inv.supply_type === 'intra';

  setBody(`
    <div class="row-b no-print" style="margin-bottom:14px">
      <a class="btn btn-ghost btn-sm" href="/app/invoices">← All invoices</a>
      <div class="row">
        <select id="status" style="width:150px">${['draft', 'unpaid', 'partial', 'paid', 'cancelled']
          .map(s => `<option ${inv.status === s ? 'selected' : ''}>${s}</option>`).join('')}</select>
        <button class="btn btn-ghost btn-sm" onclick="window.print()">🖨 Print</button>
        <a class="btn btn-primary btn-sm" href="/api/invoices/${inv.id}/pdf?t=${state.token}" target="_blank">📄 PDF</a>
      </div>
    </div>

    <div class="card pad-l" id="paper">
      <div class="row-b" style="align-items:flex-start;border-bottom:2px solid var(--navy);padding-bottom:16px">
        <div>
          <h2 style="font-size:20px">${esc(co.name)}</h2>
          <div class="sm muted" style="margin-top:4px">${esc(co.address || '')} ${esc(co.city || '')} ${esc(co.pincode || '')}<br>
            ${co.gstin ? `GSTIN: <strong>${esc(co.gstin)}</strong><br>` : ''}${esc(co.email || '')} ${co.phone ? '· ' + esc(co.phone) : ''}</div>
        </div>
        <div class="right">
          <div style="font-size:21px;font-weight:800;color:var(--teal-ink)">${inv.doc_type === 'sale' ? 'TAX INVOICE' : 'PURCHASE BILL'}</div>
          <div style="font-weight:700;margin-top:3px">${esc(inv.number)}</div>
          <div class="sm muted">Date: ${fdate(inv.invoice_date)}<br>Due: ${fdate(inv.due_date)}</div>
        </div>
      </div>

      <div class="grid g2 mt">
        <div class="card pad-s" style="box-shadow:none;background:var(--line-2);border:none">
          <div class="xs muted">BILL TO</div>
          <div style="font-weight:700;font-size:15px;margin-top:3px">${esc(inv.customer_name)}</div>
          <div class="sm muted">${inv.customer_gstin ? 'GSTIN: ' + esc(inv.customer_gstin) : 'Unregistered / B2C'}<br>
            Place of supply: ${esc(d.place_of_supply_name)} (${esc(inv.place_of_supply)})</div>
        </div>
        <div class="card pad-s right" style="box-shadow:none;background:var(--line-2);border:none">
          <div class="xs muted">AMOUNT ${inv.status === 'paid' ? 'PAID' : 'DUE'}</div>
          <div style="font-size:26px;font-weight:800">${inr(inv.total - (inv.amount_paid || 0))}</div>
          <div>${statusBadge(inv.status)} <span class="badge ${intra ? 'b-teal' : 'b-violet'}">${intra ? 'Intra-state' : 'Inter-state'}</span></div>
        </div>
      </div>

      <div class="mt">${table([
        { label: '#', render: (r, i) => '' },
        { label: 'Item', render: r => `<strong>${esc(r.name)}</strong>${r.discount_pct ? `<div class="xs muted">discount ${r.discount_pct}%</div>` : ''}` },
        { label: 'HSN', render: r => `<span class="sm">${esc(r.hsn || '—')}</span>` },
        { label: 'Qty', align: 'right', mono: true, render: r => `${r.qty} ${esc(r.unit || '')}` },
        { label: 'Rate', align: 'right', mono: true, render: r => inr2(r.rate) },
        { label: 'Taxable', align: 'right', mono: true, render: r => inr2(r.taxable) },
        ...(intra
          ? [{ label: 'CGST', align: 'right', mono: true, render: r => `${inr2(r.cgst)}<div class="xs muted">${r.gst_rate / 2}%</div>` },
             { label: 'SGST', align: 'right', mono: true, render: r => `${inr2(r.sgst)}<div class="xs muted">${r.gst_rate / 2}%</div>` }]
          : [{ label: 'IGST', align: 'right', mono: true, render: r => `${inr2(r.igst)}<div class="xs muted">${r.gst_rate}%</div>` }]),
        { label: 'Amount', align: 'right', mono: true, render: r => `<strong>${inr2(r.total)}</strong>` },
      ], items.map((r, i) => ({ ...r, _i: i + 1 })))}</div>

      <div class="grid g2 mt" style="align-items:start">
        <div>
          <div class="card-t" style="margin-bottom:7px">Tax rate summary</div>
          ${table([
            { label: 'Rate', render: r => `${r.gst_rate}%` },
            { label: 'Taxable', align: 'right', mono: true, render: r => inr2(r.taxable) },
            { label: 'CGST', align: 'right', mono: true, render: r => inr2(r.cgst) },
            { label: 'SGST', align: 'right', mono: true, render: r => inr2(r.sgst) },
            { label: 'IGST', align: 'right', mono: true, render: r => inr2(r.igst) },
          ], d.tax_breakup)}
          <div class="sm mt"><strong>In words:</strong> ${esc(d.amount_in_words)}</div>
          ${inv.notes ? `<div class="sm mt"><strong>Notes:</strong> ${esc(inv.notes)}</div>` : ''}
          ${inv.terms ? `<div class="xs muted mt-s"><strong>Terms:</strong> ${esc(inv.terms)}</div>` : ''}
        </div>
        <div>
          <div class="stat-line"><span>Subtotal</span><span class="mono">${inr2(inv.subtotal)}</span></div>
          ${inv.discount_total ? `<div class="stat-line"><span>Discount</span><span class="mono">− ${inr2(inv.discount_total)}</span></div>` : ''}
          <div class="stat-line"><span>Taxable value</span><span class="mono">${inr2(inv.taxable_total)}</span></div>
          ${intra ? `<div class="stat-line"><span>CGST</span><span class="mono">${inr2(inv.cgst)}</span></div>
                     <div class="stat-line"><span>SGST</span><span class="mono">${inr2(inv.sgst)}</span></div>`
                  : `<div class="stat-line"><span>IGST</span><span class="mono">${inr2(inv.igst)}</span></div>`}
          ${inv.round_off ? `<div class="stat-line"><span>Round off</span><span class="mono">${inr2(inv.round_off)}</span></div>` : ''}
          <div class="stat-line" style="border-top:2px solid var(--navy);padding-top:9px">
            <strong>Total</strong><strong style="font-size:21px">${inr(inv.total)}</strong></div>
          ${inv.doc_type === 'sale' && inv.cost_total ? `
            <div class="card pad-s mt no-print" style="box-shadow:none;background:var(--line-2);border:none">
              <div class="xs muted">INTERNAL — NOT PRINTED</div>
              <div class="stat-line"><span>Cost of goods/services</span><span class="mono">${inr(inv.cost_total)}</span></div>
              <div class="stat-line"><span>Profit</span>
                <strong class="mono" style="color:${inv.profit >= 0 ? 'var(--green)' : 'var(--red)'}">${inr(inv.profit)} (${inv.margin_pct.toFixed(1)}%)</strong></div>
            </div>` : ''}
        </div>
      </div>
    </div>`);

  document.getElementById('status').onchange = async (e) => {
    try {
      await api('/api/invoices/' + id, { method: 'PATCH', body: { status: e.target.value } });
      bust('/api/invoices'); bust('/api/gst');
      toast('Status updated', 'ok');
      invoiceDetail({ id });
    } catch (err) { toast(err.message, 'err'); }
  };
}
