/* Запис з мікрофона (AudioWorklet, передзапис, метр, кодування WAV). */
import { post } from "./api.js";
import { AC, play, stopPlay } from "./audio.js";
import { renderCard } from "./card.js";
import { CLIP_ADVICE, clipCheck } from "./clip.js";
import { putPhrase } from "./phrase.js";
import { S, cur, ids } from "./state.js";
import { toast } from "./toast.js";
import { takeItem } from "./trim.js";
import { $, esc, fmt } from "./util.js";

export const MAX_REC = 30;

// Джерело звуку обирає користувач (#micSel, localStorage "studio.mic"); "" = системний за замовчуванням.
export const Rec = { node: null, analyser: null, stream: null, src: null, label: "", worklet: false, meter: false,
  on: false, chunks: [], pre: [], t0: 0, sr: 48000, devices: [] };

let micId = ""; try { micId = localStorage.getItem("studio.mic") || ""; } catch {}

const MIC_OPTS = { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 };

async function refreshMics() {
  try { Rec.devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audioinput" && d.deviceId !== "default"); }
  catch { Rec.devices = []; }
  renderMicSel();
}

export function renderMicSel() {
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

export async function switchMic(id) {
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

export async function toggleRec() { if (Rec.on) await stopRec(); else await startRec(); }

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

export function setRecUI(on) {
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

refreshMics();
