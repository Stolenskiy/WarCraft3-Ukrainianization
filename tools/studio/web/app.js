"use strict";
/* Студія озвучки — фронтенд (vanilla JS, без залежностей). */

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fmt = (s) => `${(+s).toFixed(2)} с`;
const MAX_REC = 30;

const S = { catalogs: [], lang: "ru", cat: null, unit: null, phrases: [], idx: 0, filter: "all", undo: null, busy: false };
const ids = (p = cur()) => ({ cid: S.cat, gid: S.unit, lid: p.id });

// ------------------------------------------------------------------ API
async function getJSON(url) {
  const r = await fetch(url);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}
async function post(path, body, isAudio = false) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "X-Studio": "1", "Content-Type": isAudio ? "audio/wav" : "application/json" },
    body: isAudio ? body : JSON.stringify(body),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}
const cur = () => S.phrases[S.idx];
const isDone = (p) => !!(p.approved || p.original);   // дубль обрано або залишено оригінал
const aurl = (kind, name) => `/audio/${kind}/${S.cat}/${S.unit}/${encodeURIComponent(name)}`;
// мова оригіналу (налаштування в шапці): "ru" | "en"; якщо англійського файлу немає — рос.
// без російського мовного пакета (make refs) звучить лише англійський
const refLang = (p) => ((S.lang === "en" && p.has_en) || !p.has_ru ? "en" : "ru");
const urlRef = (p) => aurl(refLang(p) === "en" ? "ref-en" : "ref", p.id);
const urlTake = (f) => aurl("take", f);

// ------------------------------------------------------------------ аудіо: декодування, хвилі, програвання
const AC = new (window.AudioContext || window.webkitAudioContext)();
// Контекст «будимо» синхронно в будь-якому жесті: після await (діалог дозволу мікрофона)
// браузер уже не вважає це дією користувача, і resume() зависає.
for (const ev of ["pointerdown", "keydown"]) document.addEventListener(ev, () => { if (AC.state !== "running") AC.resume(); }, true);
// Декодуємо в OfflineAudioContext — працює навіть коли AC ще «спить» або немає виходу звуку.
const DEC = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, 1, 44100);
const bufCache = new Map();
function loadBuf(url) {
  if (!bufCache.has(url)) {
    bufCache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error("audio " + r.status); return r.arrayBuffer(); })
      .then((b) => DEC.decodeAudioData(b)).catch((e) => { bufCache.delete(url); throw e; }));
  }
  return bufCache.get(url);
}

/** Межі голосу (без тиші на краях), як у копії для гри: поріг −45 dB. */
function voiceSpan(buf) {
  // Як ffmpeg silenceremove (detection=rms, window 20 мс, поріг −45 дБ): RMS у ковзному вікні,
  // тож поодиноке клацання в тиші не вважається голосом. Запас 0.08 с / 0.12 с — як у AUTO_TRIM.
  const d = buf.getChannelData(0), sr = buf.sampleRate, thr2 = Math.pow(10, -45 / 10);
  const win = Math.max(1, Math.round(sr * 0.02)), hop = Math.max(1, Math.round(sr * 0.005));
  const loud = (i) => { let s = 0; const e = Math.min(i + win, d.length); for (let k = i; k < e; k++) s += d[k] * d[k]; return s / Math.max(1, e - i) > thr2; };
  let a = 0, b = d.length - win;
  while (a < d.length && !loud(a)) a += hop;
  while (b > a && !loud(Math.max(0, b))) b -= hop;
  if (a >= b) return [0, buf.duration];
  return [Math.max(0, a / sr - 0.08), Math.min(buf.duration, (b + win) / sr + 0.12)];
}

const waves = new Map(); // id -> {canvas, buf, opts}
function drawWave(id, progress = -1) {
  const w = waves.get(id);
  if (!w || !w.canvas.isConnected) return;
  const { canvas, buf, opts } = w;
  const dpr = window.devicePixelRatio || 1, W = canvas.clientWidth, H = canvas.clientHeight;
  if (!W) return;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const g = canvas.getContext("2d");
  g.scale(dpr, dpr);
  const scale = Math.max(opts.scale || buf.duration, buf.duration);
  const used = W * (buf.duration / scale);
  const bar = 2, gap = 1, n = Math.max(1, Math.floor(used / (bar + gap)));
  const d = buf.getChannelData(0), per = Math.max(1, Math.floor(d.length / n));
  const mid = H / 2;
  for (let i = 0; i < n; i++) {
    let m = 0;
    for (let k = i * per; k < (i + 1) * per && k < d.length; k += 4) m = Math.max(m, Math.abs(d[k]));
    const h = Math.max(1.5, Math.min(1, m * 1.6) * (H - 4));
    const x = i * (bar + gap);
    g.fillStyle = progress >= 0 && x / used <= progress ? opts.played : opts.color;
    g.fillRect(x, mid - h / 2, bar, h);
  }
  if (opts.marker != null) { // довжина оригіналу — пунктир
    const x = Math.min(W - 1, W * (opts.marker / scale));
    g.strokeStyle = "rgba(240,164,65,.9)"; g.setLineDash([3, 3]); g.lineWidth = 1;
    g.beginPath(); g.moveTo(x + 0.5, 0); g.lineTo(x + 0.5, H); g.stroke();
    g.setLineDash([]); g.fillStyle = "rgba(240,164,65,.9)"; g.font = "10px -apple-system, sans-serif";
    g.fillText("оригінал", Math.min(x + 4, W - 46), 10);
  }
}

// ------------------------------------------------------------------ еквалайзер персонажа
// Профіль {name, enabled, gain_db, bands:[{type,freq_hz,gain_db,q}]} (дані й ffmpeg — eq.py).
// Прослуховування дублів іде через BiquadFilterNode з тими самими параметрами; файл для гри
// змінюється лише кнопкою «Застосувати до обраних дублів».
const EQ = { data: null, id: null, prof: null, bypass: false, live: null, naming: false };
const EQ_TYPES = { highpass: "Зріз низів (гул)", lowshelf: "Низи (полиця)", peaking: "Смуга", highshelf: "Верхи (полиця)", lowpass: "Зріз верхів (шипіння)" };
const eqClone = (o) => JSON.parse(JSON.stringify(o));
const eqLog = (v) => Math.round(Math.log(v / 20) / Math.log(1000) * 1000);      // 20 Гц…20 кГц → 0…1000
const eqFromLog = (x) => Math.round(20 * Math.pow(1000, x / 1000));
const eqOwn = () => EQ.data && EQ.data.profiles.find((p) => p.id === EQ.id && !p.builtin);
const eqDirty = () => { const b = EQ.data && EQ.data.profiles.find((p) => p.id === EQ.id); return !!b && JSON.stringify(eqPlain(b)) !== JSON.stringify(eqPlain(EQ.prof)); };
const eqPlain = (p) => ({ name: p.name, enabled: p.enabled, gain_db: p.gain_db, bands: p.bands });

