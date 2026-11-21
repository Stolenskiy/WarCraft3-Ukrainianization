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
const aurl = (kind, name) => `/audio/${kind}/${S.cat}/${S.unit}/${encodeURIComponent(name)}`;
// мова оригіналу (налаштування в шапці): "ru" | "en"; якщо англійського файлу немає — рос.
const refLang = (p) => (S.lang === "en" && p.has_en ? "en" : "ru");
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
  const d = buf.getChannelData(0), thr = Math.pow(10, -45 / 20), w = Math.floor(buf.sampleRate * 0.01);
  const loud = (i) => { let m = 0; for (let k = i; k < Math.min(i + w, d.length); k++) m = Math.max(m, Math.abs(d[k])); return m > thr; };
  let a = 0, b = d.length - 1;
  while (a < d.length && !loud(a)) a += w;
  while (b > a && !loud(Math.max(0, b - w))) b -= w;
  if (a >= b) return [0, buf.duration];
  return [Math.max(0, a / buf.sampleRate - 0.08), Math.min(buf.duration, b / buf.sampleRate + 0.12)];
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

let playToken = null, playing = null; // playing: {id, src, t0, dur}
async function play(items) {
  stopPlay();
  const token = {};
  playToken = token;
  if (AC.state !== "running") AC.resume();
  for (const it of items) {
    let buf;
    try { buf = await loadBuf(it.url); } catch { toast("Не вдалося відкрити аудіо", true); return; }
    if (playToken !== token) return;
    await new Promise((res) => {
      const src = AC.createBufferSource();
      src.buffer = buf; src.connect(AC.destination); src.onended = res;
      playing = { id: it.id, src, t0: AC.currentTime, dur: buf.duration };
      src.start();
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
  document.querySelectorAll("[data-play]").forEach((b) => {
    const on = playing && b.dataset.play === playing.id;
    b.classList.toggle("playing", !!on); b.textContent = on ? "■" : "▶";
  });
}
(function anim() {
  if (playing) drawWave(playing.id, (AC.currentTime - playing.t0) / playing.dur);
  requestAnimationFrame(anim);
})();

// ------------------------------------------------------------------ запис (мікрофон тримаємо відкритим → старт миттєвий)
const Rec = { node: null, analyser: null, on: false, chunks: [], pre: [], t0: 0, sr: 48000 };
async function ensureMic() {
  if (Rec.node) return;
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
  });
  if (AC.state !== "running") AC.resume();
  const code = `class Cap extends AudioWorkletProcessor{constructor(){super();this.b=new Float32Array(2048);this.i=0}
    process(inp){const c=inp[0]&&inp[0][0];if(c){for(let k=0;k<c.length;k++){this.b[this.i++]=c[k];
    if(this.i===this.b.length){this.port.postMessage(this.b.slice(0));this.i=0}}}return true}}registerProcessor('cap',Cap)`;
  await AC.audioWorklet.addModule(URL.createObjectURL(new Blob([code], { type: "application/javascript" })));
  const src = AC.createMediaStreamSource(stream);
  Rec.sr = AC.sampleRate;
  Rec.node = new AudioWorkletNode(AC, "cap");
  const mute = AC.createGain(); mute.gain.value = 0;
  src.connect(Rec.node); Rec.node.connect(mute); mute.connect(AC.destination);
  Rec.analyser = AC.createAnalyser(); Rec.analyser.fftSize = 1024; src.connect(Rec.analyser);
  const preN = Math.ceil((0.25 * Rec.sr) / 2048); // 0.25 с «передзапису», щоб не з'їсти перший склад
  Rec.node.port.onmessage = (e) => {
    if (Rec.on) Rec.chunks.push(e.data);
    else { Rec.pre.push(e.data); if (Rec.pre.length > preN) Rec.pre.shift(); }
  };
  meterLoop();
}
function meterLoop() {
  const data = new Float32Array(Rec.analyser.fftSize);
  const tick = () => {
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
    const q = new URLSearchParams(ids(p)).toString();
    const res = await post(`/api/take?${q}`, encodeWav(pcm, Rec.sr), true);
    const newest = res.takes.filter((t) => !t.deleted).slice(-1)[0];
    applyPhrase(res, newest && newest.file);
    if ($("#optAutoplay").checked && newest) play([{ url: urlTake(newest.file), id: "take:" + newest.file }]);
  } catch (e) { toast("Не збережено: " + e.message, true); renderCard(); }
  finally { S.busy = false; }
}
function setRecUI(on) {
  $("#recBtn")?.classList.toggle("on", on);
  const t = $("#recTitle"), sub = $("#recSub"), tm = $("#timer");
  if (t) { t.textContent = on ? "Іде запис — говоріть" : "Готові записати дубль"; t.classList.toggle("live", on); }
  if (sub) sub.innerHTML = on ? "<kbd>Пробіл</kbd> — зупинити" : Rec.node ? "Мікрофон увімкнено — індикатор показує рівень. <kbd>Пробіл</kbd> — почати" : "<kbd>Пробіл</kbd> або кнопка — браузер попросить доступ до мікрофона";
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
    return `<button class="${x.id === c.id ? "on" : ""}" data-cat="${x.id}">${esc(x.title.split(" — ")[0])} <small>${d}/${t}</small></button>`;
  }).join("");
  const card = (g) => `<button class="unit-card ${c.id === S.cat && g.id === S.unit ? "on" : ""} ${g.done === g.total ? "complete" : ""}" data-unit="${g.id}" data-unit-cat="${c.id}">
      <span class="avatar">${esc(initials(g.title))}</span>
      <span class="meta"><b>${esc(g.title)}</b><small>${g.done} / ${g.total} · ${g.id}</small>
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
  const i = S.phrases.findIndex((p) => !p.approved && !p.no_speech);
  S.idx = i >= 0 ? i : 0;
  await loadCatalogs();
  const g = groupOf();
  $("#traits").innerHTML = g && g.traits.length
    ? g.traits.map((t) => { const [k, ...v] = t.split(": "); return `<p><b>${esc(k)}:</b> ${esc(v.join(": "))}</p>`; }).join("")
    : "<p>Аркуша персонажа у voice bible ще немає.</p>";
  renderCues(); renderCard();
}

// ------------------------------------------------------------------ список реплік
function visible() {
  return S.phrases.map((p, i) => i).filter((i) => {
    const p = S.phrases[i];
    return S.filter === "all" || (S.filter === "done" ? !!p.approved : !p.approved);
  });
}
function renderCues() {
  $("#cues").innerHTML = visible().map((i) => {
    const p = S.phrases[i], n = p.takes.filter((t) => !t.deleted).length;
    const st = p.approved ? "ok" : n ? "has" : p.no_speech ? "mute" : "";
    return `<li class="cue ${i === S.idx ? "on" : ""} ${p.no_speech ? "mute" : ""}" data-i="${i}">
      <span class="st ${st}"></span>
      <span><div class="ru">${esc(p.ru)}</div><div class="ua">${esc(p.ua)}</div></span>
      <span class="tag">${esc(p.kind_ua)}${n ? `<br>${n} дубл.` : ""}</span></li>`;
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
    if (!S.phrases[j].approved && !S.phrases[j].no_speech) return select(j);
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
       ${appr ? "" : `<button class="btn primary" data-approve="${esc(t.file)}" title="Цей дубль піде в гру">✓ Обрати</button>`}
       <button class="btn icon" data-del="${esc(t.file)}" title="У кошик (можна відновити)">🗑</button>`;
  return `<div class="take ${appr ? "approved" : ""} ${t.deleted ? "deleted" : ""} ${isNew ? "new" : ""}">
    <button class="play" data-play="${esc(id)}" ${t.exists ? "" : "disabled"}>▶</button>
    <div><div class="take-head"><b>Дубль ${t.n || "?"}</b>
      <span class="fit" data-fit="${esc(t.file)}">${t.exists ? fmt(t.dur) : "файл відсутній"}</span>
      ${appr ? `<span class="badge-game">У ГРІ</span>` : ""}
      <span class="time">${t.deleted ? "видалено " + timeLabel(t.deleted) : timeLabel(t.created)}</span></div>
      <canvas class="wave" data-wave="${esc(id)}"></canvas></div>
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
      ${p.no_speech ? `<span class="chip warn">у референсі немає мови</span>` : ""}</div>

    <div class="lang"><div class="lang-tag" id="refTag">${refLang(p).toUpperCase()}</div><div>
      <h1 class="ru-text">«${esc(p.ru)}»</h1>
      ${refLang(p) === "en" ? `<div class="ua-meta">звук — англійський оригінал; текст — з російського транскрипту</div>`
        : S.lang === "en" ? `<div class="ua-meta">англійського оригіналу для цієї репліки немає — звучить російський</div>` : ""}
      <div class="wave-row"><button class="play big" data-play="ref" title="Оригінал (R)">▶</button>
        <canvas class="wave" data-wave="ref"></canvas><span class="dur" id="refDur">${fmt(p.ru_dur)}</span></div></div></div>

    <div class="lang ua-block"><div class="lang-tag">UA</div><div>
      <input class="ua-input" id="ua" value="${esc(p.ua)}" placeholder="Український текст репліки" spellcheck="true">
      <div class="ua-meta"><span id="uaState">${textState}</span>
        ${p.ua_custom && p.ua_hint && p.ua_hint !== p.ua ? `<button class="linkish" id="resetText">повернути «${esc(p.ua_hint)}»</button>` : ""}</div>
      ${p.direction ? `<div class="direction"><b>Як грати</b>${esc(p.direction)}</div>` : ""}
      ${p.approved ? `<div class="approved-banner"><span>✓</span><span class="grow">У грі — <b>Дубль ${apprTake ? apprTake.n : "?"}</b> → <code>game-files/${esc(p.game_rel)}</code></span>
        <button class="btn quiet" id="playGame">▶ Як у грі</button><button class="btn quiet" id="unapprove">Скасувати вибір</button></div>` : ""}
    </div></div>

    <div class="rec-zone">
      <button class="rec-btn" id="recBtn" title="Запис / стоп (Пробіл)"></button>
      <div class="rec-info"><div class="rec-title" id="recTitle"></div><div class="rec-sub" id="recSub"></div>
        <div class="meter" id="meter">${"<i></i>".repeat(20)}</div></div>
      <div class="timer" id="timer">0.0 с<small>макс. ${MAX_REC} с</small></div>
    </div>

    <div class="section-h"><h3>Дублі</h3><span>${active.length ? `${active.length} · новіші зверху · пунктир = довжина оригіналу` : ""}</span></div>
    <div class="takes">${active.length ? active.map((t) => takeRow(p, t, t.file === newFile)).join("")
      : `<div class="empty-takes">Ще немає дублів. Послухайте оригінал і запишіть перший — <kbd>Пробіл</kbd></div>`}</div>

    ${trash.length ? `<details class="fold"><summary>Кошик · ${trash.length}</summary><div class="takes">${trash.map((t) => takeRow(p, t)).join("")}</div></details>` : ""}
    <details class="fold"><summary>Журнал дій · ${p.history.length}</summary><ul class="history">
      ${p.history.slice().reverse().map((h) => `<li><time>${esc(timeLabel(h.ts))}</time><span>${esc(h.action)}</span></li>`).join("") || "<li>—</li>"}</ul></details>
  </div>`;
  setRecUI(false);
  bindCard(p);
  loadWaves(p);
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
  const scale = Math.max(refBuf ? refBuf.duration : 0, ...tbufs.map(([, b]) => b.duration));
  if (refBuf) { mk("ref", refBuf, { color: "#5a6270", played: "#e4572e", scale }); const d = $("#refDur"); if (d) d.textContent = fmt(refBuf.duration); }
  for (const [t, b] of tbufs) {
    const [va, vb] = voiceSpan(b), voice = vb - va;
    const appr = p.approved === t.file;
    mk("take:" + t.file, b, { color: appr ? "#3f8f57" : "#4f5765", played: appr ? "#46c46a" : "#e4572e", scale, marker: va + refVoice });
    const f = document.querySelector(`[data-fit="${CSS.escape(t.file)}"]`), fi = fitInfo(voice, refVoice);
    if (f) { f.className = "fit " + fi.cls; f.textContent = fi.text; f.title = `Довжина голосу без тиші на краях; оригінал — ${fmt(refVoice)}`; }
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
  $("#playGame")?.addEventListener("click", () => play([{ url: aurl("game", p.id) + `?v=${Date.now()}`, id: "game" }]));
  $("#main").onclick = (e) => {
    const b = e.target.closest("button, canvas");
    if (!b) return;
    const d = b.dataset;
    if (d.play || d.wave) {
      const id = d.play || d.wave;
      if (playing && playing.id === id) return stopPlay();
      return play([{ url: id === "ref" ? urlRef(p) : urlTake(id.slice(5)), id }]);
    }
    if (d.ab) return play([{ url: urlRef(p), id: "ref" }, { url: urlTake(d.ab), id: "take:" + d.ab }]);
    if (d.approve) return approve(d.approve);
    if (d.del) return del(d.del);
    if (d.restore) return restore(d.restore);
  };
}

