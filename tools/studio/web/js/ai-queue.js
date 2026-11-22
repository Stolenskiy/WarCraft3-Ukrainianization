/* Черга ШІ: компактний індикатор у шапці («ШІ: 1 генерує · 2 у черзі» + смуга), список завдань зі «Скасувати», тост по завершенню.
   Опитує /api/ai/events (раз на 1 с, поки є активні, інакше рідше) і /api/ai/jobs; UI не блокується. Новий варіант поточної репліки
   з’являється в списку, щойно завдання змінило стан (`onLine` — реєструє ai.js). */
import { getJSON, post } from "./api.js";
import { S } from "./state.js";
import { toast } from "./toast.js";
import { $, esc } from "./util.js";

const Q = { jobs: [], at: Date.now(), prev: new Map(), last: 0, timer: null, ready: false, onLine: () => {}, subs: [] };
const MAX_ROWS = 12;                                     // ШІ-чернетка раси — сотні завдань: решта — одним рядком
const active = () => Q.jobs.filter((j) => j.state === "queued" || j.state === "running");

export const onLine = (fn) => { Q.onLine = fn; };
/** Після кожного оновлення списку завдань: fn(jobs, prev) — prev: Map id → {state} до оновлення (ai-draft.js). */
export const onJobs = (fn) => { Q.subs.push(fn); };

const label = (j) => `${j.draft ? "чернетка · " : ""}${j.lid.replace(/\.wav$/, "")} · ${j.params.n} ${j.params.n === 1 ? "варіант" : "варіанти"}`;
const phaseUa = { queued: "у черзі", loading: "завантаження моделі", generating: "генерація", metrics: "перевірка (розпізнавання)" };

/** «≈ 1 хв 05 с» / «≈ 40 с» / «ще трохи…» (оцінка вичерпалась, а двигун ще працює). */
export const leftUa = (s) => (s == null ? "" : s <= 0 ? "ще трохи…" : s < 60 ? `≈ ${Math.ceil(s)} с` : `≈ ${Math.floor(s / 60)} хв ${String(Math.round(s % 60)).padStart(2, "0")} с`);
/** Частка виконання завдання 0…1 за оцінкою сервера (eta.total — усе завдання, left − ahead — що лишилось саме йому). */
const frac = (j) => (j.state !== "running" || !j.eta ? 0 : Math.min(0.97, Math.max(j.progress.done / (j.progress.total || 1) * 0.9, 1 - (j.eta.left - j.eta.ahead) / (j.eta.total || 1))));
const leftOf = (j) => (j.eta ? j.eta.left - (Date.now() - Q.at) / 1000 : null);
const stepUa = (j) => {
  const pr = j.progress;
  if (j.state === "queued") return j.eta && j.eta.ahead ? `у черзі — спершу інші завдання (${leftUa(j.eta.ahead)})` : "у черзі";
  if (pr.phase === "generating") return `генерую варіант ${Math.min(pr.done + 1, pr.total)} з ${pr.total}`;
  return phaseUa[pr.phase] || j.state;
};
const bar = (j, cls = "") => `<i class="aiq-bar ${cls}"><b style="width:${Math.round(100 * frac(j))}%"></b></i>`;

/** Прогрес генерації поточної репліки — над панеллю «✨ Згенерувати» (#aiLineProg[data-lid]). */
function renderLine() {
  const el = document.querySelector("#aiLineProg");
  if (!el) return;
  const mine = active().filter((j) => j.cid === S.cat && j.gid === S.unit && j.lid === el.dataset.lid);
  el.hidden = !mine.length;
  el.innerHTML = mine.map((j) => `<div class="aip" data-job="${esc(j.id)}" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(100 * frac(j))}">
    <div class="aip-top"><b>✨ ${esc(stepUa(j))}</b><span class="aip-left">${esc(leftUa(leftOf(j)))}</span>
    <button class="ghost" data-cancel="${esc(j.id)}" title="Скасувати завдання">Скасувати</button></div>${bar(j, "big")}
    <small>${j.params.n} ${j.params.n === 1 ? "варіант" : "варіанти"} · ${esc(j.engine)} · час — оцінка за попередніми генераціями</small></div>`).join("");
}