function eqNodeSpec(b) {  // Web Audio: Q фільтрів HP/LP — у дБ
  return { type: b.type, frequency: b.freq_hz, gain: b.gain_db, Q: b.type === "highpass" || b.type === "lowpass" ? 20 * Math.log10(b.q) : b.q };
}
function eqApply(node, b) {
  const s = eqNodeSpec(b);
  node.type = s.type; node.frequency.value = s.frequency; node.gain.value = s.gain; node.Q.value = s.Q;
}
// Граф дубля завжди: src → dry → вихід, та src → [EQ-ланцюг] → wet → вихід. A/B і зміна профілю лише
// перемикають гучність dry/wet (setTargetAtTime), тож працюють і на дублі, що вже звучить (eqRewire).
const eqActive = () => !!EQ.prof && EQ.prof.enabled && !EQ.bypass;
const EQ_RAMP = 0.015;   // стала часу перемикання, с
function eqConnect(src, id, buf, url) {
  EQ.live = null;
  if (!EQ.prof || !String(id).startsWith("take:")) { src.connect(AC.destination); return; }
  const dry = AC.createGain(), wet = AC.createGain();
  dry.gain.value = wet.gain.value = 0;
  src.connect(dry); dry.connect(AC.destination); wet.connect(AC.destination);
  EQ.live = { src, dry, wet, nodes: [], vol: null, head: null, n: undefined, buf, url };
  eqRewire();
}
function eqRewire() {  // стан EQ (увімкнено / A-B / профіль) → живий граф і чип
  const l = EQ.live;
  if (!l || !EQ.prof) return eqChip();
  const on = eqActive(), P = EQ.prof;
  if (on ? l.n !== P.bands.length : l.n === undefined) {   // змінилась кількість смуг або перша збірка
    if (l.head) { try { l.src.disconnect(l.head); } catch {} }
    [...l.nodes, l.vol].forEach((n) => { try { n && n.disconnect(); } catch {} });
    if (on) {
      l.nodes = P.bands.map((b) => { const n = AC.createBiquadFilter(); eqApply(n, b); return n; });
      l.vol = AC.createGain();
      const chain = [l.src, ...l.nodes, l.vol, l.wet];
      chain.reduce((x, n) => (x.connect(n), n));
      l.head = chain[1]; l.n = P.bands.length;
    } else { l.nodes = []; l.vol = null; l.src.connect(l.wet); l.head = l.wet; l.n = -1; }
  }
  if (on) eqLiveUpdate();
  const t = AC.currentTime;
  l.wet.gain.setTargetAtTime(on ? 1 : 0, t, EQ_RAMP);
  l.dry.gain.setTargetAtTime(on ? 0 : eqMatched(l), t, EQ_RAMP);   // B (без EQ) вирівняно за гучністю з A
  if (!on && l.buf && !eqMatchVal.has(eqMatchKey(l.url))) eqMatch(l.buf, l.url).then(() => { if (EQ.live === l) eqRewire(); });
  eqChip();
}
function eqLiveUpdate() {  // слайдери під час прослуховування
  const l = EQ.live;
  if (!l || !l.vol || l.nodes.length !== EQ.prof.bands.length) return;
  EQ.prof.bands.forEach((b, i) => eqApply(l.nodes[i], b));
  l.vol.gain.value = Math.pow(10, EQ.prof.gain_db / 20);
}
// Вирівнювання A/B за гучністю: RMS(дубль через EQ) / RMS(дубль), раз на (дубль, профіль) через OfflineAudioContext
const eqMatchVal = new Map(), eqMatchJobs = new Map();
const eqMatchKey = (url) => url + "|" + JSON.stringify(eqPlain(EQ.prof));
const eqMatched = (l) => (l.url && eqMatchVal.get(eqMatchKey(l.url))) || 1;
function eqMatch(buf, url) {
  const key = eqMatchKey(url);
  if (!eqMatchJobs.has(key)) {
    const P = eqClone(EQ.prof);
    eqMatchJobs.set(key, (async () => {
      let g = 1;
      try {
        const oc = new OfflineAudioContext(buf.numberOfChannels, buf.length, buf.sampleRate);
        const s = oc.createBufferSource(); s.buffer = buf;
        const nodes = P.bands.map((b) => { const n = oc.createBiquadFilter(); eqApply(n, b); return n; });
        const vol = oc.createGain(); vol.gain.value = Math.pow(10, P.gain_db / 20);
        [s, ...nodes, vol, oc.destination].reduce((x, n) => (x.connect(n), n));
        s.start();
        const out = await oc.startRendering();
        const rms = (b) => { let sum = 0, n = 0; for (let c = 0; c < b.numberOfChannels; c++) for (const v of b.getChannelData(c)) { sum += v * v; n++; } return Math.sqrt(sum / (n || 1)); };
        const d = rms(buf), w = rms(out);
        if (d > 1e-6 && w > 1e-6) g = Math.min(4, Math.max(0.25, w / d));
      } catch (e) { console.warn("eq match", e); }
      eqMatchVal.set(key, g);
    })());
  }
  return eqMatchJobs.get(key);
}
function eqToggleAB() { EQ.bypass = !EQ.bypass; eqRender(); eqRewire(); }
function eqChip() {  // чип «EQ · профіль» на дублі, що звучить: золотий — з EQ, сірий — без (B); клік / A — перемкнути
  document.querySelectorAll("[data-eq-chip]").forEach((c) => c.remove());
  if (!playing || !EQ.live || !EQ.prof) return;
  const head = document.querySelector(`[data-play="${CSS.escape(playing.id)}"]`)?.closest(".take")?.querySelector(".wave-box");  // накладка: розмітку не зсуває
  if (!head) return;
  const on = eqActive();
  head.insertAdjacentHTML("beforeend", `<button class="eq-chip ${on ? "on" : ""}" data-eq-chip aria-pressed="${on}"
    title="${on ? "Звучить з EQ" : "Звучить без EQ (B)"} — клік або A: порівняти">EQ · ${esc(EQ.prof.name)}</button>`);
}
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
function eqRender() {                               // зберігає фокус: інакше клавіші підуть у глобальні
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
async function eqLoad() {
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
function eqSetup() {
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
eqSetup();

let playToken = null, playing = null; // playing: {id, src, t0, dur}
async function play(items) {
  stopPlay();
  const token = {};
  playToken = token;
  if (AC.state !== "running") AC.resume();
  for (const it of items) {
    let buf;
    try { buf = await loadBuf(it.url); } catch { toast("Не вдалося відкрити аудіо", true); return; }
    if (it.nocache) bufCache.delete(it.url);           // «Як у грі»: той самий url не тримаємо, налаштування могли змінитись
    if (playToken !== token) return;
    if (String(it.id).startsWith("take:")) {         // EQ має встигнути завантажитись (інакше дубль зазвучить без нього)
      await S.eqReady;
      if (EQ.prof && EQ.prof.enabled) await eqMatch(buf, it.url);
      if (playToken !== token) return;
    }
    await new Promise((res) => {
      const src = AC.createBufferSource();
      src.buffer = buf; eqConnect(src, it.id, buf, it.url); src.onended = res;
      const off = it.start || 0, len = (it.end ?? buf.duration) - off; // ручне обрізання дубля
      playing = { id: it.id, src, t0: AC.currentTime, dur: len, off, full: buf.duration };
      src.start(0, off, len);
      markPlaying();
    });
    if (playToken !== token) return;
    if (playing) drawWave(playing.id);
    playing = null; markPlaying();
    await sleep(220);
  }
}
function stopPlay() {
  playToken = null;
  if (playing) { try { playing.src.onended = null; playing.src.stop(); } catch {} drawWave(playing.id); playing = null; }
  markPlaying();
}
function markPlaying() {
  if (!playing) EQ.live = null;
  document.querySelectorAll("[data-play]").forEach((b) => {
    const on = playing && b.dataset.play === playing.id;
    b.classList.toggle("playing", !!on); b.textContent = on ? "■" : "▶";
  });
  eqChip();
}
(function anim() {
  if (playing) drawWave(playing.id, ((playing.off || 0) + AC.currentTime - playing.t0) / (playing.full || playing.dur));
  requestAnimationFrame(anim);
})();

// ------------------------------------------------------------------ запис (мікрофон тримаємо відкритим → старт миттєвий)
// Джерело звуку обирає користувач (#micSel, localStorage "studio.mic"); "" = системний за замовчуванням.
const Rec = { node: null, analyser: null, stream: null, src: null, label: "", worklet: false, meter: false,
  on: false, chunks: [], pre: [], t0: 0, sr: 48000, devices: [] };
let micId = ""; try { micId = localStorage.getItem("studio.mic") || ""; } catch {}
const MIC_OPTS = { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 };

async function refreshMics() {
  try { Rec.devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audioinput" && d.deviceId !== "default"); }
  catch { Rec.devices = []; }
  renderMicSel();
}
function renderMicSel() {
  const sel = $("#micSel");
  if (!sel) return;
  const opts = [`<option value="">Системний (за замовчуванням)</option>`].concat(Rec.devices.map((d, i) =>
    `<option value="${esc(d.deviceId)}">${esc(d.label || `Мікрофон ${i + 1}`)}</option>`));
  sel.innerHTML = opts.join("");
  sel.value = Rec.devices.some((d) => d.deviceId === micId) ? micId : "";
  sel.disabled = Rec.on;
}
function closeMic() {
  Rec.stream?.getTracks().forEach((t) => t.stop());
  try { Rec.src?.disconnect(); Rec.node?.disconnect(); } catch {}
  Rec.stream = Rec.src = Rec.node = Rec.analyser = null; Rec.pre = []; Rec.label = "";
}
async function switchMic(id) {
  if (Rec.on) return;
  micId = id; try { localStorage.setItem("studio.mic", id); } catch {}
  closeMic();
  try { await ensureMic(); toast(`Запис із: ${Rec.label || "системного мікрофона"}`); }
  catch (e) { toast(`Не вдалося відкрити цей мікрофон: ${e.message || e.name}`, true); }
  setRecUI(false);
}
navigator.mediaDevices?.addEventListener?.("devicechange", refreshMics);

async function ensureMic() {
  if (Rec.node) return;
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: micId ? { ...MIC_OPTS, deviceId: { exact: micId } } : MIC_OPTS });
  } catch (e) {
    if (!micId || e.name !== "OverconstrainedError" && e.name !== "NotFoundError") throw e;
    micId = "";                                    // обраний пристрій від'єднано → системний
    stream = await navigator.mediaDevices.getUserMedia({ audio: MIC_OPTS });
  }
  if (AC.state !== "running") AC.resume();
  if (!Rec.worklet) {
    const code = `class Cap extends AudioWorkletProcessor{constructor(){super();this.b=new Float32Array(2048);this.i=0}
    process(inp){const c=inp[0]&&inp[0][0];if(c){for(let k=0;k<c.length;k++){this.b[this.i++]=c[k];
    if(this.i===this.b.length){this.port.postMessage(this.b.slice(0));this.i=0}}}return true}}registerProcessor('cap',Cap)`;
    await AC.audioWorklet.addModule(URL.createObjectURL(new Blob([code], { type: "application/javascript" })));
    Rec.worklet = true;
  }
  const src = AC.createMediaStreamSource(stream);
  Rec.stream = stream; Rec.src = src; Rec.label = stream.getAudioTracks()[0]?.label || "";
  Rec.sr = AC.sampleRate;
  Rec.node = new AudioWorkletNode(AC, "cap");
  const mute = AC.createGain(); mute.gain.value = 0;
  src.connect(Rec.node); Rec.node.connect(mute); mute.connect(AC.destination);
  Rec.analyser = AC.createAnalyser(); Rec.analyser.fftSize = 1024; src.connect(Rec.analyser);
  refreshMics();                                   // після дозволу браузер віддає назви пристроїв
  const preN = Math.ceil((0.25 * Rec.sr) / 2048); // 0.25 с «передзапису», щоб не з'їсти перший склад
  Rec.node.port.onmessage = (e) => {
    if (Rec.on) { Rec.chunks.push(e.data); clipCheck(e.data); }
    else { Rec.pre.push(e.data); if (Rec.pre.length > preN) Rec.pre.shift(); }
  };
  if (!Rec.meter) { Rec.meter = true; meterLoop(); }
}
function meterLoop() {
  const data = new Float32Array(1024);
  const tick = () => {
    if (!Rec.analyser) { requestAnimationFrame(tick); return; }
    Rec.analyser.getFloatTimeDomainData(data);
    let pk = 0; for (const v of data) pk = Math.max(pk, Math.abs(v));
    const db = 20 * Math.log10(pk || 1e-6), lit = Math.round(Math.max(0, Math.min(1, (db + 60) / 60)) * 20);
    const bars = document.querySelectorAll("#meter i");
    bars.forEach((b, i) => { b.className = i < lit ? (i >= 18 ? "l3" : i >= 14 ? "l2" : "l1") : ""; });
    if (Rec.on) {
      const t = AC.currentTime - Rec.t0, el = $("#timer");
      if (el) el.firstChild.nodeValue = t.toFixed(1) + " с";
      if (t >= MAX_REC) stopRec();
    }
    requestAnimationFrame(tick);
  };
  tick();
}
async function toggleRec() { if (Rec.on) await stopRec(); else await startRec(); }
async function startRec() {
  if (S.busy || !cur()) return;
  stopPlay();
  try { await ensureMic(); }
  catch (e) {
    const why = e && e.name === "NotAllowedError" ? "доступ заборонено" : e && e.name === "NotFoundError" ? "мікрофон не знайдено" : (e && e.message) || e;
    toast(`Мікрофон не ввімкнувся (${why}). Дозвольте його в браузері (значок у рядку адреси) і в Системних параметрах → Конфіденційність і безпека → Мікрофон → ваш браузер.`, true, 12000);
    return;
  }
  if (AC.state !== "running") { toast("Аудіо ще не активоване браузером — натисніть запис ще раз", true); return; }
  Rec.chunks = Rec.pre.slice(); Rec.on = true; Rec.t0 = AC.currentTime;
  setRecUI(true);
}
async function stopRec() {
  if (!Rec.on) return;
  Rec.on = false;
  setRecUI(false);
  const total = Rec.chunks.reduce((n, c) => n + c.length, 0);
  const drop = Math.floor(Rec.sr * 0.06); // відрізати клацання клавіші в кінці
  const pcm = new Float32Array(Math.max(0, total - drop));
  let o = 0;
  for (const c of Rec.chunks) { if (o >= pcm.length) break; pcm.set(c.subarray(0, Math.min(c.length, pcm.length - o)), o); o += c.length; }
  Rec.chunks = [];
  if (pcm.length < Rec.sr * 0.3) { toast("Закороткий запис — спробуйте ще раз", true); return; }
  const p = cur();
  S.busy = true;
  $("#recTitle").textContent = "Зберігаю…";
  try {
    const where = ids(p);
    const res = await post(`/api/take?${new URLSearchParams(where)}`, encodeWav(pcm, Rec.sr), true);
    const newest = res.takes.filter((t) => !t.deleted).slice(-1)[0];
    putPhrase(where, res, newest && newest.file);
    if (newest && newest.clipped) toast(CLIP_ADVICE, true, 14000);
    if ($("#optAutoplay").checked && newest && cur()?.id === res.id && S.unit === where.gid) play([takeItem(res, newest.file)]);
  } catch (e) { toast("Не збережено: " + e.message, true); renderCard(); }
  finally { S.busy = false; }
}
function setRecUI(on) {
  $("#recBtn")?.classList.toggle("on", on);
  const t = $("#recTitle"), sub = $("#recSub"), tm = $("#timer");
  if (t) { t.textContent = on ? "Іде запис — говоріть" : "Готові записати дубль"; t.classList.toggle("live", on); }
  if (sub) sub.innerHTML = on ? "<kbd>Пробіл</kbd> — зупинити" : Rec.node ? "Мікрофон увімкнено — індикатор показує рівень. <kbd>Пробіл</kbd> — почати" : "<kbd>Пробіл</kbd> або кнопка — браузер попросить доступ до мікрофона";
  const sel = $("#micSel"); if (sel) sel.disabled = on;
  if (tm) { tm.classList.toggle("live", on); if (!on) tm.firstChild.nodeValue = "0.0 с"; }
  document.body.classList.toggle("recording", on);
}
function encodeWav(f32, sr) {
  const n = f32.length, buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
  const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); w(8, "WAVE"); w(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  w(36, "data"); v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) { const s = Math.max(-1, Math.min(1, f32[i])); v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true); }
  return new Blob([buf], { type: "audio/wav" });
}

