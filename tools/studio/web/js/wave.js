/* Хвилі дублів: межі голосу, малювання, завантаження хвиль картки. */
import { loadBuf } from "./audio.js";
import { S, cur, urlRef, urlTake } from "./state.js";
import { FIT, tempoFmt, tempoOf } from "./tempo.js";
import { AUTO, mountTrim } from "./trim.js";
import { $, fmt } from "./util.js";

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

export const waves = new Map(); // id -> {canvas, buf, opts}
/** Малює хвилю; після першого малювання клас .ready знімає opacity:0 (CSS-перехід появи). */
export function drawWave(id, ...a) {
  paintWave(id, ...a);
  waves.get(id)?.canvas.classList.add("ready");
}

function paintWave(id, progress = -1) {
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

export async function loadWaves(p) {
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

function autoDim(cv, title) {
  const d = document.createElement("div"); d.className = "auto-dim"; d.title = title; cv.parentElement.appendChild(d); return d;
}

export function fitInfo(voiceDur, ref) {
  if (!ref) return { cls: "", text: fmt(voiceDur) };
  const d = voiceDur - ref, r = voiceDur / ref;
  return { cls: r <= 1.1 ? "good" : r <= 1.3 ? "long" : "bad", text: `голос ${fmt(voiceDur)} · ${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(2)} с` };
}