export function render() {
  const box = $("#aiQueue"), act = active(), run = act.filter((j) => j.state === "running"), wait = act.length - run.length;
  box.hidden = !act.length;
  renderLine();
  if (!act.length) { $("#aiQueuePop").hidden = true; return; }
  const last = act.reduce((m, j) => Math.max(m, leftOf(j) ?? 0), 0);
  $("#aiQueueTxt").textContent = `ШІ: ${run.length ? `${run.length} генерує` : ""}${run.length && wait ? " · " : ""}${wait ? `${wait} у черзі` : ""} · ${leftUa(last)}`;
  $("#aiQueueBar").style.width = `${Math.round(100 * (run[0] ? frac(run[0]) : 0))}%`;
  const drafts = act.filter((j) => j.draft).length, more = act.length - MAX_ROWS;
  $("#aiQueuePop").innerHTML = act.slice(0, MAX_ROWS).map((x) => `<div class="aiq-job" data-job="${esc(x.id)}"><span><b>${esc(label(x))}</b><br><small>${esc(x.engine)} · ${esc(stepUa(x))}
    · ${esc(leftUa(leftOf(x)))}</small>${bar(x)}</span><button class="ghost" data-cancel="${esc(x.id)}" title="Скасувати завдання">Скасувати</button></div>`).join("")
    + (more > 0 ? `<p class="aiq-more">… і ще ${more} у черзі · усе разом ${esc(leftUa(last))}</p>` : "")
    + (drafts ? `<button class="ghost aiq-draft-cancel" data-draft-cancel title="Зупинити всі завдання ШІ-чернетки (готові варіанти лишаються)">Скасувати всю ШІ-чернетку · ${drafts}</button>` : "");
}

function finished(j, was) {
  if (was === j.state || j.draft) return;               // чернетка: один підсумковий тост на пакет (ai-draft.js)
  if (j.state === "done") toast(`ШІ: готово — ${label(j)} (${j.license})`, false, 6000);
  else if (j.state === "failed") toast(`ШІ: не вдалося — ${j.error || "помилка двигуна"}`, true, 10000);
  else if (j.state === "cancelled") toast("ШІ: завдання скасовано");
}

async function refresh() {
  Q.jobs = await getJSON("/api/ai/jobs");
  Q.at = Date.now();
  let touched = false;
  const before = new Map(Q.prev);
  for (const j of Q.jobs) {
    const was = Q.prev.get(j.id), sig = `${j.state}:${j.progress.done}:${j.progress.phase}`;
    if (Q.ready) finished(j, was ? was.state : "queued");   // нове після старту — теж «було в черзі» (встигло завершитись між опитуваннями)
    if (Q.ready && (!was || was.sig !== sig) && j.cid === S.cat && j.gid === S.unit) touched = true;
    Q.prev.set(j.id, { state: j.state, sig });
  }
  Q.ready = true;
  render();
  if (touched) Q.onLine();
  Q.subs.forEach((fn) => fn(Q.jobs, before));
}

async function tick() {
  clearTimeout(Q.timer);
  try {
    const ev = await getJSON(`/api/ai/events?after=${Q.last}`);
    if (ev.length) Q.last = ev[ev.length - 1].id;
    if (ev.length || active().length || !Q.ready) await refresh();
  } catch { /* студія перезапускається — спробуємо ще */ }
  Q.timer = setTimeout(tick, active().length ? 1000 : 3000);
}

/** Після постановки завдання — одразу оновити (не чекати наступного опитування). */
export function kick() { clearTimeout(Q.timer); Q.timer = setTimeout(tick, 50); }

$("#aiQueueBtn").onclick = () => { const p = $("#aiQueuePop"); p.hidden = !p.hidden; };
document.addEventListener("click", async (e) => {      // «Скасувати» — у спливному списку черги і в прогресі репліки
  const b = e.target.closest("#aiQueuePop [data-cancel], #aiLineProg [data-cancel], [data-draft-cancel]");
  if (!b) return;
  b.disabled = true;
  try {
    if (b.dataset.cancel) await post("/api/ai/cancel", { id: b.dataset.cancel });
    else toast(`ШІ-чернетку зупинено: скасовано завдань ${(await post("/api/ai/draft/cancel", {})).cancelled}`);
  } catch (er) { toast(er.message, true); }
  kick();
});
document.addEventListener("click", (e) => { if (!e.target.closest("#aiQueue")) $("#aiQueuePop").hidden = true; });

tick();