// ------------------------------------------------------------------ каталоги (раси) і групи (юніти)
const catOf = (cid = S.cat) => S.catalogs.find((c) => c.id === cid);
const groupOf = (gid = S.unit, cid = S.cat) => catOf(cid)?.groups.find((g) => g.id === gid);
async function loadCatalogs() {
  S.catalogs = await getJSON("/api/catalogs");
  const c = catOf();
  if (c) {
    const done = c.groups.reduce((a, g) => a + g.done, 0), total = c.groups.reduce((a, g) => a + g.total, 0);
    $("#overallName").textContent = c.title.split(" — ")[0];
    $("#overallNum").textContent = `${done} / ${total}`;
    $("#overallBar").style.width = `${(100 * done) / Math.max(1, total)}%`;
  }
  const g = groupOf();
  if (g) {
    $("#unitTitle").textContent = g.title;
    $("#unitSub").textContent = `${catOf().title.split(" — ")[0]} · ${g.done} з ${g.total} готово`;
    $("#unitAvatar").textContent = initials(g.title);
  }
}
const initials = (t) => t.replace(/[^\p{L}\s]/gu, "").trim().slice(0, 2);

let popCat = null; // яка раса відкрита в поповері
function renderUnitGrid() {
  const c = catOf(popCat) || catOf();
  const tabs = S.catalogs.map((x) => {
    const d = x.groups.reduce((a, g) => a + g.done, 0), t = x.groups.reduce((a, g) => a + g.total, 0);
    return `<button class="${x.id === c.id ? "on" : ""}" data-cat="${esc(x.id)}">${esc(x.title.split(" — ")[0])} <small>${d}/${t}</small></button>`;
  }).join("");
  const card = (g) => `<button class="unit-card ${c.id === S.cat && g.id === S.unit ? "on" : ""} ${g.done === g.total ? "complete" : ""}" data-unit="${esc(g.id)}" data-unit-cat="${esc(c.id)}">
      <span class="avatar">${esc(initials(g.title))}</span>
      <span class="meta"><b>${esc(g.title)}</b><small>${g.done} / ${g.total} · ${esc(g.id)}</small>
      <div class="bar"><i style="width:${(100 * g.done) / Math.max(1, g.total)}%"></i></div></span></button>`;
  const sections = [...new Set(c.groups.map((g) => g.section))];
  $("#unitGrid").innerHTML = `<div class="seg cat-tabs">${tabs}</div>` + sections.map((sec) =>
    `<div class="pop-group">${esc(sec)}</div><div class="pop-grid">${c.groups.filter((g) => g.section === sec).map(card).join("")}</div>`).join("");
}
function toggleUnitPopover(show) {
  const pop = $("#unitPopover");
  show = show ?? pop.hidden;
  if (show) { popCat = S.cat; renderUnitGrid(); }
  pop.hidden = !show;
}
async function openUnit(cid, gid) {
  if (Rec.on) return;
  saveText();
  stopPlay();
  S.cat = cid; S.unit = gid;
  try { localStorage.setItem("studio.pos", JSON.stringify({ cid, gid })); } catch {}
  const data = await getJSON(`/api/group/${cid}/${gid}`);
  S.phrases = data.lines;
  const i = S.phrases.findIndex((p) => !isDone(p) && !p.no_speech);
  S.idx = i >= 0 ? i : 0;
  await loadCatalogs();
  const g = groupOf();
  $("#traits").innerHTML = g && g.traits.length
    ? g.traits.map((t) => { const [k, ...v] = t.split(": "); return `<p><b>${esc(k)}:</b> ${esc(v.join(": "))}</p>`; }).join("")
    : "<p>Аркуша персонажа у voice bible ще немає.</p>";
  renderCues(); renderCard();
  S.eqReady = eqLoad();
}

// ------------------------------------------------------------------ список реплік
function visible() {
  return S.phrases.map((p, i) => i).filter((i) => {
    const p = S.phrases[i];
    return S.filter === "all" || (S.filter === "done" ? isDone(p) : !isDone(p));
  });
}
function renderCues() {
  $("#cues").innerHTML = visible().map((i) => {
    const p = S.phrases[i], n = p.takes.filter((t) => !t.deleted).length;
    const st = p.approved ? "ok" : p.original ? "orig" : n ? "has" : p.no_speech ? "mute" : "";
    return `<li class="cue ${i === S.idx ? "on" : ""} ${p.no_speech ? "mute" : ""}" data-i="${i}">
      <span class="st ${st}"></span>
      <span><div class="ru">${esc(p.ru)}</div><div class="ua">${esc(p.ua)}</div></span>
      <span class="tag">${esc(p.kind_ua)}${p.original ? `<br><b class="orig-chip" title="У грі лишається оригінал">ориг. ${p.original.lang.toUpperCase()}</b>` : n ? `<br>${n} дубл.` : ""}${AI.cueMark(p)}</span></li>`;
  }).join("") || `<li class="empty">Тут порожньо</li>`;
  $("#cues .cue.on")?.scrollIntoView({ block: "nearest" });
}
function select(i) {
  if (Rec.on || i < 0 || i >= S.phrases.length) return;
  saveText();
  stopPlay();
  S.idx = i;
  renderCues(); renderCard();
}
function step(d) {
  const v = visible();
  if (!v.length) return;
  const pos = v.indexOf(S.idx);
  select(v[Math.max(0, Math.min(v.length - 1, (pos < 0 ? 0 : pos + d)))]);
}
function nextTodo() {
  const n = S.phrases.length;
  for (let k = 1; k <= n; k++) {
    const j = (S.idx + k) % n;
    if (!isDone(S.phrases[j]) && !S.phrases[j].no_speech) return select(j);
  }
  toast("Усі репліки цього юніта затверджено 🎉");
}

