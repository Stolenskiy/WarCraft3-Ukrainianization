/* Еквалайзер: панель у лівій колонці, профілі, збереження через API. */
import { getJSON, post } from "./api.js";
import { AC } from "./audio.js";
import { renderCard } from "./card.js";
import { renderCues, select, step } from "./cues.js";
import { EQ, eqApply, eqClone, eqDirty, eqLiveUpdate, eqOwn, eqPlain, eqRewire, eqToggleAB } from "./eq-live.js";
import { S } from "./state.js";
import { toast } from "./toast.js";
import { $, esc } from "./util.js";

const EQ_TYPES = { highpass: "Зріз низів (гул)", lowshelf: "Низи (полиця)", peaking: "Смуга", highshelf: "Верхи (полиця)", lowpass: "Зріз верхів (шипіння)" };

const eqLog = (v) => Math.round(Math.log(v / 20) / Math.log(1000) * 1000);      // 20 Гц…20 кГц → 0…1000

const eqFromLog = (x) => Math.round(20 * Math.pow(1000, x / 1000));

function eqCurve() {
  const c = $("#eqCurve");
  if (!c || !EQ.prof) return;
  const W = c.width, H = c.height, g = c.getContext("2d");
  g.clearRect(0, 0, W, H);
  g.strokeStyle = "#2a303b"; g.lineWidth = 1;
  for (const db of [-12, -6, 0, 6, 12]) { const y = H / 2 - db / 12 * (H / 2 - 3); g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
  const N = 120, fr = new Float32Array(N), mag = new Float32Array(N), ph = new Float32Array(N), tot = new Float32Array(N).fill(1);
  for (let i = 0; i < N; i++) fr[i] = 20 * Math.pow(1000, i / (N - 1));
  for (const b of EQ.prof.bands) {
    const n = AC.createBiquadFilter(); eqApply(n, b); n.getFrequencyResponse(fr, mag, ph);
    for (let i = 0; i < N; i++) tot[i] *= mag[i];
  }
  const k = Math.pow(10, EQ.prof.gain_db / 20);
  g.strokeStyle = EQ.prof.enabled && !EQ.bypass ? "#f0a441" : "#5d6573"; g.lineWidth = 2; g.beginPath();
  for (let i = 0; i < N; i++) {
    const db = Math.max(-14, Math.min(14, 20 * Math.log10(Math.max(1e-4, tot[i] * k))));
    const x = i / (N - 1) * W, y = H / 2 - db / 12 * (H / 2 - 3);
    i ? g.lineTo(x, y) : g.moveTo(x, y);
  }
  g.stroke();
}

export function eqRender() {                               // зберігає фокус: інакше клавіші підуть у глобальні
  const f = document.activeElement, box0 = $("#eq");
  const key = f && box0.contains(f) ? (f.id ? `#${f.id}` : f.dataset.eq ? `[data-eq="${f.dataset.eq}"]${f.dataset.i != null ? `[data-i="${f.dataset.i}"]` : ":not([data-i])"}` : null) : null;
  eqRenderInner();
  if (key) box0.querySelector(key)?.focus();
}

function eqRenderInner() {
  const box = $("#eq");
  if (!EQ.data || !EQ.prof) { box.innerHTML = ""; return; }
  const P = EQ.data.profiles, own = !!eqOwn(), dirty = eqDirty();
  const opt = (p) => `<option value="${esc(p.id)}" ${p.id === EQ.id ? "selected" : ""}>${esc(p.name)}</option>`;
  box.innerHTML = `
    <select id="eqSel" aria-label="Профіль">
      <optgroup label="Пресети">${P.filter((p) => p.builtin).map(opt).join("")}</optgroup>
      ${P.some((p) => !p.builtin) ? `<optgroup label="Мої профілі">${P.filter((p) => !p.builtin).map(opt).join("")}</optgroup>` : ""}
    </select>
    <canvas id="eqCurve" width="248" height="72"></canvas>
    <div class="eq-row">
      <label class="switch"><input type="checkbox" id="eqOn" ${EQ.prof.enabled ? "checked" : ""}><span></span>Увімкнено</label>
      <button class="ghost ${EQ.bypass ? "on" : ""}" id="eqBypass" aria-pressed="${EQ.bypass}" title="Порівняти: прослуховування без EQ (A/B)">${EQ.bypass ? "Слухаю без EQ" : "Слухаю з EQ"}</button>
    </div>
    <label class="eq-sl">Гучність <output>${EQ.prof.gain_db} дБ</output>
      <input type="range" data-eq="gain" aria-label="Загальна гучність профілю" min="-12" max="12" step="0.5" value="${EQ.prof.gain_db}"></label>
    ${EQ.prof.bands.map((b, i) => `<div class="eq-band"><b>${esc(EQ_TYPES[b.type])}</b>
      <label class="eq-sl">Частота <output>${b.freq_hz} Гц</output>
        <input type="range" data-eq="freq" data-i="${i}" aria-label="${esc(EQ_TYPES[b.type])}: частота" min="0" max="1000" value="${eqLog(b.freq_hz)}"></label>
      ${b.type === "highpass" || b.type === "lowpass" ? "" : `<label class="eq-sl">Підсилення <output>${b.gain_db} дБ</output>
        <input type="range" data-eq="gain" data-i="${i}" aria-label="${esc(EQ_TYPES[b.type])}: підсилення" min="-12" max="12" step="0.5" value="${b.gain_db}"></label>`}
      ${b.type === "lowshelf" || b.type === "highshelf" ? "" : `<label class="eq-sl">Q <output>${b.q}</output>
        <input type="range" data-eq="q" data-i="${i}" aria-label="${esc(EQ_TYPES[b.type])}: Q" min="0.1" max="10" step="0.05" value="${b.q}"></label>`}</div>`).join("")}
    <div class="eq-row">
      ${EQ.naming ? `<input type="text" id="eqName" maxlength="60" placeholder="Назва профілю" value="${esc(own ? "" : EQ.prof.name + " (копія)")}">
        <button class="ghost" id="eqSaveNew">Зберегти</button>` : `<button class="ghost" id="eqNew">Зберегти як новий профіль</button>`}
      ${own && dirty ? `<button class="ghost" id="eqUpdate">Оновити профіль</button>` : ""}
      ${own ? `<button class="ghost danger" id="eqDel">Видалити</button>` : ""}
    </div>
    <button class="ghost wide" id="eqReexport" title="Перезаписати файли для гри з поточним EQ">Застосувати до обраних дублів</button>
    <p class="eq-hint">${EQ.data.selected === EQ.id ? "" : "Профіль для гри — «" + esc((P.find((p) => p.id === EQ.data.selected) || {}).name) + "». "}${P.find((p) => p.id === EQ.id).builtin ? "Пресет лише для читання: правки зберігайте як новий профіль. " : ""}Зміни чути одразу; у файли для гри потрапляють після застосування.</p>`;
  eqCurve();
}

let eqLoadSeq = 0;

export async function eqLoad() {
  const my = ++eqLoadSeq;
  EQ.prof = null;   // поки профіль не прийшов, play() чекає S.eqReady, а не грає з профілем попереднього юніта
  try { EQ.data = await getJSON(`/api/eq?cid=${encodeURIComponent(S.cat)}&gid=${encodeURIComponent(S.unit)}`); } catch (e) { EQ.data = null; eqRender(); toast(`Еквалайзер не завантажився: ${e.message || e}`, true); return; }
  if (my !== eqLoadSeq) return;
  EQ.id = EQ.data.selected; EQ.naming = false; EQ.bypass = false;
  EQ.prof = eqClone(eqPlain(EQ.data.profiles.find((p) => p.id === EQ.id)));
  eqRender(); eqRewire();
}

async function eqCommit(path, body, msg) {  // відповідь — новий стан /api/eq
  try {
    EQ.data = await post(path, { cid: S.cat, gid: S.unit, ...body });
    EQ.id = EQ.data.saved_id || EQ.data.selected; EQ.naming = false;
    EQ.prof = eqClone(eqPlain(EQ.data.profiles.find((p) => p.id === EQ.id)));
    eqRender(); eqRewire(); if (msg) toast(msg);
    return true;
  } catch (e) { toast(String(e.message || e), true); return false; }
}

export function eqSetup() {
  const box = $("#eq");
  box.addEventListener("input", (ev) => {
    const el = ev.target, k = el.dataset.eq;
    if (!k || !EQ.prof) return;
    const v = +el.value, b = el.dataset.i != null ? EQ.prof.bands[+el.dataset.i] : null;
    if (!b) EQ.prof.gain_db = v;
    else if (k === "freq") b.freq_hz = eqFromLog(v);
    else if (k === "gain") b.gain_db = v;
    else b.q = v;
    const out = el.parentElement.querySelector("output");
    if (out) out.textContent = !b ? `${v} дБ` : k === "freq" ? `${b.freq_hz} Гц` : k === "gain" ? `${v} дБ` : v;
    eqLiveUpdate(); eqCurve();
  });
  box.addEventListener("change", (ev) => {
    if (ev.target.id === "eqSel") {
      const prev = EQ.id;
      eqCommit("/api/eq/assign", { profile_id: ev.target.value }).then((ok) => { if (!ok) { ev.target.value = prev; } });
    } else if (ev.target.id === "eqOn") {
      EQ.prof.enabled = ev.target.checked; eqRender(); eqRewire();
    } else if (ev.target.dataset.eq) eqRender();   // оновити кнопки (напр. «Оновити профіль»)
  });
  box.addEventListener("click", (ev) => {
    const id = ev.target.id;
    if (id === "eqBypass") eqToggleAB();
    else if (id === "eqNew") { EQ.naming = true; eqRender(); $("#eqName").focus(); }
    else if (id === "eqSaveNew") {
      const name = $("#eqName").value.trim();
      if (!name) return toast("Вкажіть назву профілю", true);
      eqCommit("/api/eq/profile", { profile: { ...EQ.prof, name } }, `Профіль «${name}» збережено`);
    } else if (id === "eqUpdate") eqCommit("/api/eq/profile", { id: EQ.id, profile: EQ.prof }, "Профіль оновлено");
    else if (id === "eqDel") { if (confirm(`Видалити профіль «${EQ.prof.name}»?`)) eqCommit("/api/eq/delete", { id: EQ.id }, "Профіль видалено"); }
    else if (id === "eqReexport") eqReexport();
  });
  // Усередині #eq глобальні клавіші не діють, крім L, B, A і Пробілу на повзунках (стрілки/Home/End/PageUp/PageDown лишаються повзунку)
  box.addEventListener("keydown", (ev) => {
    if (!(ev.target.matches("input[type=range]") && ["KeyL", "KeyB", "KeyA", "Space"].includes(ev.code))) ev.stopPropagation();
    if (ev.key === "Enter" && ev.target.id === "eqName") $("#eqSaveNew").click();
  });
}

async function eqReexport() {
  if (eqDirty() || !EQ.data.profiles.find((p) => p.id === EQ.id)) return toast("Спершу збережіть профіль", true);
  if (EQ.data.selected !== EQ.id && !(await eqCommit("/api/eq/assign", { profile_id: EQ.id }))) return;
  try {
    const r = await post("/api/eq/reexport", { cid: S.cat, gid: S.unit });
    const byId = Object.fromEntries(r.lines.map((l) => [l.id, l]));
    S.phrases = S.phrases.map((p) => byId[p.id] || p);
    renderCues(); renderCard();
    toast(r.done.length ? `EQ застосовано до ${r.done.length} дубл. ${r.failed.length ? `(помилок: ${r.failed.length})` : ""}` : "Немає обраних дублів", !r.done.length);
  } catch (e) { toast(String(e.message || e), true); }
}
