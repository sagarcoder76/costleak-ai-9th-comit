/* Upload expense workbook → run the 8-rule cost-leak engine. */
import { api, bust, state, esc, go, inr, inrShort } from '../core.js';
import { shell, setBody, alert, toast, busy } from '../ui.js';

export async function upload() {
  shell('Upload expense data', 'Excel or CSV in, ranked rupee savings out. Nothing leaves your database.', `
    <div class="grid" style="grid-template-columns:1.25fr 1fr;gap:16px;align-items:start">
      <div class="card pad-l">
        <div class="dropzone" id="dz">
          <div style="font-size:40px">📂</div>
          <h3 style="margin:10px 0 6px">Drop your workbook here</h3>
          <p class="sm muted">.xlsx or .csv · up to 10 MB · processed in under a minute</p>
          <input type="file" id="file" accept=".xlsx,.xls,.csv" hidden>
          <button class="btn btn-primary mt" id="pick">Choose file</button>
          <div class="xs muted mt-s">or <a href="#" id="sample" style="color:var(--teal-ink);font-weight:650">run the built-in sample company</a></div>
        </div>
        <div id="out" class="mt"></div>
      </div>

      <div class="col" style="gap:16px">
        <div class="card pad">
          <div class="card-t" style="margin-bottom:9px">Expected sheets</div>
          <div class="col" style="gap:10px">
            ${[['Expenses', 'date, vendor, category, department, amount, description'],
               ['Subscriptions', 'tool, vendor, monthly_cost, seats_paid, seats_used, renewal_date, category'],
               ['Manual_Tasks', 'task, department, frequency, times_per_month, minutes_each, people, hourly_cost'],
               ['Attendance (optional)', 'department, month, overtime_hours, hourly_cost']]
              .map(([n, c]) => `<div><strong class="sm">${n}</strong>
                <div class="xs muted mono" style="word-break:break-word">${c}</div></div>`).join('')}
          </div>
          <div class="help mt-s">Column names are matched loosely — extra columns are ignored and
            missing optional sheets are skipped.</div>
          <a class="btn btn-soft btn-sm btn-block mt" href="/api/exports/template.xlsx?t=${state.token}">⬇ Download blank template</a>
        </div>
        <div class="card pad">
          <div class="card-t" style="margin-bottom:9px">What runs on your file</div>
          <div class="col" style="gap:6px">
            ${['Duplicate payments (same vendor + amount, 20-day window)',
               'Duplicate / overlapping software tools',
               'Unused software seats',
               'Vendor price increases above 20%',
               'High-cost, low-usage subscriptions',
               'Upcoming renewals worth reviewing',
               'Manual work that can be automated',
               'Departmental overtime patterns']
              .map(r => `<div class="sm">✓ ${r}</div>`).join('')}
          </div>
          <div class="help mt-s">Every number is computed from your rows at runtime. Findings are de-duplicated
            so the same rupee is never counted twice.</div>
        </div>
      </div>
    </div>`);

  const dz = document.getElementById('dz');
  const file = document.getElementById('file');
  const out = document.getElementById('out');

  document.getElementById('pick').onclick = () => file.click();
  file.onchange = () => file.files[0] && send(file.files[0]);

  ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => {
    e.preventDefault(); dz.classList.add('over');
  }));
  ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => {
    e.preventDefault(); dz.classList.remove('over');
  }));
  dz.addEventListener('drop', e => {
    const f = e.dataTransfer.files[0];
    if (f) send(f);
  });

  document.getElementById('sample').onclick = async (e) => {
    e.preventDefault();
    out.innerHTML = progress('Loading the sample company…');
    try {
      const r = await api('/api/analysis/sample', { method: 'POST' });
      done(r);
    } catch (err) { out.innerHTML = alert('err', esc(err.message)); }
  };

  async function send(f) {
    if (!/\.(xlsx|xls|csv)$/i.test(f.name)) return toast('Please choose an .xlsx or .csv file', 'err');
    if (f.size > 10 * 1024 * 1024) return toast('File is larger than 10 MB', 'err');
    out.innerHTML = progress(`Analysing <strong>${esc(f.name)}</strong>…`);
    const fd = new FormData();
    fd.append('file', f);
    try {
      const r = await api('/api/analysis/upload', { method: 'POST', body: fd });
      done(r);
    } catch (err) {
      out.innerHTML = err.data?.code === 'plan_limit'
        ? alert('warn', `<strong>Plan limit reached.</strong> ${esc(err.data.message)}
            <a href="/app/plans" style="font-weight:700">Upgrade →</a>`)
        : alert('err', esc(err.message));
    }
  }

  function progress(label) {
    return `<div class="card pad" style="box-shadow:none;background:var(--line-2);border:none">
      <div class="row" style="gap:10px"><span class="spinner"></span><span class="sm">${label}</span></div>
      <div class="help mt-s">Parsing sheets → normalising columns → running 8 detection rules → de-duplicating claims.</div>
    </div>`;
  }

  function done(r) {
    bust('/api/analysis');
    const k = r.result.kpis;
    out.innerHTML = `
      ${alert('ok', `<strong>Analysis complete.</strong> ${r.result.findings.length} findings across ${k.months_covered || 1} month(s) of data.`)}
      <div class="grid g3 mt">
        <div class="card pad center"><div class="xs muted">MONTHLY SPEND</div>
          <div style="font-size:23px;font-weight:800">${inrShort(k.monthly_spend)}</div></div>
        <div class="card pad center"><div class="xs muted">ESTIMATED WASTE</div>
          <div style="font-size:23px;font-weight:800;color:var(--red)">${inrShort(k.monthly_waste)}</div></div>
        <div class="card pad center"><div class="xs muted">ANNUAL OPPORTUNITY</div>
          <div style="font-size:23px;font-weight:800;color:var(--green)">${inrShort(k.annual_savings)}</div></div>
      </div>
      <a class="btn btn-teal btn-block btn-lg mt" href="/app/cost-leaks">See all findings →</a>`;
    toast('Analysis complete', 'ok');
  }
}