// ------------------------------------------------------------------ картка репліки
function fitInfo(voiceDur, ref) {
  if (!ref) return { cls: "", text: fmt(voiceDur) };
  const d = voiceDur - ref, r = voiceDur / ref;
  return { cls: r <= 1.1 ? "good" : r <= 1.3 ? "long" : "bad", text: `голос ${fmt(voiceDur)} · ${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(2)} с` };
}
function timeLabel(iso) {
  if (!iso) return "";
  const t = new Date(iso), today = new Date().toDateString() === t.toDateString();
  return today ? t.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" }) : t.toLocaleString("uk-UA", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}
function takeRow(p, t, isNew) {
  const id = "take:" + t.file, appr = p.approved === t.file && !t.deleted;
  const actions = t.deleted
    ? `<button class="btn" data-restore="${esc(t.file)}">↩ Відновити</button>`
    : `<button class="btn" data-ab="${esc(t.file)}" title="Спершу оригінал, потім цей дубль">Оригінал → дубль</button>
       <button class="btn quiet" data-preview="${esc(t.file)}" title="Як цей дубль прозвучить у грі: обрізання, темп, шумоговорення, EQ, гучність">▶ У грі</button>
       <button class="btn icon tempo-btn" data-tempo-toggle="${esc(t.file)}" title="Темп: прискорити голос без зміни висоти">⏩</button>
       ${appr ? "" : `<button class="btn primary" data-approve="${esc(t.file)}" title="Цей дубль піде в гру">✓ Обрати</button>`}
       <button class="btn icon" data-del="${esc(t.file)}" title="У кошик (можна відновити)">🗑</button>`;
  return `<div class="take ${appr ? "approved" : ""} ${t.deleted ? "deleted" : ""} ${isNew ? "new" : ""}">
    <button class="play" data-play="${esc(id)}" ${t.exists ? "" : "disabled"}>▶</button>
    <div><div class="take-head"><b>Дубль ${t.n || "?"}</b>
      <span class="fit" data-fit="${esc(t.file)}">${t.exists ? fmt(t.dur) : "файл відсутній"}</span>
      ${appr ? `<span class="badge-game">У ГРІ</span>` : ""}${t.source === "ai" ? `<span class="badge-ai" title="Взято з ШІ-варіантів (${esc(t.engine || "ШІ")})">ШІ</span>` : ""}<span class="trim-info" data-trim-info="${esc(t.file)}"></span>${tempoBadge(t)}
      <span class="time">${t.deleted ? "видалено " + timeLabel(t.deleted) : timeLabel(t.created)}</span></div>
      <div class="wave-box"><canvas class="wave" data-wave="${esc(id)}"></canvas></div>${t.deleted ? "" : tempoPanel(t)}</div>
    <div class="take-actions">${actions}</div></div>`;
}
function renderCard(newFile) {
  const p = cur(), main = $("#main");
  if (!p) { main.innerHTML = `<div class="empty">Немає реплік</div>`; return; }
  const active = p.takes.filter((t) => !t.deleted).reverse(), trash = p.takes.filter((t) => t.deleted).reverse();
  const apprTake = p.takes.find((t) => t.file === p.approved);
  const textState = p.ua_custom ? "ваш текст" : p.ua_hint ? "пропозиція з voice bible — можна змінити" : "введіть український текст";
  main.innerHTML = `<div class="card">
    <div class="eyebrow"><span class="chip type">${esc(p.kind_ua)}</span>
      <span>Репліка ${S.idx + 1} з ${S.phrases.length}</span><span class="dot-sep">${esc(p.id)}</span>
      ${p.no_speech ? `<span class="chip warn">без слів — крик / звук</span>` : ""}</div>

    <div class="lang"><div class="lang-tag" id="refTag">${refLang(p).toUpperCase()}</div><div>
      <h1 class="ru-text">«${esc(p.ru)}»</h1>
      ${S.lang === "en" && p.has_en ? `<div class="ua-meta">звук — англійський оригінал; текст — з російського транскрипту</div>`
        : S.lang === "en" ? `<div class="ua-meta">англійського оригіналу для цієї репліки немає — звучить російський</div>` : ""}
      ${S.lang === "ru" && !p.has_ru ? `<div class="ua-meta">російського оригіналу немає (потрібен мовний пакет — README) — звучить англійський</div>` : ""}
      <div class="wave-row"><button class="play big" data-play="ref" title="Оригінал (R)">▶</button>
        <canvas class="wave" data-wave="ref"></canvas><span class="dur" id="refDur">${fmt(p.ru_dur)}</span></div>
      <div class="orig-row"><button class="btn quiet" id="keepOrig" ${p.original && p.original.lang === refLang(p) ? "disabled" : ""} title="Для звуків без слів (Угу, сміх, крики): у гру піде оригінал без переозвучення (O)">Залишити оригінал (${refLang(p).toUpperCase()})</button>
        ${p.orig_hint && !p.original ? `<span class="chip hint" title="Короткий вигук чи звук без слів">Можна залишити оригінал</span>` : ""}</div></div></div>

    <div class="lang ua-block"><div class="lang-tag">UA</div><div>
      <input class="ua-input" id="ua" value="${esc(p.ua)}" placeholder="Український текст репліки" spellcheck="true">
      <div class="ua-meta"><span id="uaState">${textState}</span>
        ${p.ua_custom && p.ua_hint && p.ua_hint !== p.ua ? `<button class="linkish" id="resetText">повернути «${esc(p.ua_hint)}»</button>` : ""}</div>
      ${p.direction ? `<div class="direction"><b>Як грати</b>${esc(p.direction)}</div>` : ""}
      ${p.original ? `<div class="approved-banner orig"><span>♪</span><span class="grow">Залишено оригінал (${p.original.lang.toUpperCase()}) — переозвучення не потрібне → <code>game-files/${esc(p.game_rel)}</code></span>
        <button class="btn quiet" id="playGame">▶ Як у грі</button><button class="btn quiet" id="clearOrig">Скасувати</button></div>` : ""}
      ${p.approved ? `<div class="approved-banner"><span>✓</span><span class="grow">У грі — <b>Дубль ${apprTake ? apprTake.n : "?"}</b> → <code>game-files/${esc(p.game_rel)}</code></span>
        <button class="btn quiet" id="playGame">▶ Як у грі</button><button class="btn quiet" id="unapprove">Скасувати вибір</button></div>` : ""}
    </div></div>

    <div class="rec-zone">
      <button class="rec-btn" id="recBtn" title="Запис / стоп (Пробіл)"></button>
      <div class="rec-info"><div class="rec-title" id="recTitle"></div><div class="rec-sub" id="recSub"></div>
        <div class="meter" id="meter">${"<i></i>".repeat(20)}</div>
        <label class="mic-pick" title="Звідки записувати звук">🎙 <select id="micSel"></select></label></div>
      <div class="timer" id="timer">0.0 с<small>макс. ${MAX_REC} с</small></div>
    </div>

    <div class="section-h"><h3>Дублі</h3><span>${active.length ? `${active.length} · новіші зверху` : ""}</span>
      ${active.length ? `<details class="legend"><summary title="Що означають позначки">? Як читати</summary><div>
        <p><i class="lg-mark"></i><b>Помаранчевий пунктир «оригінал»</b> — де закінчився б голос, якби ви говорили
          так само довго, як в оригіналі (відлік від початку вашого голосу). Ваша хвиля помітно далі за пунктир —
          репліка задовга, у грі звучатиме повільніше за анімацію.</p>
        <p><span class="fit good">голос 0.80 с · +0.05 с</span> довжина вашого голосу без тиші на краях і різниця з оригіналом:
          <b class="ok-t">зелений</b> — вкладаєтесь (до +10 %), <b class="warn-t">жовтий</b> — трохи довше (до +30 %),
          <b class="bad-t">червоний</b> — задовго, краще сказати швидше чи коротше.</p>
        <p><b>Тиша на початку й у кінці</b> (<i class="lg-auto"></i>заштрихована частина хвилі) у файлі для гри обрізається
          автоматично, якщо в шапці увімкнено «Обрізати тишу»; сам дубль не змінюється, тож у студії тишу чути.
          Почути точно як у грі — «▶ Як у грі» на будь-якому дублі (з обрізанням, темпом, шумоговоренням, EQ і гучністю оригіналу).</p>
        <p><b>⏩ Темп</b> — прискорює голос без зміни висоти (×0.8–×1.3). «Під довжину оригіналу» ставить темп так, щоб
          голос не перевищував оригінал; підпис «голос … с» уже враховує темп. Звичайне ▶ темп не чує — для цього «▶ Як у грі».</p>
        <p><b>Ручки на хвилі</b> — межі того, що піде в гру. З «Обрізати тишу» вони одразу стоять на краях голосу,
          тож ▶ і «Оригінал → дубль» звучать уже обрізаними. Тягніть, щоб обрізати сильніше (затемнене відкидається)
          або розсунути — тоді видно штриховану тишу. ←/→ на ручці — крок 10 мс, подвійний клік — повернути ручку,
          «Скинути» — обидві. Файл дубля не змінюється.</p>
        <p><kbd>A</kbd> — порівняти звучання з EQ і без нього (A/B) просто під час прослуховування; те саме — клік по чипу «EQ · профіль» на дублі.
          «Без EQ» вирівняно за гучністю, тож різниця — у тембрі, а не в голосності.</p>
        <p><b>Еквалайзер</b> (ліва панель) — дублі в студії звучать уже з EQ персонажа; «Слухаю без EQ» — порівняти.
          Новий вибір для гри отримує поточний профіль; уже обрані файли оновлює «Застосувати до обраних дублів».</p></div></details>` : ""}</div>
    <div class="takes">${active.length ? active.map((t) => takeRow(p, t, t.file === newFile)).join("")
      : `<div class="empty-takes">Ще немає дублів. Послухайте оригінал і запишіть перший — <kbd>Пробіл</kbd></div>`}</div>

    ${trash.length ? `<details class="fold"><summary>Кошик · ${trash.length}</summary><div class="takes">${trash.map((t) => takeRow(p, t)).join("")}</div></details>` : ""}
    <details class="fold"><summary>Журнал дій · ${p.history.length}</summary><ul class="history">
      ${p.history.slice().reverse().map((h) => `<li><time>${esc(timeLabel(h.ts))}</time><span>${esc(h.action)}</span></li>`).join("") || "<li>—</li>"}</ul></details>
  </div>`;
  setRecUI(Rec.on);                                  // перемальовка під час запису не «зупиняє» UI
  renderMicSel();
  $("#micSel").onchange = (e) => { e.target.blur(); switchMic(e.target.value); };  // Пробіл знову = запис
  bindCard(p);
  loadWaves(p);
  AI.mount(p);
}

async function loadWaves(p) {
  waves.clear();
  const unit = S.unit;
  let refBuf = null, refSpan = [0, p.ru_dur];
  try { refBuf = await loadBuf(urlRef(p)); refSpan = voiceSpan(refBuf); } catch (e) { console.warn("wave ref", e); document.body.dataset.waveErr = String(e); }
  if (cur() !== p || S.unit !== unit) return;
  const refVoice = refSpan[1] - refSpan[0];
  const mk = (id, buf, opts) => { const c = document.querySelector(`canvas[data-wave="${CSS.escape(id)}"]`); if (c) { waves.set(id, { canvas: c, buf, opts }); drawWave(id); } };
  const tbufs = [];
  for (const t of p.takes.filter((t) => t.exists)) {
    try { tbufs.push([t, await loadBuf(urlTake(t.file))]); } catch {}
  }
  if (cur() !== p) return;
  // спільний масштаб — оригінал + дублі поза кошиком (довгий видалений дубль не стискає решту хвиль)
  const scale = Math.max(refBuf ? refBuf.duration : 0, ...tbufs.filter(([t]) => !t.deleted).map(([, b]) => b.duration));
  if (refBuf) { mk("ref", refBuf, { color: "#5a6270", played: "#e4572e", scale }); const d = $("#refDur"); if (d) d.textContent = fmt(refBuf.duration); }
  for (const [t, b] of tbufs) {
    const [va, vb] = voiceSpan(b);
    AUTO.set(t.file, [va, vb]);
    const appr = p.approved === t.file;
    const cv = document.querySelector(`canvas[data-wave="${CSS.escape("take:" + t.file)}"]`);
    if (cv) cv.title = "Помаранчевий пунктир — довжина голосу в оригіналі, відкладена від початку вашого голосу";
    const wid = "take:" + t.file;
    mk(wid, b, { color: appr ? "#3f8f57" : "#4f5765", played: appr ? "#46c46a" : "#e4572e", scale, marker: va + refVoice });
    // голос і пунктир «оригінал» рахуються в межах ручного обрізання; mountTrim викликає це й під час перетягування
    const f = document.querySelector(`[data-fit="${CSS.escape(t.file)}"]`);
    // тиша, яку «Обрізати тишу» зріже у файлі для гри (той самий поріг −45 дБ і запас, що в ffmpeg)
    const autoL = cv && autoDim(cv, "Тиша — у файлі для гри обріжеться («Обрізати тишу»)");
    const autoR = cv && autoDim(cv, "Тиша — у файлі для гри обріжеться («Обрізати тишу»)");
    const refit = (tr) => {
      if (autoL) {
        const pc = (x) => `${(100 * x) / scale}%`, a0 = Math.min(Math.max(va, tr.start), tr.end), b0 = Math.max(Math.min(vb, tr.end), a0);
        autoL.style.cssText = `left:${pc(tr.start)};width:${pc(a0 - tr.start)}`;
        autoR.style.cssText = `left:${pc(b0)};width:${pc(tr.end - b0)}`;
      }
      let a = Math.max(va, tr.start), e = Math.min(vb, tr.end);
      if (e <= a) [a, e] = [tr.start, tr.end];
      const voice = e - a, tempo = tempoOf(p, t.file), fi = fitInfo(voice / tempo, refVoice), w = waves.get(wid);
      FIT.set(t.file, { voice, refVoice });                            // для «Під довжину оригіналу»
      const mk2 = a + refVoice * tempo;                                // де закінчився б голос оригінальної довжини
      if (w) { w.opts.marker = mk2; drawWave(wid); }
      if (cv) cv.dataset.markerSec = mk2.toFixed(3);
      if (f) { f.className = "fit " + fi.cls; f.textContent = fi.text; f.title = `Ваш голос (без тиші на краях і обрізання) — ${fmt(voice)}; голос в оригіналі — ${fmt(refVoice)}${tempo !== 1 ? `; з темпом ${tempoFmt(tempo)} звучить ${fmt(voice / tempo)}` : ""}. Зелений ≤ +10 %, жовтий ≤ +30 %, червоний — задовго.`; }
    };
    mountTrim(p, t, b.duration, scale, refit);
  }
}

function bindCard(p) {
  const ua = $("#ua");
  ua.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); ua.blur(); }
    if (e.key === "Escape") { ua.value = p.ua; ua.blur(); }
    e.stopPropagation();
  });
  ua.addEventListener("blur", saveText);
  $("#resetText")?.addEventListener("click", () => { ua.value = p.ua_hint; saveText(); });
  $("#recBtn").addEventListener("click", toggleRec);
  $("#unapprove")?.addEventListener("click", unapprove);
  $("#keepOrig")?.addEventListener("click", () => keepOriginal(p));
  $("#clearOrig")?.addEventListener("click", clearOriginal);
  $("#playGame")?.addEventListener("click", () => play([{ url: aurl("game", p.id) + `?v=${Date.now()}`, id: "game" }]));
  $("#main").oninput = (e) => { const r = e.target.closest("[data-tempo-range]"); if (r) tempoLabel(r); };
  $("#main").onchange = (e) => { const r = e.target.closest("[data-tempo-range]"); if (r) saveTempo(ids(p), r.dataset.tempoRange, tempoOf(p, r.dataset.tempoRange), +r.value); };
  $("#main").onclick = (e) => {
    const b = e.target.closest("button, canvas");
    if (!b) return;
    const d = b.dataset;
    if (d.eqChip !== undefined) return eqToggleAB();
    if (d.play || d.wave) {
      const id = d.play || d.wave;
      if (playing && playing.id === id) return stopPlay();
      return play([id === "ref" ? { url: urlRef(p), id } : takeItem(p, id.slice(5))]);
    }
    if (d.preview) return playPreview(p, d.preview);
    if (d.tempoToggle || d.tempoFit || d.tempoReset) return tempoClick(p, d);
    if (d.ab) return play([{ url: urlRef(p), id: "ref" }, takeItem(p, d.ab)]);
    if (d.trimReset) return resetTrim(p, d.trimReset);
    if (d.approve) return approve(d.approve);
    if (d.del) return del(d.del);
    if (d.restore) return restore(d.restore);
  };
}

