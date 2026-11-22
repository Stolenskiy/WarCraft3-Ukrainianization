/* Ручне обрізання дубля (ручки на хвилі). */
import { post } from "./api.js";
import { play } from "./audio.js";
import { renderCard } from "./card.js";
import { putPhrase } from "./phrase.js";
import { S, ids, urlTake } from "./state.js";
import { toast } from "./toast.js";
import { $, esc } from "./util.js";

// Файл дубля не змінюється: сервер зберігає {start, end} і застосовує їх при копіюванні в гру.
const MIN_TRIM = 0.25; // = MIN_TAKE_SEC на сервері

const trimOf = (p, file) => p.takes.find((t) => t.file === file)?.trim || null;

// Межі голосу дубля (voiceSpan, той самий поріг, що в ffmpeg) — заповнюється при малюванні хвиль.
export const AUTO = new Map();

/** Межі без ручного обрізання: з «Обрізати тишу» — краї голосу (те, що й так піде в гру), інакше весь файл. */
const autoEdges = (file, dur) => ($("#optTrim")?.checked && AUTO.has(file) ? { start: AUTO.get(file)[0], end: AUTO.get(file)[1] } : { start: 0, end: dur });

/** Що звучить у грі: ручне обрізання, інакше авто-межі (якщо їх уже пораховано). */
const effTrim = (p, file) => trimOf(p, file) || (AUTO.has(file) && $("#optTrim")?.checked ? autoEdges(file, 0) : null);

/** Елемент для play(): дубль звучить так, як піде в гру (у межах обрізання). */
export const takeItem = (p, file) => { const tr = effTrim(p, file); return { url: urlTake(file), id: "take:" + file, ...(tr ? { start: tr.start, end: tr.end } : {}) }; };

const trimFmt = (a, b) => `${a.toFixed(2)}–${b.toFixed(2)} с`;

export function mountTrim(p, t, dur, scale, onChange = () => {}) {
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

export function resetTrim(p, file) {
  saveTrim(ids(p), file, trimOf(p, file), null, null);
}
