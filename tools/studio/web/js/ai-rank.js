/* ШІ: автотривалість і автовибір — оцінка й рейтинг варіантів (бейдж «найкращий»), темп під довжину оригіналу, «★ Обрати найкращий для гри».
   Дані — із сервера (studio/aifit.py): v.score 0–100, v.score_parts, v.rank, v.best, v.fit {target, need, tempo, after, fits, short, note}.
   Хуки в ai.js: rankHtml(v) у рядку варіанта, autoBar(p) + bindAuto(p, host) над списком, fitOn() для «Взяти в дублі»; autoPickOn() — ai-gen.js. */
import { act, putPhrase } from "./phrase.js";
import { ids } from "./state.js";
import { toast } from "./toast.js";
import { esc } from "./util.js";

const KEY_FIT = "studio.aiFit", KEY_PICK = "studio.aiAutoPick";
const load = (k, def) => { try { const v = localStorage.getItem(k); return v == null ? def : v === "1"; } catch { return def; } };
const save = (k, on) => { try { localStorage.setItem(k, on ? "1" : "0"); } catch { /* приватний режим — лише до перезавантаження */ } };
/** «Взяти в дублі» ставить темп під оригінал (типово так). */
export const fitOn = () => load(KEY_FIT, true);
/** Після генерації найкращий варіант сам іде в гру (типово ні). */
export const autoPickOn = () => load(KEY_PICK, false);

const PART_UA = { cer: "розбірливість", similarity: "схожість голосу", dur: "тривалість", clip: "без перевантаження" };
const pct = (x) => `${Math.round(x * 100)}%`;
const x2 = (x) => `×${(+x).toFixed(2)}`;

/** Чому автовибір недоступний ("" — доступний). Живий запис завжди має пріоритет. */
export function pickBlock(p) {
  const appr = p.takes.find((t) => t.file === p.approved);
  if (appr && appr.source !== "ai") return `для гри обрано живий дубль ${appr.n} — він має пріоритет над ШІ`;
  if (p.original) return "для гри залишено оригінал — автовибір його не замінює";
  if (!p.ai.some((v) => v.score != null)) return "варіанти ще не оцінено";
  return "";
}

function fitHtml(v) {
  const f = v.fit;
  if (!f) return "";
  const cls = !f.fits ? "bad" : f.tempo !== 1 ? "long" : "good";
  const txt = !f.fits ? `не влазить: треба ${x2(f.need)}` : f.tempo === 1 ? "як оригінал" : `темп ${x2(f.tempo)}`;
  return `<span class="ai-fit ${cls}" title="Автотривалість: ${esc(f.note)}">⏱ ${txt}</span>`;
}

/** Бейджі рядка варіанта: тривалість відносно оригіналу, місце й оцінка, «найкращий». */
export function rankHtml(v) {
  if (v.score == null) return fitHtml(v);
  const why = Object.entries(v.score_parts || {}).map(([k, x]) => `${PART_UA[k] || k} ${pct(x)}`).join(" · ");
  return `${fitHtml(v)}<span class="ai-score" title="Оцінка для автовибору 0–100 — ${esc(why)}">№${v.rank} · ${v.score}</span>${
    v.best ? `<span class="ai-best" title="Найвища оцінка серед показаних варіантів">★ найкращий</span>` : ""}`;
}

/** Панель над списком варіантів: автотривалість, автовибір після генерації, «★ Обрати найкращий для гри». */
export function autoBar(p) {
  const why = pickBlock(p), top = p.ai.find((v) => v.rank === 1);
  return `<label title="«Взяти в дублі» поставить новому дублю темп під довжину голосу оригіналу (×0.80–×1.25, висота голосу та сама); файл варіанта не змінюється">
      <input type="checkbox" data-ai-fit ${fitOn() ? "checked" : ""}> Автотривалість</label>
    <label title="Коли генерація завершиться, найкращий її варіант сам стане дублем «ШІ» і піде в гру — лише якщо для гри не обрано живий дубль">
      <input type="checkbox" data-ai-autopick ${autoPickOn() ? "checked" : ""}> Обирати найкращий автоматично</label>
    ${p.ai.length ? `<button class="btn" data-ai-pick ${why ? "disabled" : ""} title="${esc(why || `Варіант ${top.n} (оцінка ${top.score}) → дубль «ШІ» → у гру`)}">★ Обрати найкращий для гри</button>
    ${why ? `<span class="ai-note" data-ai-pick-why>${esc(why)}</span>` : ""}` : ""}`;
}

export async function pickBest(p) {
  const where = ids(p), res = await act("/api/ai/auto-pick", { lid: p.id, fit: fitOn() });
  if (!res) return;
  const k = res.picked, t = res.takes.find((x) => x.file === k.take), v = res.ai.find((x) => x.file === k.file);
  putPhrase(where, res, k.take);
  toast(`У грі — ШІ-варіант ${v ? v.n : "?"} (оцінка ${k.score}) як Дубль ${t ? t.n : "?"}${k.tempo !== 1 ? `, темп ${x2(k.tempo)}` : ""} · позначка «ШІ»`, false, 6000);
}

export function bindAuto(p, host) {
  host.onchange = (e) => {
    const d = e.target.dataset;
    if ("aiFit" in d) save(KEY_FIT, e.target.checked);
    if ("aiAutopick" in d) save(KEY_PICK, e.target.checked);
  };
  host.onclick = (e) => {
    if (!e.target.closest("[data-ai-pick]")) return;
    e.stopPropagation();
    pickBest(p);
  };
}