// ------------------------------------------------------------------ дії
// Відповідь сервера кладемо за (каталог, юніт, id репліки), а не за поточним індексом:
// поки йшов запит, користувач міг перейти на іншу репліку чи юніт.
function putPhrase(where, res, newFile) {
  if (!res || where.cid !== S.cat || where.gid !== S.unit) { loadCatalogs(); return; }
  const i = S.phrases.findIndex((x) => x.id === res.id);
  if (i < 0) return;
  S.phrases[i] = res;
  renderCues();
  if (i === S.idx) renderCard(newFile);
  loadCatalogs();
}
async function act(path, body) {
  try { return await post(path, { ...ids(), ...body }); }
  catch (e) { toast(e.message, true); return null; }
}
async function saveText() {
  const ua = $("#ua"), p = cur();
  if (!ua || !p || ua.value.trim() === p.ua) return;
  const where = ids(), prev = p.ua;
  const res = await act("/api/text", { text: ua.value });
  if (!res) return;
  if (where.cid === S.cat && where.gid === S.unit) {
    const i = S.phrases.findIndex((x) => x.id === res.id);
    if (i >= 0) S.phrases[i] = res;
    renderCues();
    if (cur()?.id === res.id) { const st = $("#uaState"); if (st) st.textContent = "✓ збережено"; }
  }
  setUndo("Текст змінено", async () => putPhrase(where, await post("/api/text", { ...where, text: prev })));
}
async function approve(file) {
  const where = ids(), prev = cur().approved;
  const res = await act("/api/approve", { file });
  if (!res) return;
  putPhrase(where, res);
  const n = res.takes.find((t) => t.file === file)?.n;
  toast(`Дубль ${n} обрано для гри`, false, 5000, () => undoTo(where, prev));
}
async function unapprove() {
  const where = ids(), prev = cur().approved;
  const res = await act("/api/unapprove", {});
  if (!res) return;
  putPhrase(where, res);
  toast("Вибір скасовано — дубль лишився у списку", false, 5000, () => undoTo(where, prev));
}
// «Залишити оригінал»: у гру йде необроблений оригінал у вибраній мові; взаємовиключно з обраним дублем
async function keepOriginal(p) {
  const where = ids(), prev = { approved: p.approved, original: p.original }, lang = refLang(p);
  const res = await act("/api/original", { lid: p.id, lang });
  if (!res) return;
  putPhrase(where, res);
  toast(`Залишено оригінал (${lang.toUpperCase()}) — переозвучення не потрібне`, false, 5000, () => undoOriginal(where, p.id, prev));
}
async function clearOriginal() {
  const p = cur(), where = ids(), prev = { approved: null, original: p.original };
  const res = await act("/api/original/clear", { lid: p.id });
  if (!res) return;
  putPhrase(where, res);
  toast("Оригінал прибрано з гри", false, 5000, () => undoOriginal(where, p.id, prev));
}
async function undoOriginal(where, lid, prev) {
  const body = { ...where, lid };
  const res = prev.approved ? await post("/api/approve", { ...body, file: prev.approved })
    : prev.original ? await post("/api/original", { ...body, lang: prev.original.lang })
    : await post("/api/original/clear", body);
  putPhrase(where, res);
}
async function undoTo(where, prevApproved) {
  const res = prevApproved
    ? await post("/api/approve", { ...where, file: prevApproved })
    : await post("/api/unapprove", where);
  putPhrase(where, res);
}
async function del(file) {
  stopPlay();
  const where = ids(), wasAppr = cur().approved === file;
  const res = await act("/api/delete", { file });
  if (!res) return;
  putPhrase(where, res);
  const n = res.takes.find((t) => t.file === file)?.n;
  toast(`Дубль ${n} у кошику${wasAppr ? " (вибір для гри знято)" : ""}`, false, 7000, async () => {
    let r = await post("/api/restore", { ...where, file });
    if (wasAppr) r = await post("/api/approve", { ...where, file });
    putPhrase(where, r);
  });
}
async function restore(file) {
  const where = ids();
  const res = await act("/api/restore", { file });
  if (res) { putPhrase(where, res, file); toast("Дубль відновлено"); }
}

// ------------------------------------------------------------------ ручне обрізання дубля (ручки на хвилі)
// Файл дубля не змінюється: сервер зберігає {start, end} і застосовує їх при копіюванні в гру.
const MIN_TRIM = 0.25; // = MIN_TAKE_SEC на сервері
const trimOf = (p, file) => p.takes.find((t) => t.file === file)?.trim || null;
// Межі голосу дубля (voiceSpan, той самий поріг, що в ffmpeg) — заповнюється при малюванні хвиль.
const AUTO = new Map();
/** Межі без ручного обрізання: з «Обрізати тишу» — краї голосу (те, що й так піде в гру), інакше весь файл. */
const autoEdges = (file, dur) => ($("#optTrim")?.checked && AUTO.has(file) ? { start: AUTO.get(file)[0], end: AUTO.get(file)[1] } : { start: 0, end: dur });
/** Що звучить у грі: ручне обрізання, інакше авто-межі (якщо їх уже пораховано). */
const effTrim = (p, file) => trimOf(p, file) || (AUTO.has(file) && $("#optTrim")?.checked ? autoEdges(file, 0) : null);
/** Елемент для play(): дубль звучить так, як піде в гру (у межах обрізання). */
const takeItem = (p, file) => { const tr = effTrim(p, file); return { url: urlTake(file), id: "take:" + file, ...(tr ? { start: tr.start, end: tr.end } : {}) }; };
const trimFmt = (a, b) => `${a.toFixed(2)}–${b.toFixed(2)} с`;

