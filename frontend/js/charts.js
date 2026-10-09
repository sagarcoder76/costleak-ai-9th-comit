/* Minimal canvas chart library (~6 KB, no dependencies).
   Replaces Chart.js so no CDN request blocks first paint.
   Supports: bar, hbar, line/area, donut, sparkline + hover tooltips. */
import { inrShort, inr, esc } from './core.js';

export const PALETTE = ['#0B1F3A', '#0FB5A0', '#3B82F6', '#F59E0B', '#E25555',
                        '#7C5CFF', '#1FA971', '#38BDF8', '#EC4899', '#64748B'];

const DPR = () => Math.min(window.devicePixelRatio || 1, 2);
const css = (name, fb) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fb;

function setup(canvas) {
  const parent = canvas.parentElement;
  const w = parent.clientWidth, h = parent.clientHeight || 240;
  const dpr = DPR();
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  ctx.font = "11px Inter,system-ui,sans-serif";
  return { ctx, w, h };
}

function tooltip(canvas, hits) {
  let tip = canvas._tip;
  if (!tip) {
    tip = document.createElement('div');
    tip.style.cssText = `position:absolute;pointer-events:none;background:#0B1F3A;color:#fff;
      padding:6px 10px;border-radius:8px;font-size:11.5px;font-weight:600;white-space:nowrap;
      opacity:0;transition:opacity .12s;z-index:20;box-shadow:0 8px 24px -10px rgba(0,0,0,.6)`;
    canvas.parentElement.style.position = 'relative';
    canvas.parentElement.appendChild(tip);
    canvas._tip = tip;
  }
  canvas.onmousemove = (e) => {
    const r = canvas.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    const hit = hits.find(h => x >= h.x0 && x <= h.x1 && y >= h.y0 && y <= h.y1);
    if (hit) {
      tip.innerHTML = hit.label;
      tip.style.opacity = '1';
      tip.style.left = Math.min(Math.max(x + 12, 4), r.width - tip.offsetWidth - 4) + 'px';
      tip.style.top = Math.max(y - 34, 2) + 'px';
      canvas.style.cursor = 'pointer';
    } else { tip.style.opacity = '0'; canvas.style.cursor = 'default'; }
  };
  canvas.onmouseleave = () => { tip.style.opacity = '0'; };
}

