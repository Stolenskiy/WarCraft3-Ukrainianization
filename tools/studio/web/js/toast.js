/* Тост і ⌘Z (undo). */
import { S } from "./state.js";
import { $, esc } from "./util.js";

// ⌘Z діє лише поки видно підказку (або кілька секунд після зміни тексту) — не «через хвилини».
let toastTimer = null, undoTimer = null;

export function setUndo(label, fn, ms = 7000) {
  S.undo = fn ? { label, fn } : null;
  clearTimeout(undoTimer);
  if (fn) undoTimer = setTimeout(() => { S.undo = null; }, ms);
}

export function toast(msg, err = false, ms = 4000, undoFn = null) {
  const t = $("#toast");
  t.className = "toast" + (err ? " err" : "");
  t.innerHTML = `<span>${esc(msg)}</span>` + (undoFn ? `<button id="undoBtn">Скасувати <small>⌘Z</small></button>` : "");
  t.hidden = false;
  if (undoFn) { setUndo(msg, undoFn, ms); $("#undoBtn").onclick = runUndo; }
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, ms);
}

export async function runUndo() {
  if (!S.undo) return;
  const u = S.undo; S.undo = null; $("#toast").hidden = true;
  try { await u.fn(); toast("Скасовано"); } catch (e) { toast("Не вдалося скасувати: " + e.message, true); }
}