// ------------------------------------------------------------------ дії
function applyPhrase(res, newFile) {
  S.phrases[S.idx] = res;
  renderCues(); renderCard(newFile); loadCatalogs();
}
async function act(path, body) {
  try { return await post(path, { ...ids(), ...body }); }
  catch (e) { toast(e.message, true); return null; }
}
async function saveText() {
  const ua = $("#ua"), p = cur();
  if (!ua || !p || ua.value.trim() === p.ua) return;
  const idx = S.idx, prev = p.ua;
  const res = await act("/api/text", { text: ua.value });
  if (res && S.idx === idx) { S.phrases[idx] = res; renderCues(); const st = $("#uaState"); if (st) st.textContent = "✓ збережено"; }
  else if (res) S.phrases[idx] = res;
  if (res) setUndo(`Текст змінено`, async () => { const r = await post("/api/text", { cid: S.cat, gid: S.unit, lid: res.id, text: prev }); S.phrases[idx] = r; if (S.idx === idx) renderCard(); renderCues(); });
}
async function approve(file) {
  const prev = cur().approved, idx = S.idx;
  const res = await act("/api/approve", { file, trim: $("#optTrim").checked });
  if (!res) return;
  applyPhrase(res);
  const n = res.takes.find((t) => t.file === file)?.n;
  toast(`Дубль ${n} обрано для гри`, false, 5000, () => undoTo(idx, prev));
}
async function unapprove() {
  const prev = cur().approved, idx = S.idx;
  const res = await act("/api/unapprove", {});
  if (!res) return;
  applyPhrase(res);
  toast("Вибір скасовано — дубль лишився у списку", false, 5000, () => undoTo(idx, prev));
}
async function undoTo(idx, prevApproved) {
  const base = ids(S.phrases[idx]);
  const res = prevApproved
    ? await post("/api/approve", { ...base, file: prevApproved, trim: $("#optTrim").checked })
    : await post("/api/unapprove", base);
  S.phrases[idx] = res; if (S.idx === idx) renderCard(); renderCues(); loadCatalogs();
}
async function del(file) {
  stopPlay();
  const p = cur(), idx = S.idx, wasAppr = p.approved === file;
  const res = await act("/api/delete", { file });
  if (!res) return;
  applyPhrase(res);
  const n = res.takes.find((t) => t.file === file)?.n;
  toast(`Дубль ${n} у кошику${wasAppr ? " (вибір для гри знято)" : ""}`, false, 7000, async () => {
    let r = await post("/api/restore", { ...ids(p), file });
    if (wasAppr) r = await post("/api/approve", { ...ids(p), file, trim: $("#optTrim").checked });
    S.phrases[idx] = r; if (S.idx === idx) renderCard(); renderCues(); loadCatalogs();
  });
}
async function restore(file) {
  const res = await act("/api/restore", { file });
  if (res) { applyPhrase(res, file); toast("Дубль відновлено"); }
}

