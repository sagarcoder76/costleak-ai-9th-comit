/* Product / cost database + margin engine. */
import { api, cached, bust, inr, inr2, inrShort, pct, esc, GST_RATES, debounce } from '../core.js';
import { shell, setBody, kpi, table, modal, closeModal, toast, busy, empty, formData,
         chartCard, confirmDialog } from '../ui.js';
import * as ch from '../charts.js';

export async function products() {
  shell('Products & costs', 'What each item costs you, what you charge, and where you are losing money.',
    '<div class="skel" style="height:320px"></div>',
    `<button class="btn btn-teal btn-sm" id="new-p">+ Add product</button>`);

  let search = '';
  async function load() {
    const d = await api('/api/products?search=' + encodeURIComponent(search));
    const list = d.products, s = d.summary;
    const losing = list.filter(p => p.selling_price <= p.cost_price);

    setBody(`
      <div class="grid g4">
        ${kpi('Products tracked', s.count, `${s.services} services · ${s.goods} goods`, 'teal')}
        ${kpi('Average margin', pct(s.avg_margin), 'across all products', s.avg_margin >= 25 ? 'green' : 'orange')}
        ${kpi('Losing money', losing.length, losing.length ? 'priced at or below cost' : 'none — good', losing.length ? 'red' : 'green')}
        ${kpi('Stock value at cost', inrShort(s.stock_value), 'quantity × cost price', 'violet')}
      </div>

      ${losing.length ? `<div class="alert a-err mt"><span>🔴</span><div>
        <strong>${losing.length} product${losing.length > 1 ? 's are' : ' is'} selling at or below cost.</strong>
        ${losing.slice(0, 3).map(p => `${esc(p.name)} (cost ${inr(p.cost_price)} vs price ${inr(p.selling_price)})`).join(' · ')}
        </div></div>` : ''}

      <div class="grid g2 mt">
        ${chartCard('Margin % by product', 'c-margin', { height: 260 })}
        ${chartCard('Profit per unit — top earners', 'c-profit', { height: 260 })}
      </div>

      <div class="card pad mt">
        <div class="card-h"><div class="card-t">All products</div>
          <input id="q" placeholder="Search…" style="width:220px" value="${esc(search)}"></div>
        ${table([
          { label: 'Product', render: p => `<strong>${esc(p.name)}</strong>
              <div class="xs muted">${esc(p.sku || '—')} · ${esc(p.category || 'Uncategorised')}</div>` },
          { label: 'HSN/SAC', render: p => `<span class="sm mono">${esc(p.hsn || '—')}</span>` },
          { label: 'Cost', align: 'right', mono: true, render: p => inr2(p.cost_price) },
          { label: 'Selling', align: 'right', mono: true, render: p => inr2(p.selling_price) },
          { label: 'GST', align: 'right', render: p => `<span class="sm">${p.gst_rate}%</span>` },
          { label: 'Profit/unit', align: 'right', mono: true,
            render: p => `<span style="color:${p.profit_per_unit >= 0 ? 'var(--green)' : 'var(--red)'};font-weight:700">${inr2(p.profit_per_unit)}</span>` },
          { label: 'Margin', align: 'right', render: p => `<span class="badge ${p.margin_pct >= 30 ? 'b-green' : p.margin_pct >= 12 ? 'b-orange' : 'b-red'}">${p.margin_pct.toFixed(1)}%</span>` },
          { label: 'Qty', align: 'right', mono: true, render: p => p.stock_qty ?? '—' },
          { label: '', align: 'right', render: p => `<button class="btn btn-soft btn-sm" data-edit="${p.id}">Edit</button>` },
        ], list, { empty: 'No products yet. Add your first one to unlock margin alerts.' })}
      </div>`);

    document.getElementById('new-p').onclick = () => form();
    document.getElementById('q').oninput = debounce(e => { search = e.target.value; load(); }, 350);
    document.querySelectorAll('[data-edit]').forEach(b =>
      b.onclick = () => form(list.find(p => p.id === b.dataset.edit)));

    ch.clearCharts();
    ch.draw(() => ch.hbar('c-margin', list.slice(0, 9)
      .map(p => ({ label: p.name, value: +p.margin_pct.toFixed(1) })), { suffix: '%' }));
    ch.draw(() => ch.bar('c-profit', [...list].sort((a, b) => b.profit_per_unit - a.profit_per_unit).slice(0, 8)
      .map(p => ({ label: p.name, value: Math.round(p.profit_per_unit) }))));

    function form(p = null) {
      modal(p ? 'Edit product' : 'Add product', `
        <form id="pf">
          <div class="fr"><label class="field">Name *</label><input name="name" required value="${esc(p?.name || '')}"></div>
          <div class="grid g2" style="gap:12px">
            <div class="fr"><label class="field">SKU</label><input name="sku" value="${esc(p?.sku || '')}"></div>
            <div class="fr"><label class="field">HSN / SAC code</label><input name="hsn" value="${esc(p?.hsn || '')}">
              <div class="help">Goods = HSN, services = SAC</div></div>
          </div>
          <div class="grid g2" style="gap:12px">
            <div class="fr"><label class="field">Category</label><input name="category" value="${esc(p?.category || '')}" placeholder="Software / Service / Hardware"></div>
            <div class="fr"><label class="field">Unit</label>
              <select name="unit">${['NOS', 'HRS', 'MON', 'PCS', 'KGS', 'SET', 'LOT'].map(u =>
                `<option ${p?.unit === u ? 'selected' : ''}>${u}</option>`).join('')}</select></div>
          </div>
          <div class="grid g3" style="gap:12px">
            <div class="fr"><label class="field">Cost price (₹) *</label>
              <input name="cost_price" type="number" step="0.01" required value="${p?.cost_price ?? 0}"></div>
            <div class="fr"><label class="field">Selling price (₹) *</label>
              <input name="selling_price" type="number" step="0.01" required value="${p?.selling_price ?? 0}"></div>
            <div class="fr"><label class="field">GST rate</label>
              <select name="gst_rate">${GST_RATES.map(r =>
                `<option value="${r}" ${Number(p?.gst_rate ?? 18) === r ? 'selected' : ''}>${r}%</option>`).join('')}</select></div>
          </div>
          <div class="grid g2" style="gap:12px">
            <div class="fr"><label class="field">Stock quantity</label>
              <input name="opening_stock" type="number" step="1" value="${p?.opening_stock ?? 0}"></div>
            <div class="fr"><label class="field">Type</label>
              <select name="is_service"><option value="true" ${p?.is_service ? 'selected' : ''}>Service</option>
                <option value="false" ${!p?.is_service ? 'selected' : ''}>Good</option></select></div>
          </div>
          <div id="mp" class="card pad-s" style="box-shadow:none;background:var(--line-2);border:none"></div>
          <div class="row" style="justify-content:flex-end;gap:9px;margin-top:16px">
            ${p ? `<button type="button" class="btn btn-danger" id="del">Delete</button>` : ''}
            <button type="button" class="btn btn-ghost" onclick="document.querySelector('.modal-x').click()">Cancel</button>
            <button type="submit" class="btn btn-teal">${p ? 'Save changes' : 'Add product'}</button>
          </div>
        </form>`);

      const f = document.getElementById('pf');
      const liveMargin = () => {
        const c = +f.querySelector('[name=cost_price]').value || 0, s = +f.querySelector('[name=selling_price]').value || 0;
        const prof = s - c, m = s ? (prof / s) * 100 : 0;
        document.getElementById('mp').innerHTML = `
          <div class="row-b"><span class="sm muted">Profit per unit</span>
            <strong style="color:${prof >= 0 ? 'var(--green)' : 'var(--red)'}">${inr2(prof)}</strong></div>
          <div class="row-b"><span class="sm muted">Margin</span>
            <strong style="color:${m >= 25 ? 'var(--green)' : m >= 10 ? 'var(--orange)' : 'var(--red)'}">${m.toFixed(1)}%</strong></div>
          <div class="row-b"><span class="sm muted">Price incl. GST</span>
            <span class="mono">${inr2(s * (1 + (+f.querySelector('[name=gst_rate]').value || 0) / 100))}</span></div>
          ${prof < 0 ? `<div class="xs" style="color:var(--red);margin-top:5px">⚠ You would lose ${inr2(-prof)} on every unit sold.</div>` : ''}`;
      };
      f.oninput = liveMargin; f.onchange = liveMargin; liveMargin();

      f.onsubmit = async (e) => {
        e.preventDefault();
        const btn = f.querySelector('button[type=submit]');
        busy(btn, true, 'Saving');
        try {
          const body = formData(f);
          await api(p ? '/api/products/' + p.id : '/api/products',
            { method: p ? 'PATCH' : 'POST', body });
          bust('/api/products'); closeModal(); toast('Saved', 'ok'); load();
        } catch (err) { busy(btn, false); toast(err.message, 'err'); }
      };
      document.getElementById('del')?.addEventListener('click', async () => {
        if (!await confirmDialog('Delete product?', `${esc(p.name)} will be removed. Existing invoices keep their line items.`)) return;
        await api('/api/products/' + p.id, { method: 'DELETE' });
        bust('/api/products'); closeModal(); toast('Deleted', 'ok'); load();
      });
    }
  }
  await load();
}