function niceMax(v) {
  if (v <= 0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / mag;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag;
}

function axes(ctx, w, h, pad, max, lines = 4) {
  const line = css('--line-2', '#EEF2F8'), muted = css('--muted', '#7589A3');
  ctx.strokeStyle = line; ctx.fillStyle = muted; ctx.lineWidth = 1;
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
  for (let i = 0; i <= lines; i++) {
    const y = pad.t + (h - pad.t - pad.b) * (i / lines);
    ctx.beginPath(); ctx.moveTo(pad.l, y + .5); ctx.lineTo(w - pad.r, y + .5); ctx.stroke();
    ctx.fillText(inrShort(max * (1 - i / lines)), pad.l - 7, y);
  }
}

function clipLabel(ctx, text, maxW) {
  let t = String(text);
  if (ctx.measureText(t).width <= maxW) return t;
  while (t.length > 1 && ctx.measureText(t + '…').width > maxW) t = t.slice(0, -1);
  return t + '…';
}

/* ------------------------------------------------------------- bar --- */
export function bar(id, data, opts = {}) {
  const canvas = document.getElementById(id); if (!canvas) return;
  const { ctx, w, h } = setup(canvas);
  const items = data.slice(0, opts.limit || 12);
  if (!items.length) return empty(ctx, w, h);
  const pad = { t: 12, r: 10, b: 42, l: 54 };
  const max = niceMax(Math.max(...items.map(d => d.value), 1));
  axes(ctx, w, h, pad, max);
  const plotW = w - pad.l - pad.r, plotH = h - pad.t - pad.b;
  const step = plotW / items.length, bw = Math.min(step * 0.62, 46);
  const hits = [];
  items.forEach((d, i) => {
    const bh = Math.max((d.value / max) * plotH, d.value > 0 ? 2 : 0);
    const x = pad.l + step * i + (step - bw) / 2, y = pad.t + plotH - bh;
    const g = ctx.createLinearGradient(0, y, 0, pad.t + plotH);
    const c = opts.colors ? opts.colors[i % opts.colors.length] : (opts.color || css('--teal', '#0FB5A0'));
    g.addColorStop(0, c); g.addColorStop(1, c + 'B0');
    ctx.fillStyle = g;
    roundRect(ctx, x, y, bw, bh, 5); ctx.fill();
    ctx.fillStyle = css('--muted', '#7589A3');
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    ctx.save(); ctx.translate(x + bw / 2, pad.t + plotH + 7);
    if (step < 62) { ctx.rotate(-0.42); ctx.textAlign = 'right'; }
    ctx.fillText(clipLabel(ctx, d.label, step < 62 ? 70 : step - 6), 0, 0); ctx.restore();
    hits.push({ x0: x - 3, x1: x + bw + 3, y0: pad.t, y1: pad.t + plotH,
                label: `${esc(d.label)}: <b>${inr(d.value)}</b>` });
  });
  tooltip(canvas, hits);
}

/* ------------------------------------------------------- horizontal -- */
export function hbar(id, data, opts = {}) {
  const canvas = document.getElementById(id); if (!canvas) return;
  const { ctx, w, h } = setup(canvas);
  const items = data.slice(0, opts.limit || 10);
  if (!items.length) return empty(ctx, w, h);
  const pad = { t: 6, r: 58, b: 6, l: Math.min(130, w * 0.36) };
  const max = Math.max(...items.map(d => d.value), 1);
  const plotW = w - pad.l - pad.r, rowH = (h - pad.t - pad.b) / items.length;
  const bh = Math.min(rowH * 0.6, 20);
  const hits = [];
  items.forEach((d, i) => {
    const y = pad.t + rowH * i + (rowH - bh) / 2;
    const bw = Math.max((d.value / max) * plotW, 2);
    ctx.fillStyle = css('--line-2', '#EEF2F8');
    roundRect(ctx, pad.l, y, plotW, bh, 5); ctx.fill();
    const g = ctx.createLinearGradient(pad.l, 0, pad.l + bw, 0);
    g.addColorStop(0, opts.color || css('--teal', '#0FB5A0'));
    g.addColorStop(1, opts.color2 || css('--blue', '#3B82F6'));
    ctx.fillStyle = g;
    roundRect(ctx, pad.l, y, bw, bh, 5); ctx.fill();
    ctx.fillStyle = css('--body', '#44536A'); ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    ctx.fillText(clipLabel(ctx, d.label, pad.l - 10), pad.l - 8, y + bh / 2);
    ctx.fillStyle = css('--ink', '#0E1C2F'); ctx.textAlign = 'left';
    ctx.font = "600 11px Inter,sans-serif";
    ctx.fillText(inrShort(d.value), pad.l + bw + 7, y + bh / 2);
    ctx.font = "11px Inter,sans-serif";
    hits.push({ x0: pad.l, x1: pad.l + plotW, y0: y - 4, y1: y + bh + 4,
                label: `${esc(d.label)}: <b>${inr(d.value)}</b>` });
  });
  tooltip(canvas, hits);
}

/* ------------------------------------------------------------ line --- */
export function line(id, data, opts = {}) {
  const canvas = document.getElementById(id); if (!canvas) return;
  const { ctx, w, h } = setup(canvas);
  if (!data.length) return empty(ctx, w, h);
  const pad = { t: 12, r: 12, b: 32, l: 54 };
  const max = niceMax(Math.max(...data.map(d => d.value), 1));
  axes(ctx, w, h, pad, max);
  const plotW = w - pad.l - pad.r, plotH = h - pad.t - pad.b;
  const X = i => pad.l + (data.length === 1 ? plotW / 2 : plotW * i / (data.length - 1));
  const Y = v => pad.t + plotH - (v / max) * plotH;
  const col = opts.color || css('--teal', '#0FB5A0');

  ctx.beginPath(); ctx.moveTo(X(0), Y(data[0].value));
  data.forEach((d, i) => { if (i) ctx.lineTo(X(i), Y(d.value)); });
  ctx.lineTo(X(data.length - 1), pad.t + plotH); ctx.lineTo(X(0), pad.t + plotH); ctx.closePath();
  const g = ctx.createLinearGradient(0, pad.t, 0, pad.t + plotH);
  g.addColorStop(0, col + '44'); g.addColorStop(1, col + '04');
  ctx.fillStyle = g; ctx.fill();

  ctx.beginPath(); ctx.moveTo(X(0), Y(data[0].value));
  data.forEach((d, i) => { if (i) ctx.lineTo(X(i), Y(d.value)); });
  ctx.strokeStyle = col; ctx.lineWidth = 2.4; ctx.lineJoin = 'round'; ctx.stroke();

  const hits = [];
  data.forEach((d, i) => {
    ctx.beginPath(); ctx.arc(X(i), Y(d.value), 3.6, 0, 7);
    ctx.fillStyle = css('--card', '#fff'); ctx.fill();
    ctx.strokeStyle = col; ctx.lineWidth = 2.2; ctx.stroke();
    ctx.fillStyle = css('--muted', '#7589A3'); ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    if (data.length <= 14 || i % Math.ceil(data.length / 10) === 0)
      ctx.fillText(clipLabel(ctx, d.label, plotW / data.length + 16), X(i), pad.t + plotH + 8);
    hits.push({ x0: X(i) - 14, x1: X(i) + 14, y0: pad.t, y1: pad.t + plotH,
                label: `${esc(d.label)}: <b>${inr(d.value)}</b>` });
  });
  tooltip(canvas, hits);
}

/* ----------------------------------------------------------- donut --- */
export function donut(id, data, opts = {}) {
  const canvas = document.getElementById(id); if (!canvas) return;
  const { ctx, w, h } = setup(canvas);
  const items = data.filter(d => d.value > 0).slice(0, opts.limit || 7);
  if (!items.length) return empty(ctx, w, h);
  const total = items.reduce((s, d) => s + d.value, 0);
  const legendW = w > 420 ? Math.min(168, w * 0.42) : 0;
  const cx = (w - legendW) / 2, cy = h / 2;
  const R = Math.min(cx, cy) - 8, r = R * 0.6;
  let a0 = -Math.PI / 2;
  const hits = [];
  items.forEach((d, i) => {
    const a1 = a0 + (d.value / total) * Math.PI * 2;
    ctx.beginPath(); ctx.arc(cx, cy, R, a0, a1); ctx.arc(cx, cy, r, a1, a0, true); ctx.closePath();
    ctx.fillStyle = PALETTE[i % PALETTE.length]; ctx.fill();
    ctx.strokeStyle = css('--card', '#fff'); ctx.lineWidth = 2; ctx.stroke();
    const mid = (a0 + a1) / 2, mr = (R + r) / 2;
    hits.push({ x0: cx + Math.cos(mid) * mr - 22, x1: cx + Math.cos(mid) * mr + 22,
                y0: cy + Math.sin(mid) * mr - 22, y1: cy + Math.sin(mid) * mr + 22,
                label: `${esc(d.label)}: <b>${inr(d.value)}</b> (${(d.value / total * 100).toFixed(1)}%)` });
    a0 = a1;
  });
  ctx.fillStyle = css('--ink', '#0E1C2F'); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.font = "700 15px Inter,sans-serif"; ctx.fillText(inrShort(total), cx, cy - 5);
  ctx.font = "10.5px Inter,sans-serif"; ctx.fillStyle = css('--muted', '#7589A3');
  ctx.fillText(opts.centerLabel || 'total', cx, cy + 11);

  if (legendW) {
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.font = "11px Inter,sans-serif";
    const lx = w - legendW + 6;
    const step = Math.min(21, (h - 12) / items.length);
    items.forEach((d, i) => {
      const y = (h - step * items.length) / 2 + step * i + step / 2;
      ctx.fillStyle = PALETTE[i % PALETTE.length];
      roundRect(ctx, lx, y - 4, 8, 8, 2); ctx.fill();
      ctx.fillStyle = css('--body', '#44536A');
      ctx.fillText(clipLabel(ctx, d.label, legendW - 58), lx + 13, y);
      ctx.fillStyle = css('--muted', '#7589A3'); ctx.textAlign = 'right';
      ctx.fillText(`${(d.value / total * 100).toFixed(0)}%`, w - 4, y);
      ctx.textAlign = 'left';
    });
  }
  tooltip(canvas, hits);
}

/* -------------------------------------------------------- sparkline -- */
export function spark(id, values, opts = {}) {
  const canvas = document.getElementById(id); if (!canvas) return;
  const { ctx, w, h } = setup(canvas);
  if (!values.length) return;
  const max = Math.max(...values, 1), min = Math.min(...values, 0);
  const X = i => (w - 4) * i / Math.max(values.length - 1, 1) + 2;
  const Y = v => h - 3 - ((v - min) / (max - min || 1)) * (h - 6);
  ctx.beginPath(); values.forEach((v, i) => i ? ctx.lineTo(X(i), Y(v)) : ctx.moveTo(X(i), Y(v)));
  ctx.strokeStyle = opts.color || css('--teal', '#0FB5A0'); ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.stroke();
  ctx.lineTo(X(values.length - 1), h); ctx.lineTo(X(0), h); ctx.closePath();
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, (opts.color || '#0FB5A0') + '38'); g.addColorStop(1, '#ffffff00');
  ctx.fillStyle = g; ctx.fill();
}

/* ----------------------------------------------------------- utils --- */
function roundRect(ctx, x, y, w, h, r) {
  r = Math.min(r, w / 2, Math.abs(h) / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
}
function empty(ctx, w, h) {
  ctx.fillStyle = css('--muted', '#7589A3'); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText('No data for this period', w / 2, h / 2);
}

/* Redraw all registered charts on resize (debounced). */
const registry = [];
export function draw(fn) { registry.push(fn); fn(); }
export function clearCharts() { registry.length = 0; }
let rt;
window.addEventListener('resize', () => {
  clearTimeout(rt);
  rt = setTimeout(() => registry.forEach(f => { try { f(); } catch {} }), 160);
});
