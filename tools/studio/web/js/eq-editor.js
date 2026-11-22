/* Редактор EQ: SVG-крива 20 Гц…11 кГц з вузлами (Pointer Events, колесо = Q, стрілки) і таблиця смуг. */
import { AC } from "./audio.js";
import { EQ, eqApply, eqLiveUpdate } from "./eq-live.js";
import { $, esc } from "./util.js";

export const EQ_NAMES = { highpass: "Зріз низів", lowshelf: "Низи (полиця)", peaking: "Смуга", highshelf: "Верхи (полиця)", lowpass: "Зріз верхів" };
const COLORS = ["#e4572e", "#f0a441", "#46c46a", "#4aa8e8", "#b39ae8", "#e86ab0", "#7bd3c4", "#c9c24a"];
const W = 340, H = 156, PL = 30, PR = 10, PT = 8, PB = 18, F0 = 20, F1 = 11000, DB = 12, MAXQ = 18;   // 11 кГц — межа файлу гри (22 кГц дискретизації)

const px = (f) => PL + Math.log(f / F0) / Math.log(F1 / F0) * (W - PL - PR);
const fx = (x) => F0 * Math.pow(F1 / F0, (x - PL) / (W - PL - PR));
const py = (db) => PT + (DB - db) / (2 * DB) * (H - PT - PB);
const dyb = (y) => DB - (y - PT) / (H - PT - PB) * 2 * DB;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const hasGain = (b) => b.type !== "highpass" && b.type !== "lowpass";
const hasQ = (b) => b.type !== "lowshelf" && b.type !== "highshelf";
const fmtHz = (f) => (f >= 1000 ? `${+(f / 1000).toFixed(2)} кГц` : `${f} Гц`).replace(".", ",");
const label = (b, i, what) => `Смуга ${i + 1} (${fmtHz(b.freq_hz)}) — ${what}`;

function curve(P, amount) {
  const N = 120, fr = new Float32Array(N), mag = new Float32Array(N), ph = new Float32Array(N), tot = new Float32Array(N).fill(Math.pow(10, P.gain_db / 20));
  for (let i = 0; i < N; i++) fr[i] = F0 * Math.pow(F1 / F0, i / (N - 1));
  for (const b of P.bands) {
    const n = AC.createBiquadFilter(); eqApply(n, b, amount); n.getFrequencyResponse(fr, mag, ph);
    for (let i = 0; i < N; i++) tot[i] *= Number.isFinite(mag[i]) ? mag[i] : 1;   // за Найквістом getFrequencyResponse дає NaN
  }
  return Array.from(fr, (f, i) => `${i ? "L" : "M"}${px(f).toFixed(1)},${py(clamp(20 * Math.log10(Math.max(1e-4, tot[i])), -DB - 2, DB + 2)).toFixed(1)}`).join("");
}

export function eqSvg() {
  const grid = [-12, -6, 0, 6, 12].map((db) => `<line class="g${db ? "" : " z"}" x1="${PL}" x2="${W - PR}" y1="${py(db)}" y2="${py(db)}"/><text class="t" x="${PL - 4}" y="${py(db) + 3}" text-anchor="end">${db > 0 ? "+" : ""}${db}</text>`).join("")
    + [[100, "100"], [1000, "1k"], [10000, "10k"]].map(([f, t]) => `<line class="g" x1="${px(f)}" x2="${px(f)}" y1="${PT}" y2="${H - PB}"/><text class="t" x="${px(f)}" y="${H - 5}" text-anchor="middle">${t}</text>`).join("");
  const nodes = EQ.prof.bands.map((b, i) => `<g class="eq-node${EQ.sel === i ? " sel" : ""}" data-node="${i}" tabindex="0" role="slider" aria-valuemin="${hasGain(b) ? -DB : F0}" aria-valuemax="${hasGain(b) ? DB : F1}"><circle class="hit" r="14"/><circle class="dot" r="6" fill="${COLORS[i % COLORS.length]}"/></g>`).join("");
  return `<svg id="eqCurve" class="eq-svg" viewBox="0 0 ${W} ${H}" role="group" aria-label="Крива еквалайзера 20 Гц – 11 кГц, ±12 дБ. Вузли: тягніть, колесо — Q, стрілки — крок.">${grid}<path id="eqRef" class="eq-ref"/><path id="eqLine" class="eq-line"/>${nodes}</svg>`;
}

export function eqTable() {
  const row = (b, i) => `<tr data-row="${i}" class="${EQ.sel === i ? "sel" : ""}"><td><i class="dot" style="background:${COLORS[i % COLORS.length]}"></i></td><td>${esc(EQ_NAMES[b.type])}</td>
    <td><input type="number" data-eq="freq" data-i="${i}" aria-label="${esc(label(b, i, "частота"))}" min="20" max="20000" step="1" value="${b.freq_hz}"></td>
    <td>${hasGain(b) ? `<input type="number" data-eq="gain" data-i="${i}" aria-label="${esc(label(b, i, "підсилення"))}" min="-12" max="12" step="0.5" value="${b.gain_db}">` : "—"}</td>
    <td>${hasQ(b) ? `<input type="number" data-eq="q" data-i="${i}" aria-label="${esc(label(b, i, "Q"))}" min="0.1" max="${MAXQ}" step="0.05" value="${b.q}">` : "—"}</td></tr>`;
  return `<table class="eq-tbl"><thead><tr><th></th><th>смуга</th><th>Гц</th><th>дБ</th><th>Q</th></tr></thead><tbody>${EQ.prof.bands.map(row).join("")}</tbody></table>`;
}

