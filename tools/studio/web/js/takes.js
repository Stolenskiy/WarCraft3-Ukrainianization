/* Дії над дублями й оригіналом: обрати, зняти, кошик, відновити, undo. */
import { post } from "./api.js";
import { stopPlay } from "./audio.js";
import { act, putPhrase } from "./phrase.js";
import { cur, ids, refLang } from "./state.js";
import { toast } from "./toast.js";

export async function approve(file) {
  const where = ids(), prev = cur().approved;
  const res = await act("/api/approve", { file });
  if (!res) return;
  putPhrase(where, res);
  const n = res.takes.find((t) => t.file === file)?.n;
  toast(`Дубль ${n} обрано для гри`, false, 5000, () => undoTo(where, prev));
}

export async function unapprove() {
  const where = ids(), prev = cur().approved;
  const res = await act("/api/unapprove", {});
  if (!res) return;
  putPhrase(where, res);
  toast("Вибір скасовано — дубль лишився у списку", false, 5000, () => undoTo(where, prev));
}

// «Залишити оригінал»: у гру йде необроблений оригінал у вибраній мові; взаємовиключно з обраним дублем
export async function keepOriginal(p) {
  const where = ids(), prev = { approved: p.approved, original: p.original }, lang = refLang(p);
  const res = await act("/api/original", { lid: p.id, lang });
  if (!res) return;
  putPhrase(where, res);
  toast(`Залишено оригінал (${lang.toUpperCase()}) — переозвучення не потрібне`, false, 5000, () => undoOriginal(where, p.id, prev));
}

export async function clearOriginal() {
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

async function delTake(file) {
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

export async function restore(file) {
  const where = ids();
  const res = await act("/api/restore", { file });
  if (res) { putPhrase(where, res, file); toast("Дубль відновлено"); }
}

/** Видалення в кошик: картка коротко згасає перед перемальовкою (лише презентація). */
export async function del(file) {
  const row = document.querySelector(`[data-del="${CSS.escape(file)}"]`)?.closest(".take");
  if (row && !matchMedia("(prefers-reduced-motion: reduce)").matches) { row.classList.add("leaving"); await new Promise((r) => setTimeout(r, 160)); }
  try { return await delTake(file); } finally { row?.classList.remove("leaving"); }
}
