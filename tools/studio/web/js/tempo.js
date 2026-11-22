/* Темп дубля (atempo) і підгонка під довжину оригіналу. */
import { post } from "./api.js";
import { renderCard } from "./card.js";
import { step } from "./cues.js";
import { putPhrase } from "./phrase.js";
import { S, ids } from "./state.js";
import { toast } from "./toast.js";
import { esc } from "./util.js";

const TEMPO_MIN = 0.8, TEMPO_MAX = 1.3;

export const FIT = new Map();                                   // файл дубля → {voice, refVoice} без темпу (заповнює refit)

export const tempoOf = (p, file) => p.takes.find((t) => t.file === file)?.tempo || 1;

export const tempoFmt = (x) => `×${(+x).toFixed(2)}`;

export const tempoBadge = (t) => (Math.abs((t.tempo || 1) - 1) > 0.0005 ? `<span class="tempo-t" title="Темп дубля: прискорення без зміни висоти">${tempoFmt(t.tempo)}</span>` : "");

export function tempoPanel(t) {
  const v = t.tempo || 1;
  return `<div class="tempo-pop" data-tempo-pop="${esc(t.file)}" ${S.tempoOpen === t.file ? "" : "hidden"}>
    <label>Темп <input type="range" min="${TEMPO_MIN}" max="${TEMPO_MAX}" step="0.01" value="${v}" data-tempo-range="${esc(t.file)}"><b data-tempo-val>${tempoFmt(v)}</b></label>
    <button class="btn" data-tempo-fit="${esc(t.file)}" title="Темп = голос / голос оригіналу (1.0–1.3)">Під довжину оригіналу</button>
    <button class="linkish" data-tempo-reset="${esc(t.file)}">Скинути</button></div>`;
}

export const tempoLabel = (r) => { const b = r.parentElement.querySelector("[data-tempo-val]"); if (b) b.textContent = tempoFmt(r.value); };

export function tempoClick(p, d) {
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

export async function saveTempo(where, file, prev, tempo) {
  let res;
  try { res = await post("/api/tempo", { ...where, file, tempo }); }
  catch (e) { toast(e.message, true); if (where.cid === S.cat && where.gid === S.unit) renderCard(); return; }
  putPhrase(where, res);
  const n = res.takes.find((t) => t.file === file)?.n, none = tempo == null || Math.abs(tempo - 1) < 0.0005;
  toast(none ? `Темп дубля ${n} скинуто` : `Дубль ${n} прискорено ${tempoFmt(tempo)}`, false, 5000, async () =>
    putPhrase(where, await post("/api/tempo", { ...where, file, tempo: prev > 1.0005 || prev < 0.9995 ? prev : null })));
}