function autoDim(cv, title) {
  const d = document.createElement("div"); d.className = "auto-dim"; d.title = title; cv.parentElement.appendChild(d); return d;
}
function mountTrim(p, t, dur, scale, onChange = () => {}) {
  const cv = document.querySelector(`canvas[data-wave="${CSS.escape("take:" + t.file)}"]`);
  const info = document.querySelector(`[data-trim-info="${CSS.escape(t.file)}"]`);
  if (!cv || t.deleted) return;
  const box = cv.parentElement, where = ids(p), base = autoEdges(t.file, dur), tr = { start: t.trim?.start ?? base.start, end: t.trim?.end ?? base.end };
  const el = (cls, html = "") => { const d = document.createElement("div"); d.className = cls; d.innerHTML = html; box.appendChild(d); return d; };
  const dimL = el("trim-dim"), dimR = el("trim-dim");
  const hS = el("trim-h start"), hE = el("trim-h end");
  for (const [h, name] of [[hS, "початок"], [hE, "кінець"]]) {
    h.tabIndex = 0; h.setAttribute("role", "slider"); h.setAttribute("aria-label", `Обрізати ${name} дубля`);
    h.setAttribute("aria-valuemin", "0"); h.setAttribute("aria-valuemax", String(dur));
  }
  const paint = () => {
    const pc = (x) => `${(100 * x) / scale}%`;
    dimL.style.cssText = `left:0;width:${pc(tr.start)}`;
    dimR.style.cssText = `left:${pc(tr.end)};width:${pc(dur - tr.end)}`;
    hS.style.left = pc(tr.start); hE.style.left = pc(tr.end);
    hS.setAttribute("aria-valuenow", tr.start.toFixed(3)); hE.setAttribute("aria-valuenow", tr.end.toFixed(3));
    hS.title = `Початок ${tr.start.toFixed(2)} с — тягніть; ←/→ крок 10 мс; подвійний клік — скинути`;
    hE.title = `Кінець ${tr.end.toFixed(2)} с — тягніть; ←/→ крок 10 мс; подвійний клік — скинути`;
    onChange(tr);
    const on = Math.abs(tr.start - base.start) > 0.0005 || Math.abs(tr.end - base.end) > 0.0005;
    if (info) info.innerHTML = on ? `<span class="trim-t">✂ ${trimFmt(tr.start, tr.end)}</span><button class="linkish" data-trim-reset="${esc(t.file)}">Скинути</button>` : "";
  };
  const setEdge = (which, x) => {
    x = Math.round(x * 1000) / 1000;
    if (which === "start") tr.start = Math.max(0, Math.min(x, tr.end - MIN_TRIM));
    else tr.end = Math.min(dur, Math.max(x, tr.start + MIN_TRIM));
    paint();
  };
  let timer = null;
  const commit = (which) => {
    clearTimeout(timer);
    const cur0 = trimOf(S.phrases.find((x) => x.id === p.id) || p, t.file), a = cur0 ? cur0.start : base.start, b = cur0 ? cur0.end : base.end;
    if (Math.abs(tr.start - a) < 0.0005 && Math.abs(tr.end - b) < 0.0005) return;
    const full = Math.abs(tr.start - base.start) < 0.0005 && Math.abs(tr.end - base.end) < 0.0005;  // = авто-межі → без ручного
    S.refocus = { file: t.file, which };
    saveTrim(where, t.file, cur0, full ? null : tr.start, full ? null : tr.end);
  };
  for (const [h, which] of [[hS, "start"], [hE, "end"]]) {
    h.onpointerdown = (e) => { e.preventDefault(); h.setPointerCapture(e.pointerId); h.focus(); h.classList.add("drag"); };
    h.onpointermove = (e) => {
      if (!h.hasPointerCapture(e.pointerId)) return;
      const r = box.getBoundingClientRect();
      setEdge(which, ((e.clientX - r.left) / r.width) * scale);
    };
    h.onpointerup = h.onpointercancel = (e) => { h.classList.remove("drag"); if (h.hasPointerCapture(e.pointerId)) { h.releasePointerCapture(e.pointerId); commit(which); } };
    h.ondblclick = () => { setEdge(which, base[which]); commit(which); };
    h.onkeydown = (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault(); e.stopPropagation();                        // глобальні стрілки міняють репліку
      setEdge(which, tr[which] + (e.key === "ArrowRight" ? 0.01 : -0.01) * (e.shiftKey ? 10 : 1));
      clearTimeout(timer); timer = setTimeout(() => commit(which), 500);
    };
  }
  paint();
  if (S.refocus && S.refocus.file === t.file) { (S.refocus.which === "end" ? hE : hS).focus(); S.refocus = null; }
}
async function saveTrim(where, file, prev, start, end) {
  let res;
  try { res = await post("/api/trim", { ...where, file, start, end }); }
  catch (e) {
    toast(e.message, true);
    if (where.cid === S.cat && where.gid === S.unit) renderCard();
    return;
  }
  putPhrase(where, res);
  const n = res.takes.find((t) => t.file === file)?.n;
  toast(start == null ? `Обрізання дубля ${n} скинуто` : `Дубль ${n} обрізано: ${trimFmt(start, end)}`, false, 5000, async () =>
    putPhrase(where, await post("/api/trim", { ...where, file, start: prev ? prev.start : null, end: prev ? prev.end : null })));
}
function resetTrim(p, file) {
  saveTrim(ids(p), file, trimOf(p, file), null, null);
}

// ------------------------------------------------------------------ обробка для гри: налаштування, темп, «Як у грі»
// Перемикачі обробки живуть на сервері (data/studio/settings.json): ті самі для затвердження, перезапису й «Як у грі».
const SETTING_IDS = { optTrim: "auto_trim", optDenoise: "denoise", optLoudness: "loudness" };
async function settingsSetup() {
  let cfg = {};
  try { cfg = await getJSON("/api/settings"); } catch (e) { toast("Налаштування не завантажились: " + e.message, true); }
  for (const [id, key] of Object.entries(SETTING_IDS)) {
    const el = $("#" + id);
    if (key in cfg) el.checked = !!cfg[key];
    el.onchange = async () => {
      syncOpts();
      try { await post("/api/settings", { [key]: el.checked }); } catch (e) { el.checked = !el.checked; syncOpts(); toast(e.message, true); return; }
      if (key !== "auto_trim") toast("Діє на нові вибори; обрані файли оновить «Застосувати до обраних дублів» (Еквалайзер)", false, 6000);
    };
  }
  syncOpts();
}
const TEMPO_MIN = 0.8, TEMPO_MAX = 1.3;
const FIT = new Map();                                   // файл дубля → {voice, refVoice} без темпу (заповнює refit)
const tempoOf = (p, file) => p.takes.find((t) => t.file === file)?.tempo || 1;
const tempoFmt = (x) => `×${(+x).toFixed(2)}`;
const tempoBadge = (t) => (Math.abs((t.tempo || 1) - 1) > 0.0005 ? `<span class="tempo-t" title="Темп дубля: прискорення без зміни висоти">${tempoFmt(t.tempo)}</span>` : "");
function tempoPanel(t) {
  const v = t.tempo || 1;
  return `<div class="tempo-pop" data-tempo-pop="${esc(t.file)}" ${S.tempoOpen === t.file ? "" : "hidden"}>
    <label>Темп <input type="range" min="${TEMPO_MIN}" max="${TEMPO_MAX}" step="0.01" value="${v}" data-tempo-range="${esc(t.file)}"><b data-tempo-val>${tempoFmt(v)}</b></label>
    <button class="btn" data-tempo-fit="${esc(t.file)}" title="Темп = голос / голос оригіналу (1.0–1.3)">Під довжину оригіналу</button>
    <button class="linkish" data-tempo-reset="${esc(t.file)}">Скинути</button></div>`;
}
const tempoLabel = (r) => { const b = r.parentElement.querySelector("[data-tempo-val]"); if (b) b.textContent = tempoFmt(r.value); };
function tempoClick(p, d) {
  if (d.tempoToggle) {
    const open = S.tempoOpen !== d.tempoToggle;
    S.tempoOpen = open ? d.tempoToggle : null;
    document.querySelectorAll("[data-tempo-pop]").forEach((x) => { x.hidden = !(open && x.dataset.tempoPop === d.tempoToggle); });
  } else if (d.tempoReset) saveTempo(ids(p), d.tempoReset, tempoOf(p, d.tempoReset), null);
  else {
    const f = FIT.get(d.tempoFit);
    if (!f || !f.refVoice) return toast("Довжину оригіналу ще не пораховано", true);
    saveTempo(ids(p), d.tempoFit, tempoOf(p, d.tempoFit), Math.min(TEMPO_MAX, Math.max(1, Math.ceil((f.voice / f.refVoice) * 100) / 100)));
  }
}
async function saveTempo(where, file, prev, tempo) {
  let res;
  try { res = await post("/api/tempo", { ...where, file, tempo }); }
  catch (e) { toast(e.message, true); if (where.cid === S.cat && where.gid === S.unit) renderCard(); return; }
  putPhrase(where, res);
  const n = res.takes.find((t) => t.file === file)?.n, none = tempo == null || Math.abs(tempo - 1) < 0.0005;
  toast(none ? `Темп дубля ${n} скинуто` : `Дубль ${n} прискорено ${tempoFmt(tempo)}`, false, 5000, async () =>
    putPhrase(where, await post("/api/tempo", { ...where, file, tempo: prev > 1.0005 || prev < 0.9995 ? prev : null })));
}
/** «Як у грі» для будь-якого дубля: сервер збирає той самий ланцюжок, що й копія для гри (EQ уже всередині). */
function playPreview(p, file) {
  const id = "preview:" + file;
  if (playing && playing.id === id) return stopPlay();
  const q = new URLSearchParams({ cid: S.cat, gid: S.unit, lid: p.id, file, v: Date.now() });
  play([{ url: `/api/preview?${q}`, id, nocache: true }]);
}

// ------------------------------------------------------------------ toast + undo
// ⌘Z діє лише поки видно підказку (або кілька секунд після зміни тексту) — не «через хвилини».
let toastTimer = null, undoTimer = null;
function setUndo(label, fn, ms = 7000) {
  S.undo = fn ? { label, fn } : null;
  clearTimeout(undoTimer);
  if (fn) undoTimer = setTimeout(() => { S.undo = null; }, ms);
}
function toast(msg, err = false, ms = 4000, undoFn = null) {
  const t = $("#toast");
  t.className = "toast" + (err ? " err" : "");
  t.innerHTML = `<span>${esc(msg)}</span>` + (undoFn ? `<button id="undoBtn">Скасувати <small>⌘Z</small></button>` : "");
  t.hidden = false;
  if (undoFn) { setUndo(msg, undoFn, ms); $("#undoBtn").onclick = runUndo; }
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, ms);
}
async function runUndo() {
  if (!S.undo) return;
  const u = S.undo; S.undo = null; $("#toast").hidden = true;
  try { await u.fn(); toast("Скасовано"); } catch (e) { toast("Не вдалося скасувати: " + e.message, true); }
}

// ------------------------------------------------------------------ клавіатура
document.addEventListener("keydown", (e) => {
  if (!e.target.matches("#eq input[type=range]") && e.target.closest("input, textarea, select, summary, .trim-h, #eq")) return;  // елементи керування мають свої клавіші (повзунки EQ — див. eqSetup)
  if ((e.metaKey || e.ctrlKey) && e.code === "KeyZ") { e.preventDefault(); return runUndo(); }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.code === "Escape") return toggleUnitPopover(false);
  if (e.code === "Space") { e.preventDefault(); return toggleRec(); }
  if (Rec.on) return;
  const p = cur(); if (!p) return;
  const last = p.takes.filter((t) => !t.deleted && t.exists).slice(-1)[0];
  switch (e.code) {
    case "KeyR": play([{ url: urlRef(p), id: "ref" }]); break;
    case "KeyL": if (last) play([takeItem(p, last.file)]); break;
    case "KeyB": if (last) play([{ url: urlRef(p), id: "ref" }, takeItem(p, last.file)]); break;
    case "KeyA": eqToggleAB(); break;
    case "KeyN": nextTodo(); break;
    case "KeyO": keepOriginal(p); break;
    case "ArrowDown": e.preventDefault(); step(1); break;
    case "ArrowUp": e.preventDefault(); step(-1); break;
  }
});

