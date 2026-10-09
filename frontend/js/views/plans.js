/* Subscription plans + Razorpay checkout (test keys, simulated fallback). */
import { api, cached, bust, state, inr, inrShort, esc, fdate, go } from '../core.js';
import { shell, setBody, kpi, table, alert, toast, busy, modal, closeModal, statusBadge } from '../ui.js';

export async function plans() {
  shell('Plans & billing', 'Upgrade, downgrade and see every payment.', '<div class="skel" style="height:330px"></div>');
  await render();
}

async function render() {
  const d = await api('/api/billing/overview');
  const cur = d.subscription, cycleYearly = false;
  let yearly = false;

  const paint = () => setBody(`
    ${cur.status === 'trialing' ? alert('info',
      `<strong>You are on a free trial.</strong> ${cur.trial_days_left} day${cur.trial_days_left === 1 ? '' : 's'} left
       (ends ${fdate(cur.trial_ends_at)}). Pick a plan to keep access after that.`) : ''}
    ${d.mode === 'simulated' ? alert('warn',
      `<strong>Demo payment mode.</strong> No Razorpay API keys are configured, so checkout is simulated —
       plans activate instantly without a real charge. Set <span class="mono">RAZORPAY_KEY_ID</span> and
       <span class="mono">RAZORPAY_KEY_SECRET</span> to enable live test-mode checkout.`) : alert('ok',
      `<strong>Razorpay ${esc(d.mode)} mode active.</strong> Checkout opens the Razorpay window; use test card
       4111 1111 1111 1111 with any future expiry and CVV.`)}

    <div class="grid g4 mt">
      ${kpi('Current plan', esc(cur.plan_name), cur.status === 'trialing' ? 'trial' : esc(cur.status), 'teal')}
      ${kpi('Billing', cur.billing_cycle === 'yearly' ? 'Yearly' : 'Monthly',
            cur.next_billing_at ? 'renews ' + fdate(cur.next_billing_at) : 'no renewal scheduled', 'violet')}
      ${kpi('Users', `${d.usage.users} / ${d.limits.users}`, 'seats in your account',
            d.usage.users >= d.limits.users ? 'red' : 'green')}
      ${kpi('Invoices this month', `${d.usage.invoices} / ${d.limits.invoices_per_month}`, 'plan allowance',
            d.usage.invoices >= d.limits.invoices_per_month ? 'red' : 'green')}
    </div>

    <div class="card pad mt">
      <div class="card-h"><div class="card-t">Choose a plan</div>
        <div class="seg"><button id="m" class="${!yearly ? 'on' : ''}">Monthly</button>
          <button id="y" class="${yearly ? 'on' : ''}">Yearly — 2 months free</button></div></div>
      <div class="grid g3 mt-s">
        ${d.plans.map(p => {
          const price = yearly ? p.price_yearly : p.price_monthly;
          const active = p.code === cur.plan_code && cur.status === 'active';
          return `<div class="card pad-l" style="border:2px solid ${p.popular ? 'var(--teal)' : 'var(--line)'};box-shadow:none;position:relative">
            ${p.popular ? '<span class="badge b-teal" style="position:absolute;top:-10px;left:20px">POPULAR</span>' : ''}
            <h3 style="font-size:18px">${esc(p.name)}</h3>
            <p class="sm muted" style="min-height:38px">${esc(p.tagline)}</p>
            <div style="margin:10px 0 4px"><span style="font-size:29px;font-weight:800">₹${price.toLocaleString('en-IN')}</span>
              <span class="sm muted">/${yearly ? 'year' : 'month'}</span></div>
            <div class="xs muted" style="margin-bottom:14px">+ 18% GST${yearly ? ` · ₹${Math.round(p.price_yearly / 12).toLocaleString('en-IN')}/mo effective` : ''}</div>
            <button class="btn ${active ? 'btn-soft' : p.popular ? 'btn-teal' : 'btn-primary'} btn-block"
              data-buy="${p.code}" ${active ? 'disabled' : ''}>
              ${active ? '✓ Current plan' : cur.status === 'trialing' ? 'Activate ' + esc(p.name) : 'Switch to ' + esc(p.name)}</button>
            <div class="col" style="gap:7px;margin-top:14px">
              ${p.features.map(f => `<div class="sm">✓ ${esc(f)}</div>`).join('')}</div>
            <div class="xs muted" style="margin-top:12px;padding-top:10px;border-top:1px solid var(--line)">
              ${p.limits.users} users · ${p.limits.invoices_per_month.toLocaleString('en-IN')} invoices/mo ·
              ${p.limits.products.toLocaleString('en-IN')} products · ${p.limits.analyses_per_month} analyses/mo</div>
          </div>`;
        }).join('')}
      </div>
    </div>

    <div class="card pad mt">
      <div class="card-t" style="margin-bottom:10px">Payment history</div>
      ${table([
        { label: 'Date', render: r => fdate(r.created_at) },
        { label: 'Plan', render: r => `${esc(r.plan_name)} <span class="xs muted">${esc(r.billing_cycle)}</span>` },
        { label: 'Reference', render: r => `<span class="mono xs">${esc(r.reference || r.id)}</span>` },
        { label: 'Method', render: r => `<span class="sm">${esc(r.method || 'razorpay')}</span>` },
        { label: 'Amount', align: 'right', mono: true, render: r => inr(r.amount) },
        { label: 'Status', align: 'right', render: r => statusBadge(r.status) },
      ], d.payments, { empty: 'No payments yet — you are still on the free trial.' })}
    </div>`);

  paint();
  wire();

  function wire() {
    document.getElementById('m').onclick = () => { yearly = false; paint(); wire(); };
    document.getElementById('y').onclick = () => { yearly = true; paint(); wire(); };
    document.querySelectorAll('[data-buy]').forEach(b => b.onclick = () => checkout(b, b.dataset.buy, yearly));
  }

  async function checkout(btn, code, isYearly) {
    busy(btn, true, 'Starting checkout');
    try {
      const order = await api('/api/billing/checkout', { method: 'POST',
        body: { plan_code: code, billing_cycle: isYearly ? 'yearly' : 'monthly' } });

      if (order.mode === 'simulated') {
        closeModal();
        modal('Confirm your plan', `
          <p class="sm muted">Demo payment mode — no card will be charged.</p>
          <div class="card pad mt" style="box-shadow:none;background:var(--line-2);border:none">
            <div class="stat-line"><span>Plan</span><strong>${esc(order.plan_name)}</strong></div>
            <div class="stat-line"><span>Billing</span><strong>${esc(order.billing_cycle)}</strong></div>
            <div class="stat-line"><span>Base amount</span><span class="mono">${inr(order.base_amount)}</span></div>
            <div class="stat-line"><span>GST 18%</span><span class="mono">${inr(order.gst_amount)}</span></div>
            <div class="stat-line" style="border-top:2px solid var(--navy);padding-top:8px">
              <strong>Total</strong><strong style="font-size:18px">${inr(order.amount)}</strong></div>
          </div>
          <button class="btn btn-teal btn-block btn-lg mt" id="pay">Simulate successful payment</button>
          <div class="help center mt-s">In live mode this button opens the Razorpay checkout window.</div>`);
        document.getElementById('pay').onclick = async (e) => {
          busy(e.target, true, 'Processing');
          await finish(order.order_id, { simulated: true });
        };
        busy(btn, false);
        return;
      }

      // Real Razorpay checkout (test keys configured).
      await loadRzp();
      const rzp = new window.Razorpay({
        key: order.key_id, order_id: order.order_id, amount: order.amount_paise,
        currency: 'INR', name: 'CostLeak AI', description: order.plan_name + ' plan',
        prefill: { email: state.user.email, name: state.user.name },
        theme: { color: '#0F2A4A' },
        handler: (resp) => finish(order.order_id, resp),
        modal: { ondismiss: () => busy(btn, false) },
      });
      rzp.open();
    } catch (e) { busy(btn, false); toast(e.message, 'err'); }
  }

  async function finish(orderId, resp) {
    try {
      await api('/api/billing/verify', { method: 'POST', body: { order_id: orderId, ...resp } });
      bust('/api/billing'); bust('/api/company');
      closeModal();
      toast('Plan activated 🎉', 'ok');
      render();
    } catch (e) { toast(e.message, 'err'); }
  }
}

function loadRzp() {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.onload = res; s.onerror = () => rej(new Error('Could not load the Razorpay checkout script'));
    document.head.appendChild(s);
  });
}