/** Перемалювати криву, вузли й числа таблиці без перебудови розмітки (під час перетягування). */
export function eqDraw() {
  const P = EQ.prof, svg = $("#eqCurve");
  if (!svg || !P) return;
  const amt = P.amount ?? 1;
  $("#eqLine").setAttribute("d", curve(P, amt));
  $("#eqRef").setAttribute("d", amt !== 1 ? curve(P, 1) : "");
  svg.classList.toggle("off", !(P.enabled && amt > 0 && !EQ.bypass));
  P.bands.forEach((b, i) => {
    const g = svg.querySelector(`[data-node="${i}"]`);
    if (!g) return;
    g.setAttribute("transform", `translate(${px(b.freq_hz).toFixed(1)},${py(hasGain(b) ? clamp(b.gain_db, -DB, DB) : 0).toFixed(1)})`);
    g.setAttribute("aria-label", label(b, i, hasGain(b) ? "підсилення" : "частота"));
    g.setAttribute("aria-valuenow", hasGain(b) ? b.gain_db : b.freq_hz);
    g.setAttribute("aria-valuetext", hasGain(b) ? `${b.gain_db} дБ на ${fmtHz(b.freq_hz)}` : fmtHz(b.freq_hz));
  });
  for (const el of document.querySelectorAll("#eq input[data-eq][data-i]")) {
    const b = P.bands[+el.dataset.i], v = { freq: b.freq_hz, gain: b.gain_db, q: b.q }[el.dataset.eq];
    if (document.activeElement !== el && +el.value !== v) el.value = v;
  }
}

function markSel() {
  document.querySelectorAll("#eq [data-node], #eq tr[data-row]").forEach((e) => e.classList.toggle("sel", +(e.dataset.node ?? e.dataset.row) === EQ.sel));
}

/** Pointer Events на вузлах, колесо (Q), стрілки на сфокусованому вузлі. onEdit(now) — повідомити панель, що профіль змінено. */
export function eqEditorSetup(box, onEdit) {
  let drag = null;
  const changed = () => { eqLiveUpdate(); eqDraw(); };
  const at = (ev) => { const r = $("#eqCurve").getBoundingClientRect(); return [(ev.clientX - r.left) * W / r.width, (ev.clientY - r.top) * H / r.height]; };
  box.addEventListener("pointerdown", (ev) => {
    const g = ev.target.closest(".eq-node");
    if (!g) return;
    ev.preventDefault(); g.focus(); g.setPointerCapture(ev.pointerId);
    EQ.sel = +g.dataset.node; drag = { i: EQ.sel, id: ev.pointerId }; markSel();
  });
  box.addEventListener("pointermove", (ev) => {
    if (!drag || ev.pointerId !== drag.id) return;
    const b = EQ.prof.bands[drag.i], [x, y] = at(ev);
    b.freq_hz = clamp(Math.round(fx(x)), 20, F1);
    if (hasGain(b)) b.gain_db = clamp(Math.round(dyb(y) * 10) / 10, -DB, DB);
    changed();
  });
  const end = (ev) => { if (drag && ev.pointerId === drag.id) { drag = null; onEdit(true); } };
  box.addEventListener("pointerup", end);
  box.addEventListener("pointercancel", end);
  box.addEventListener("wheel", (ev) => {
    const g = ev.target.closest(".eq-node");
    if (!g) return;
    ev.preventDefault();
    const b = EQ.prof.bands[+g.dataset.node];
    if (!hasQ(b)) return;
    b.q = clamp(Math.round(b.q * (ev.deltaY < 0 ? 1.1 : 1 / 1.1) * 100) / 100, 0.1, MAXQ);
    changed(); onEdit();
  }, { passive: false });
  box.addEventListener("keydown", (ev) => {
    const g = ev.target.closest?.(".eq-node");
    if (!g) return;
    const b = EQ.prof.bands[+g.dataset.node], k = ev.shiftKey ? 1.25 : 1.05, dg = ev.shiftKey ? 2 : 0.5;
    if (ev.code === "ArrowLeft") b.freq_hz = clamp(Math.round(b.freq_hz / k), 20, F1);
    else if (ev.code === "ArrowRight") b.freq_hz = clamp(Math.round(b.freq_hz * k), 20, F1);
    else if (ev.code === "ArrowUp" && hasGain(b)) b.gain_db = clamp(Math.round((b.gain_db + dg) * 10) / 10, -DB, DB);
    else if (ev.code === "ArrowDown" && hasGain(b)) b.gain_db = clamp(Math.round((b.gain_db - dg) * 10) / 10, -DB, DB);
    else return;
    ev.preventDefault(); changed(); onEdit();
  });
  box.addEventListener("click", (ev) => {
    const r = ev.target.closest("tr[data-row]");
    if (r) { EQ.sel = +r.dataset.row; markSel(); }
  });
}