// ------------------------------------------------------------------ старт
$("#unitBtn").onclick = () => toggleUnitPopover();
$("#unitPopover").onclick = (e) => {
  const tab = e.target.closest("[data-cat]");
  if (tab) { popCat = tab.dataset.cat; return renderUnitGrid(); }
  const c = e.target.closest("[data-unit]");
  if (c) { toggleUnitPopover(false); openUnit(c.dataset.unitCat, c.dataset.unit); }
  else if (e.target.id === "unitPopover") toggleUnitPopover(false);
};
$("#filter").onclick = (e) => {
  const b = e.target.closest("button"); if (!b) return;
  S.filter = b.dataset.f;
  document.querySelectorAll("#filter button").forEach((x) => x.classList.toggle("on", x === b));
  renderCues();
};
$("#cues").onclick = (e) => { const li = e.target.closest("[data-i]"); if (li) select(+li.dataset.i); };
$("#openGameDir").onclick = () => post("/api/open-dir", { cid: S.cat, gid: S.unit }).catch((e) => toast(e.message, true));
refreshMics();

// мова оригіналу
try { S.lang = localStorage.getItem("studio.lang") || "ru"; } catch { S.lang = "ru"; }
function renderLang() {
  for (const b of document.querySelectorAll("#optLang button")) b.classList.toggle("on", b.dataset.lang === S.lang);
}
$("#optLang").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-lang]");
  if (!b || b.dataset.lang === S.lang) return;
  S.lang = b.dataset.lang;
  try { localStorage.setItem("studio.lang", S.lang); } catch {}
  renderLang(); stopPlay(); if (cur()) renderCard();
});
renderLang();

{ // «Слухати після запису» — лише налаштування цього браузера; решта перемикачів — на сервері (settingsSetup)
  const el = $("#optAutoplay");
  try { const v = localStorage.getItem("studio.optAutoplay"); if (v !== null) el.checked = v === "1"; } catch {}
  el.onchange = () => { try { localStorage.setItem("studio.optAutoplay", el.checked ? "1" : "0"); } catch {} };
}
function syncOpts() { document.body.classList.toggle("no-autotrim", !$("#optTrim").checked); }
$("#optTrim").addEventListener("change", () => { if (cur()) renderCard(); });   // ручки стають на нові авто-межі
syncOpts();
window.addEventListener("resize", () => waves.forEach((_, id) => drawWave(id)));
window.addEventListener("beforeunload", (e) => { if (Rec.on) { e.preventDefault(); e.returnValue = ""; } });

(async () => {
  await settingsSetup();
  S.catalogs = await getJSON("/api/catalogs");
  let pos = null;
  try { pos = JSON.parse(localStorage.getItem("studio.pos") || "null"); } catch {}
  if (!pos || !S.catalogs.some((c) => c.id === pos.cid && c.groups.some((g) => g.id === pos.gid))) {
    const c = S.catalogs[0];
    pos = c && { cid: c.id, gid: c.groups[0]?.id };
  }
  if (pos) await openUnit(pos.cid, pos.gid);
})().catch((e) => { $("#main").innerHTML = `<div class="empty">Помилка: ${esc(e.message)}</div>`; });

// ------------------------------------------------------------------ анімації (лише презентація)
// Поява хвилі: клас .ready знімає opacity:0 (CSS-перехід).
{
  const baseDraw = drawWave;
  drawWave = (id, ...a) => { baseDraw(id, ...a); waves.get(id)?.canvas.classList.add("ready"); };
}
// Видалення: картка коротко згасає перед перемальовкою.
const baseDel = del;
del = async (file) => {
  const row = document.querySelector(`[data-del="${CSS.escape(file)}"]`)?.closest(".take");
  if (row && !matchMedia("(prefers-reduced-motion: reduce)").matches) { row.classList.add("leaving"); await new Promise((r) => setTimeout(r, 160)); }
  try { return await baseDel(file); } finally { row?.classList.remove("leaving"); }
};

// ------------------------------------------------------------------ перевантаження мікрофона (clipping)
// Живо: відлік |x| ≥ 0.98 у воркліті → метр червоніє, у панелі запису — «перевантаження» (раз на дубль, без тостів).
// Після збереження сервер дає take.clipped/peak_db → червоний бейдж у рядку дубля й тост із порадою.
const CLIP_LEVEL = 0.98;
const CLIP_ADVICE = "Голос «рве» мікрофон: відсуньтесь на 10–15 см або зменште гучність входу в Системних параметрах → Звук → Вхід";
const Clip = { take: null, flagged: false, timer: null };
function clipCheck(buf) {
  if (Clip.take !== Rec.t0) { Clip.take = Rec.t0; Clip.flagged = false; $("#clipFlag")?.setAttribute("hidden", ""); }
  let hit = false;
  for (let i = 0; i < buf.length; i++) if (buf[i] >= CLIP_LEVEL || buf[i] <= -CLIP_LEVEL) { hit = true; break; }
  if (!hit) return;
  const m = $("#meter"); m?.classList.add("clip");
  clearTimeout(Clip.timer); Clip.timer = setTimeout(() => $("#meter")?.classList.remove("clip"), 700);
  if (!Clip.flagged) { Clip.flagged = true; $("#clipFlag")?.removeAttribute("hidden"); }
}
{
  const baseRenderCard = renderCard;               // індикатор у панелі запису (після кожної перемальовки картки)
  renderCard = (...a) => {
    baseRenderCard(...a);
    $("#recSub")?.insertAdjacentHTML("afterend", `<span class="clip-flag" id="clipFlag" title="${esc(CLIP_ADVICE)}" hidden>перевантаження</span>`);
  };
  const baseTakeRow = takeRow;                     // червоний бейдж у рядку дубля
  takeRow = (p, t, ...a) => {
    const html = baseTakeRow(p, t, ...a);
    return t.clipped ? html.replace('<span class="trim-info"',
      `<span class="badge-clip" title="${esc(CLIP_ADVICE)}">перевантаження</span><span class="trim-info"`) : html;
  };
}

