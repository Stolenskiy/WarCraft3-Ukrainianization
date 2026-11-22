/* Черга ШІ: компактний індикатор у шапці («ШІ: 1 генерує · 2 у черзі» + смуга), список завдань зі «Скасувати», тост по завершенню.
   Опитує /api/ai/events (раз на 1 с, поки є активні, інакше рідше) і /api/ai/jobs; UI не блокується. Новий варіант поточної репліки
   з’являється в списку, щойно завдання змінило стан (`onLine` — реєструє ai.js). */
import { getJSON, post } from "./api.js";
import { S } from "./state.js";
import { toast } from "./toast.js";
import { $, esc } from "./util.js";

const Q = { jobs: [], prev: new Map(), last: 0, timer: null, ready: false, onLine: () => {} };
const active = () => Q.jobs.filter((j) => j.state === "queued" || j.state === "running");

export const onLine = (fn) => { Q.onLine = fn; };

const label = (j) => `${j.lid.replace(/\.wav$/, "")} · ${j.params.n} ${j.params.n === 1 ? "варіант" : "варіанти"}`;
const phaseUa = { queued: "у черзі", generating: "генерація", metrics: "метрики" };

function render() {
  const box = $("#aiQueue"), act = active(), run = act.filter((j) => j.state === "running"), wait = act.length - run.length;
  box.hidden = !act.length;
  if (!act.length) { $("#aiQueuePop").hidden = true; return; }
  const j = run[0], pr = j && j.progress, pct = pr && pr.total ? Math.round(100 * pr.done / pr.total) : 0;
  $("#aiQueueTxt").textContent = `ШІ: ${run.length ? `${run.length} генерує` : ""}${run.length && wait ? " · " : ""}${wait ? `${wait} у черзі` : ""}`;
  $("#aiQueueBar").style.width = `${pct}%`;
  $("#aiQueuePop").innerHTML = act.map((x) => `<div class="aiq-job" data-job="${esc(x.id)}"><span><b>${esc(label(x))}</b><br><small>${esc(x.engine)} · ${esc(phaseUa[x.progress.phase] || x.state)}
    ${x.progress.total ? ` · ${x.progress.done}/${x.progress.total}` : ""}</small></span><button class="ghost" data-cancel="${esc(x.id)}" title="Скасувати завдання">Скасувати</button></div>`).join("");
}

function finished(j, was) {
  if (was === j.state) return;
  if (j.state === "done") toast(`ШІ: готово — ${label(j)} (${j.license})`, false, 6000);
  else if (j.state === "failed") toast(`ШІ: не вдалося — ${j.error || "помилка двигуна"}`, true, 10000);
  else if (j.state === "cancelled") toast("ШІ: завдання скасовано");
}

async function refresh() {
  Q.jobs = await getJSON("/api/ai/jobs");
  let touched = false;
  for (const j of Q.jobs) {
    const was = Q.prev.get(j.id), sig = `${j.state}:${j.progress.done}:${j.progress.phase}`;
    if (Q.ready) finished(j, was ? was.state : "queued");   // нове після старту — теж «було в черзі» (встигло завершитись між опитуваннями)
    if (Q.ready && (!was || was.sig !== sig) && j.cid === S.cat && j.gid === S.unit) touched = true;
    Q.prev.set(j.id, { state: j.state, sig });
  }
  Q.ready = true;
  render();
  if (touched) Q.onLine();
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
$("#aiQueuePop").onclick = async (e) => {
  const b = e.target.closest("[data-cancel]");
  if (!b) return;
  b.disabled = true;
  try { await post("/api/ai/cancel", { id: b.dataset.cancel }); } catch (er) { toast(er.message, true); }
  kick();
};
document.addEventListener("click", (e) => { if (!e.target.closest("#aiQueue")) $("#aiQueuePop").hidden = true; });

tick();