/* ------------------------------------------------- CUSTOMERS -------- */
export async function customers() {
  shell('Customers & vendors', 'GSTIN-verified parties used on your invoices and bills.',
    '<div class="skel" style="height:300px"></div>',
    `<button class="btn btn-teal btn-sm" id="new-c">+ Add party</button>`);

  const { STATE_LIST } = await import('../core.js');

  async function load() {
    const { customers: list } = await api('/api/customers');
    setBody(`
      <div class="grid g4">
        ${kpi('Total parties', list.length, 'customers + vendors', 'teal')}
        ${kpi('Customers', list.filter(c => !c.is_vendor).length, 'you invoice them', 'green')}
        ${kpi('Vendors', list.filter(c => c.is_vendor).length, 'they invoice you', 'violet')}
        ${kpi('GST registered', list.filter(c => c.gstin).length, 'B2B — eligible for ITC', 'orange')}
      </div>
      <div class="card pad mt">
        <div class="card-t" style="margin-bottom:10px">All parties</div>
        ${table([
          { label: 'Name', render: c => `<strong>${esc(c.name)}</strong>
             <div class="xs muted">${esc(c.email || '')} ${c.phone ? '· ' + esc(c.phone) : ''}</div>` },
          { label: 'GSTIN', render: c => c.gstin ? `<span class="mono sm">${esc(c.gstin)}</span>`
              : `<span class="badge b-grey">B2C</span>` },
          { label: 'State', render: c => `<span class="sm">${esc(STATE_LIST[c.state_code] || '—')}</span>` },
          { label: 'Type', render: c => `<span class="badge ${c.is_vendor ? 'b-violet' : 'b-teal'}">${c.is_vendor ? 'Vendor' : 'Customer'}</span>` },
          { label: 'Invoiced', align: 'right', mono: true, render: c => inr(c.total_billed || 0) },
          { label: '', align: 'right', render: c => `<button class="btn btn-soft btn-sm" data-e="${c.id}">Edit</button>` },
        ], list, { empty: 'No customers yet.' })}
      </div>`);
    document.getElementById('new-c').onclick = () => form();
    document.querySelectorAll('[data-e]').forEach(b =>
      b.onclick = () => form(list.find(c => c.id === b.dataset.e)));

    function form(c = null) {
      modal(c ? 'Edit party' : 'Add customer / vendor', `
        <form id="cf">
          <div class="fr"><label class="field">Name *</label><input name="name" required value="${esc(c?.name || '')}"></div>
          <div class="grid g2" style="gap:12px">
            <div class="fr"><label class="field">GSTIN</label>
              <input name="gstin" value="${esc(c?.gstin || '')}" style="text-transform:uppercase" placeholder="06AABCN4567P1Z5">
              <div class="help" id="gh">Leave blank for unregistered (B2C) parties.</div></div>
            <div class="fr"><label class="field">State *</label>
              <select name="state_code">${Object.entries(STATE_LIST).map(([k, v]) =>
                `<option value="${k}" ${c?.state_code === k ? 'selected' : ''}>${k} — ${v}</option>`).join('')}</select></div>
          </div>
          <div class="grid g2" style="gap:12px">
            <div class="fr"><label class="field">Email</label><input name="email" type="email" value="${esc(c?.email || '')}"></div>
            <div class="fr"><label class="field">Phone</label><input name="phone" value="${esc(c?.phone || '')}"></div>
          </div>
          <div class="fr"><label class="field">Address</label><textarea name="address" rows="2">${esc(c?.address || '')}</textarea></div>
          <div class="fr"><label class="field">Party type</label>
            <select name="is_vendor"><option value="0" ${!c?.is_vendor ? 'selected' : ''}>Customer (I sell to them)</option>
              <option value="1" ${c?.is_vendor ? 'selected' : ''}>Vendor (I buy from them)</option></select></div>
          <div class="row" style="justify-content:flex-end;gap:9px;margin-top:14px">
            <button type="button" class="btn btn-ghost" onclick="document.querySelector('.modal-x').click()">Cancel</button>
            <button type="submit" class="btn btn-teal">Save</button></div>
        </form>`);
      const f = document.getElementById('cf');
      const gin = f.querySelector('[name=gstin]');
      gin.onblur = async () => {
        const v = gin.value.trim(); if (!v) return;
        try {
          const r = await api('/api/gst/validate?gstin=' + encodeURIComponent(v));
          const h = document.getElementById('gh');
          h.textContent = r.valid ? `✓ Valid — ${r.state}` : `✗ ${r.message}`;
          h.style.color = r.valid ? 'var(--green)' : 'var(--red)';
          if (r.valid) f.querySelector('[name=state_code]').value = r.state_code;
        } catch {}
      };
      f.onsubmit = async (e) => {
        e.preventDefault();
        const btn = f.querySelector('button[type=submit]');
        busy(btn, true, 'Saving');
        try {
          await api(c ? '/api/customers/' + c.id : '/api/customers',
            { method: c ? 'PATCH' : 'POST', body: formData(f) });
          bust('/api/customers'); closeModal(); toast('Saved', 'ok'); load();
        } catch (err) { busy(btn, false); toast(err.message, 'err'); }
      };
    }
  }
  await load();
}