// ------------------------------------------------------------------ встановлення в гру (install_voices через API)
// Вікно: дерево Раса → Юніт → файли з чекбоксами (стан — самі чекбокси в DOM), режими «Встановити» / «Прибрати з гри».
const Inst = { mode: "install", busy: false };
const instModal = () => $("#installModal");
const instBoxes = (el = instModal()) => [...el.querySelectorAll("input[data-f]")];
const instShort = (t) => String(t).replace(/\s*\(.*\)\s*$/, "");
const INST_TAGS = {
  new: ["нове", "new"], update: ["оновиться", "upd"], same: ["вже в грі", "same"],
  present: ["у грі", "new"], changed: ["змінено не нами", "same"], missing: ["файлу немає", "same"],
};
const nFiles = (n) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? "файл" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? "файли" : "файлів"}`;

const voiceUrl = (a, rel) => `/audio/voice/${encodeURIComponent(a)}/${rel.split("/").map(encodeURIComponent).join("/")}`;
const authName = (id) => ((Inst.authors || []).find((a) => a.id === id) || {}).name || id;
// Вибір голосу: <select> автора для раси / юніта / рядка (пише data/studio/voice-choice.json через /api/voices/choice).
function authSelect(attr, key, cur, ids) {
  if ((Inst.authors || []).length < 2) return "";
  const opts = [`<option value="">за замовчуванням</option>`, ...ids.map((a) => `<option value="${esc(a)}" ${a === cur ? "selected" : ""}>${esc(authName(a))}</option>`)];
  return `<select class="auth-sel" ${attr}="${esc(key)}" title="Чий голос">${opts.join("")}</select>`;
}
function instFile(f) {
  const [txt, cls] = INST_TAGS[f.status] || [f.status, ""];
  const off = f.status === "same" || f.status === "changed" || f.status === "missing";
  const un = Inst.mode === "uninstall";
  const who = un ? "" : (f.alts && f.alts.length > 1
    ? authSelect("data-vl", f.rel, (Inst.choice.line || {})[f.rel] || "", f.alts)
    : `<span class="tag who">${esc(authName(f.author))}</span>`) +
    (f.fallback ? `<span class="tag upd" title="Обраного автора цієї репліки немає — взято наступного за порядком">запасний: ${esc(authName(f.author))}</span>` : "") +
    `<button type="button" class="ghost play-v" data-play="${esc(f.rel)}" data-a="${esc(f.author)}" title="Послухати">▶</button>`;
  return `<li class="${off ? "dim" : ""}"><label><input type="checkbox" data-f="${esc(f.rel)}" ${off ? "" : "checked"}>
    <code>${esc(f.name)}</code><span class="tag ${cls}">${txt}</span></label>${who}</li>`;
}
function instUnit(r, u) {
  const mat = u.files.some((f) => f.materialize);
  return `<details class="inst-unit" data-key="${esc(r.id)}/${esc(u.id)}"><summary>
    <input type="checkbox" data-g title="Усі файли персонажа"><b>${esc(instShort(u.title))}</b>
    <small class="cnt"></small>${Inst.mode === "install" ? authSelect("data-vu", `${r.id}/${u.id}`, (Inst.choice.unit || {})[`${r.id}/${u.id}`] || "", Inst.authors.map((a) => a.id)) : ""}${mat ? `<span class="tag mat" title="Тека юніта в грі — симлінк на Mods/. Її буде замінено реальною текою з симлінками на оригінальні файли; відкат повертає симлінк.">потребує перетворення теки</span>` : ""}</summary>
    <ul class="inst-list">${u.files.map(instFile).join("")}</ul></details>`;
}
function instRender(pl) {
  const un = Inst.mode === "uninstall";
  Inst.authors = pl.authors || []; Inst.choice = pl.choice || { default: [], race: {}, unit: {}, line: {} };
  const body = pl.races.map((r) => `<details class="inst-race" data-key="${esc(r.id)}"><summary>
    <input type="checkbox" data-g title="Усі файли раси"><b>${esc(r.title)}</b><small class="cnt"></small>${
      Inst.mode === "install" ? authSelect("data-vr", r.id, (Inst.choice.race || {})[r.id] || "", Inst.authors.map((a) => a.id)) : ""}</summary>
    ${r.units.map((u) => instUnit(r, u)).join("")}</details>`).join("");
  $("#installBody").innerHTML = `<p class="inst-game">Тека гри: <code>${esc(pl.game)}</code></p>` +
    (body || `<p class="inst-note">${un ? "Нічого не встановлено нами." : "Немає обраних дублів у game-files/."}</p>`) +
    (pl.skipped && pl.skipped.length ? `<details class="inst-skip"><summary><b>Пропущено</b> <small>${pl.skipped.length}</small></summary><ul class="inst-list skip">${
      pl.skipped.map((s) => `<li><code>${esc(s.rel)}</code><small>${esc(s.reason)}</small></li>`).join("")}</ul></details>` : "") +
    (pl.same && !un ? `<p class="inst-note">Уже в грі й без змін: ${pl.same} (за замовчуванням не обрано)</p>` : "");
  instSync();
}
function instSync() {                          // стани груп (повністю / частково / нічого) і лічильники
  const m = instModal();
  for (const d of m.querySelectorAll("details.inst-unit, details.inst-race")) {
    const bx = instBoxes(d), on = bx.filter((b) => b.checked).length, g = d.querySelector(":scope > summary > input[data-g]");
    g.checked = bx.length > 0 && on === bx.length; g.indeterminate = on > 0 && on < bx.length;
    d.querySelector(":scope > summary .cnt").textContent = d.classList.contains("inst-race")
      ? `· ${on} з ${bx.length} обрано` : `· ${nFiles(bx.length)}` + (on < bx.length ? ` · ${on} обрано` : "");
  }
  const n = instBoxes().filter((b) => b.checked).length, un = Inst.mode === "uninstall";
  const go = $("#installGo");
  go.textContent = (un ? "Прибрати" : "Встановити") + (n ? ` (${n})` : "");
  go.classList.toggle("warn", un); go.disabled = !n || Inst.busy;
}
async function instLoad(keep) {                   // keep = {open: [data-key], off: [rel]} — стан дерева переживає перерахунок
  const state = keep || null;
  document.querySelectorAll("#installMode button").forEach((b) => b.classList.toggle("on", b.dataset.mode === Inst.mode));
  $("#installBody").innerHTML = `<p class="inst-note">Перевіряю…</p>`;
  $("#installGo").disabled = true;
  try {
    instRender(await getJSON(Inst.mode === "install" ? "/api/install/plan" : "/api/uninstall/plan"));
    if (state) {
      instModal().querySelectorAll("details[data-key]").forEach((d) => { d.open = state.open.includes(d.dataset.key); });
      instBoxes().forEach((b) => { if (state.off.includes(b.dataset.f)) b.checked = false; });
      instSync();
    }
  }
  catch (e) { $("#installBody").innerHTML = `<p class="inst-err">${esc(e.message)}</p>`; }
}
function openInstall() { instModal().hidden = false; instLoad(); }
const closeInstall = () => { instModal().hidden = true; };
async function instRun() {
  if (Inst.busy) return;
  const files = instBoxes().filter((b) => b.checked).map((b) => b.dataset.f), un = Inst.mode === "uninstall";
  if (!files.length) return;
  Inst.busy = true; $("#installGo").disabled = true;
  try {
    const r = await post(un ? "/api/uninstall" : "/api/install", { files });
    closeInstall();
    toast(un ? `Прибрано з гри файлів: ${r.removed}` + (r.restored_links.length ? `; симлінків повернуто: ${r.restored_links.length}` : "") + "."
      : `Встановлено файлів: ${r.installed}` + (r.materialized.length ? `; теки відкріплено від Mods: ${r.materialized.length}` : "") + ". Перезапустіть гру.", false, 9000);
    if (cur()) { try { renderCard(); } catch {} }
  } catch (e) { toast("Не вдалося: " + e.message, true, 10000); closeInstall(); }
  finally { Inst.busy = false; }
}
$("#installBtn").onclick = openInstall;
$("#installClose").onclick = closeInstall;
$("#installModal").addEventListener("click", (e) => { if (e.target.id === "installModal") closeInstall(); });
$("#installMode").onclick = (e) => { const b = e.target.closest("button[data-mode]"); if (b && b.dataset.mode !== Inst.mode) { Inst.mode = b.dataset.mode; instLoad(); } };
$("#installGo").onclick = instRun;
let vPlayer = null;
$("#installBody").addEventListener("click", (e) => {            // ▶ послухати рядок (обраного/поточного автора)
  const b = e.target.closest("button[data-play]");
  if (!b) return;
  const sel = b.parentElement.querySelector("select[data-vl]");
  if (vPlayer) vPlayer.pause();
  vPlayer = new Audio(voiceUrl((sel && sel.value) || b.dataset.a, b.dataset.play));
  vPlayer.play().catch((er) => toast("Не вдалося відтворити: " + er.message, true));
});
async function instChoose(sel) {
  const kind = sel.hasAttribute("data-vr") ? ["race", "data-vr"] : sel.hasAttribute("data-vu") ? ["unit", "data-vu"] : ["line", "data-vl"];
  const body = { [kind[0]]: { ...(Inst.choice[kind[0]] || {}), [sel.getAttribute(kind[1])]: sel.value || null } };
  const keep = { open: [...instModal().querySelectorAll("details[open][data-key]")].map((d) => d.dataset.key),
    off: instBoxes().filter((b) => !b.checked).map((b) => b.dataset.f) };
  try { await post("/api/voices/choice", body); } catch (er) { toast("Не вдалося: " + er.message, true); }
  instLoad(keep);
}
$("#installBody").addEventListener("change", (e) => {
  const t = e.target;
  if (t.matches("select.auth-sel")) return instChoose(t);
  if (t.matches("input[data-g]")) instBoxes(t.closest("details")).forEach((b) => { b.checked = t.checked; });   // група → усі нащадки
  instSync();
});
document.addEventListener("keydown", (e) => {     // поки відкрито вікно — клавіші студії (Пробіл = запис) не діють
  if (instModal().hidden) return;
  if (e.code === "Escape") closeInstall();
  e.stopImmediatePropagation();
}, true);

// ------------------------------------------------------------------ голоси спільноти (voices/, data/studio/voice-choice.json)
// Автори й порядок пріоритету (↑↓, чекбокс «використовувати»), публікація власного голосу зі згодою CC BY 4.0.
const Vs = { v: null, order: [], on: new Set(), result: null };
const voicesModal = () => $("#voicesModal");
const mb = (b) => (b / 1e6).toFixed(1) + " МБ";
function vCoverage(a) {
  const c = Object.entries(a.coverage).map(([r, u]) => `${esc(r)}: ${Object.values(u).reduce((x, y) => x + y, 0)}`);
  return c.join(" · ") || "порожньо";
}
function vRender() {
  const v = Vs.v, by = Object.fromEntries(v.authors.map((a) => [a.id, a]));
  const rows = Vs.order.map((id, i) => { const a = by[id]; return `<li class="v-row" data-id="${esc(id)}">
    <input type="checkbox" data-von ${Vs.on.has(id) ? "checked" : ""} title="Використовувати при встановленні">
    <span class="v-name"><b>${esc(a.name)}</b><small>${a.local ? "ваші затверджені дублі (game-files/)" : esc(a.license) + " · " + mb(a.bytes)}
      · ${nFiles(a.files)}${a.ai ? ` · <span class="tag upd" title="Згенеровано ШІ власним голосом автора">ШІ ${a.ai}</span>` : ""} · ${vCoverage(a)}</small></span>
    <button class="ghost" data-vup ${i ? "" : "disabled"} title="Вище (пріоритетніший)">↑</button>
    <button class="ghost" data-vdown ${i < Vs.order.length - 1 ? "" : "disabled"} title="Нижче">↓</button></li>`; }).join("");
  const r = Vs.result;
  $("#voicesBody").innerHTML = `<h4>Порядок за замовчуванням <small>перший, у кого є репліка, виграє; вибір для раси/юніта — у вікні «Встановити в гру»</small></h4>
    <ul class="v-list">${rows}</ul>
    <h4>Опублікувати мій голос</h4>
    <p class="inst-note">Експортуються лише ваші затверджені дублі з game-files/ (FLAC, ${esc(v.license)}). Git ми не запускаємо — лише підкажемо команди.</p>
    <div class="v-pub"><input id="vNick" placeholder="нікнейм (a-z, 0-9, -)" maxlength="32" value="${esc(v.nickname)}" autocomplete="off">
      <button class="btn primary" id="vPublish">Опублікувати</button></div>
    <label class="v-consent"><input type="checkbox" id="vConsent"> ${esc(v.consent_text)}</label>
    ${r ? `<div class="v-result"><p>+${r.added} нових · ${r.updated} оновлено · ${r.removed} прибрано · ${r.unchanged} без змін · усього ${nFiles(r.files)}, ${r.total_mb} МБ
      ${r.skipped.length ? ` · пропущено ${r.skipped.length}` : ""}</p><p class="inst-note">Далі виконайте в терміналі (репозиторій проєкту):</p><pre>${esc(r.git.join("\n"))}</pre></div>` : ""}`;
}
async function vSaveOrder() {
  try { Vs.v = await post("/api/voices/choice", { default: Vs.order.filter((id) => Vs.on.has(id)) }); }
  catch (e) { toast("Не вдалося: " + e.message, true); }
}
async function openVoices() {
  voicesModal().hidden = false;
  $("#voicesBody").innerHTML = `<p class="inst-note">Завантажую…</p>`;
  try {
    const v = Vs.v = await getJSON("/api/voices"), all = v.authors.map((a) => a.id);
    Vs.on = new Set(v.choice.default);
    Vs.order = [...v.choice.default.filter((id) => all.includes(id)), ...all.filter((id) => !v.choice.default.includes(id))];
    Vs.result = null; vRender();
  } catch (e) { $("#voicesBody").innerHTML = `<p class="inst-err">${esc(e.message)}</p>`; }
}
const closeVoices = () => { voicesModal().hidden = true; };
$("#voicesBtn").onclick = openVoices;
$("#voicesClose").onclick = closeVoices;
voicesModal().addEventListener("click", async (e) => {
  if (e.target.id === "voicesModal") return closeVoices();
  const row = e.target.closest(".v-row"), pub = e.target.closest("#vPublish");
  if (row && (e.target.closest("[data-vup]") || e.target.closest("[data-vdown]"))) {
    const i = Vs.order.indexOf(row.dataset.id), j = i + (e.target.closest("[data-vup]") ? -1 : 1);
    [Vs.order[i], Vs.order[j]] = [Vs.order[j], Vs.order[i]];
    await vSaveOrder(); vRender();
  }
  if (pub) {
    const nick = $("#vNick").value.trim(), consent = $("#vConsent").checked;
    if (!consent) return toast("Підтвердьте, що це ваш голос і ліцензію CC BY 4.0.", true);
    pub.disabled = true;
    try { Vs.result = await post("/api/voices/publish", { nickname: nick, consent }); Vs.v = await getJSON("/api/voices"); vRender(); }
    catch (er) { toast("Не вдалося: " + er.message, true, 8000); pub.disabled = false; }
  }
});
voicesModal().addEventListener("change", async (e) => {
  const row = e.target.closest(".v-row");
  if (row && e.target.matches("[data-von]")) {
    e.target.checked ? Vs.on.add(row.dataset.id) : Vs.on.delete(row.dataset.id);
    await vSaveOrder();
  }
});
document.addEventListener("keydown", (e) => {
  if (voicesModal().hidden) return;
  if (e.code === "Escape") closeVoices();
  e.stopImmediatePropagation();                 // у вікні клавіші студії (Пробіл = запис) не діють
}, true);