// ------------------------------------------------------------------ toast + undo
let toastTimer = null;
function setUndo(label, fn) { S.undo = fn ? { label, fn } : null; }
function toast(msg, err = false, ms = 4000, undoFn = null) {
  const t = $("#toast");
  t.className = "toast" + (err ? " err" : "");
  t.innerHTML = `<span>${esc(msg)}</span>` + (undoFn ? `<button id="undoBtn">Скасувати <small>⌘Z</small></button>` : "");
  t.hidden = false;
  if (undoFn) { setUndo(msg, undoFn); $("#undoBtn").onclick = runUndo; }
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
  if (e.target.matches("input, textarea")) return;
  if ((e.metaKey || e.ctrlKey) && e.code === "KeyZ") { e.preventDefault(); return runUndo(); }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.code === "Escape") return toggleUnitPopover(false);
  if (e.code === "Space") { e.preventDefault(); return toggleRec(); }
  if (Rec.on) return;
  const p = cur(); if (!p) return;
  const last = p.takes.filter((t) => !t.deleted && t.exists).slice(-1)[0];
  switch (e.code) {
    case "KeyR": play([{ url: urlRef(p), id: "ref" }]); break;
    case "KeyL": if (last) play([{ url: urlTake(last.file), id: "take:" + last.file }]); break;
    case "KeyB": if (last) play([{ url: urlRef(p), id: "ref" }, { url: urlTake(last.file), id: "take:" + last.file }]); break;
    case "KeyN": nextTodo(); break;
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

for (const id of ["optTrim", "optAutoplay"]) {
  const el = $("#" + id);
  try { const v = localStorage.getItem("studio." + id); if (v !== null) el.checked = v === "1"; } catch {}
  el.onchange = () => { try { localStorage.setItem("studio." + id, el.checked ? "1" : "0"); } catch {} };
}
window.addEventListener("resize", () => waves.forEach((_, id) => drawWave(id)));
window.addEventListener("beforeunload", (e) => { if (Rec.on) { e.preventDefault(); e.returnValue = ""; } });

(async () => {
  S.catalogs = await getJSON("/api/catalogs");
  let pos = null;
  try { pos = JSON.parse(localStorage.getItem("studio.pos") || "null"); } catch {}
  if (!pos || !S.catalogs.some((c) => c.id === pos.cid && c.groups.some((g) => g.id === pos.gid))) {
    const c = S.catalogs[0];
    pos = c && { cid: c.id, gid: c.groups[0]?.id };
  }
  if (pos) await openUnit(pos.cid, pos.gid);
})().catch((e) => { $("#main").innerHTML = `<div class="empty">Помилка: ${esc(e.message)}</div>`; });
