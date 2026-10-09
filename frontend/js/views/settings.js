/* Company profile, team members, personal account. */
import { api, cached, bust, state, esc, fdate, STATE_LIST, logout } from '../core.js';
import { shell, setBody, table, toast, busy, modal, closeModal, formData, alert, confirmDialog } from '../ui.js';

export async function settings() {
  let tab = 'company';
  shell('Settings', 'Company profile, team and your own account.', '<div class="skel" style="height:300px"></div>');

  const [co, team] = await Promise.all([api('/api/company'), api('/api/company/users').catch(() => ({ users: [] }))]);

  function paint() {
    setBody(`
      <div class="tabs">
        ${[['company', 'Company profile'], ['team', 'Team members'], ['account', 'My account']]
          .map(([k, l]) => `<button data-tab="${k}" class="${tab === k ? 'on' : ''}">${l}</button>`).join('')}
      </div>
      <div id="tb" class="mt"></div>`);
    document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => { tab = b.dataset.tab; paint(); });
    const tb = document.getElementById('tb');

    if (tab === 'company') {
      tb.innerHTML = `
        <div class="grid" style="grid-template-columns:1.3fr 1fr;gap:16px;align-items:start">
          <div class="card pad-l">
            <div class="card-t" style="margin-bottom:12px">Business details</div>
            <form id="cf">
              <div class="fr"><label class="field">Legal name *</label><input name="name" required value="${esc(co.name)}"></div>
              <div class="grid g2" style="gap:12px">
                <div class="fr"><label class="field">GSTIN</label>
                  <input name="gstin" value="${esc(co.gstin || '')}" style="text-transform:uppercase">
                  <div class="help" id="gh">Printed on every invoice you issue.</div></div>
                <div class="fr"><label class="field">State (place of business) *</label>
                  <select name="state_code">${Object.entries(STATE_LIST).map(([k, v]) =>
                    `<option value="${k}" ${co.state_code === k ? 'selected' : ''}>${k} — ${v}</option>`).join('')}</select></div>
              </div>
              <div class="grid g2" style="gap:12px">
                <div class="fr"><label class="field">PAN</label><input name="pan" value="${esc(co.pan || '')}" style="text-transform:uppercase"></div>
                <div class="fr"><label class="field">Legal name</label><input name="legal_name" value="${esc(co.legal_name || '')}"></div>
              </div>
              <div class="fr"><label class="field">Registered address</label>
                <textarea name="address" rows="2">${esc(co.address || '')}</textarea></div>
              <div class="grid g3" style="gap:12px">
                <div class="fr"><label class="field">City</label><input name="city" value="${esc(co.city || '')}"></div>
                <div class="fr"><label class="field">PIN code</label><input name="pincode" value="${esc(co.pincode || '')}"></div>
                <div class="fr"><label class="field">Phone</label><input name="phone" value="${esc(co.phone || '')}"></div>
              </div>
              <div class="grid g2" style="gap:12px">
                <div class="fr"><label class="field">Billing email</label><input name="email" type="email" value="${esc(co.email || '')}"></div>
                <div class="fr"><label class="field">Invoice number prefix</label>
                  <input name="invoice_prefix" value="${esc(co.invoice_prefix || 'INV')}">
                  <div class="help">Next invoice: ${esc(co.invoice_prefix || 'INV')}/${new Date().getFullYear()}/00${(co.invoice_seq || 0) + 1}</div></div>
              </div>
              <div class="fr"><label class="field">Website</label>
                <input name="website" value="${esc(co.website || '')}" placeholder="https://company.in"></div>
              <button class="btn btn-teal mt" type="submit">Save company profile</button>
            </form>
          </div>
          <div class="col" style="gap:16px">
            <div class="card pad">
              <div class="card-t" style="margin-bottom:9px">Account</div>
              <div class="stat-line"><span>Company ID</span><span class="mono xs">${esc(co.id)}</span></div>
              <div class="stat-line"><span>Created</span><span>${fdate(co.created_at)}</span></div>
              <div class="stat-line"><span>Plan</span><strong>${esc(co.plan_name || co.plan_code || '—')}</strong></div>
              <div class="stat-line"><span>Status</span><span class="badge b-teal">${esc(co.subscription_status || 'trialing')}</span></div>
              <a class="btn btn-soft btn-sm btn-block mt-s" href="/app/plans">Manage subscription →</a>
            </div>
            <div class="card pad">
              <div class="card-t" style="margin-bottom:9px">Data isolation</div>
              <p class="sm muted">Every record you create is tagged with your company ID and filtered on the
                server for each request. No other tenant can read or write your invoices, products or analyses.</p>
            </div>
          </div>
        </div>`;

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
          await api('/api/company', { method: 'PATCH', body: formData(f) });
          bust('/api/company'); toast('Company profile saved', 'ok');
          busy(btn, false);
        } catch (err) { busy(btn, false); toast(err.message, 'err'); }
      };
    }

    if (tab === 'team') {
      tb.innerHTML = `
        <div class="card pad">
          <div class="card-h"><div class="card-t">Team members</div>
            <button class="btn btn-teal btn-sm" id="inv">+ Add member</button></div>
          ${table([
            { label: 'Name', render: u => `<strong>${esc(u.name)}</strong>${u.id === state.user.id ? ' <span class="badge b-grey">you</span>' : ''}` },
            { label: 'Email', render: u => `<span class="sm">${esc(u.email)}</span>` },
            { label: 'Role', render: u => `<span class="badge ${u.role === 'owner' ? 'b-violet' : 'b-teal'}">${esc(u.role)}</span>` },
            { label: 'Added', render: u => fdate(u.created_at) },
            { label: 'Last seen', render: u => u.last_login_at ? fdate(u.last_login_at) : '—' },
            { label: '', align: 'right', render: u => (state.user.role === 'owner' && u.id !== state.user.id)
                ? `<button class="btn btn-soft btn-sm" data-rm="${u.id}">Remove</button>` : '' },
          ], team.users)}
          <div class="help mt-s">Roles: <strong>owner</strong> full control including billing ·
            <strong>admin</strong> everything except billing · <strong>member</strong> create invoices and run analyses ·
            <strong>viewer</strong> read-only.</div>
        </div>`;
      document.getElementById('inv').onclick = () => {
        modal('Add a team member', `
          <form id="uf">
            <div class="fr"><label class="field">Name *</label><input name="name" required></div>
            <div class="fr"><label class="field">Email *</label><input name="email" type="email" required></div>
            <div class="fr"><label class="field">Temporary password *</label>
              <input name="password" required minlength="8" value="costleak${new Date().getFullYear()}">
              <div class="help">Share it with them; they can change it after signing in.</div></div>
            <div class="fr"><label class="field">Role</label>
              <select name="role">${['admin', 'member', 'viewer'].map(r => `<option>${r}</option>`).join('')}</select></div>
            <div class="row" style="justify-content:flex-end;gap:9px;margin-top:14px">
              <button type="button" class="btn btn-ghost" onclick="document.querySelector('.modal-x').click()">Cancel</button>
              <button type="submit" class="btn btn-teal">Add member</button></div>
          </form>`);
        document.getElementById('uf').onsubmit = async (e) => {
          e.preventDefault();
          const btn = e.target.querySelector('button[type=submit]');
          busy(btn, true, 'Adding');
          try {
            await api('/api/company/users', { method: 'POST', body: formData(e.target) });
            closeModal(); toast('Member added', 'ok'); settings();
          } catch (err) {
            busy(btn, false);
            if (err.data?.code === 'plan_limit') toast(err.data.message, 'err');
            else toast(err.message, 'err');
          }
        };
      };
      document.querySelectorAll('[data-rm]').forEach(b => b.onclick = async () => {
        if (!await confirmDialog('Remove member?', 'They lose access immediately. Their invoices stay.')) return;
        await api('/api/company/users/' + b.dataset.rm, { method: 'DELETE' });
        toast('Removed', 'ok'); settings();
      });
    }

    if (tab === 'account') {
      tb.innerHTML = `
        <div class="grid g2" style="align-items:start">
          <div class="card pad-l">
            <div class="card-t" style="margin-bottom:12px">Your profile</div>
            <form id="me">
              <div class="fr"><label class="field">Name</label><input name="name" value="${esc(state.user.name)}"></div>
              <div class="fr"><label class="field">Email</label><input value="${esc(state.user.email)}" disabled>
                <div class="help">Your email is your login and cannot be changed here.</div></div>
              <div class="fr"><label class="field">Role</label><input value="${esc(state.user.role)}" disabled></div>
              <button class="btn btn-primary mt" type="submit">Save</button>
            </form>
          </div>
          <div class="card pad-l">
            <div class="card-t" style="margin-bottom:12px">Change password</div>
            <form id="pw">
              <div class="fr"><label class="field">Current password</label><input name="current_password" type="password" required></div>
              <div class="fr"><label class="field">New password</label><input name="new_password" type="password" required minlength="8"></div>
              <button class="btn btn-primary mt" type="submit">Update password</button>
            </form>
            <hr style="border:none;border-top:1px solid var(--line);margin:20px 0">
            <button class="btn btn-ghost btn-block" id="out">Sign out of this device</button>
          </div>
        </div>`;
      document.getElementById('me').onsubmit = async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button');
        busy(btn, true, 'Saving');
        try {
          const r = await api('/api/auth/me', { method: 'PATCH', body: formData(e.target) });
          state.user = r.user; localStorage.setItem('cl.user', JSON.stringify(r.user));
          toast('Saved', 'ok'); busy(btn, false);
        } catch (err) { busy(btn, false); toast(err.message, 'err'); }
      };
      document.getElementById('pw').onsubmit = async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button');
        busy(btn, true, 'Updating');
        try {
          await api('/api/auth/password', { method: 'POST', body: formData(e.target) });
          e.target.reset(); toast('Password updated', 'ok'); busy(btn, false);
        } catch (err) { busy(btn, false); toast(err.message, 'err'); }
      };
      document.getElementById('out').onclick = () => logout();
    }
  }
  paint();
}
