/* ШІ-очищення запису (Sidon, MIT, локально): «✨ Очистити» на дублі, масове очищення у вкладці «Обробка», прогрес і оцінка часу.
   Результат — НОВИЙ дубль «очищено ← N» (оригінал лишається); «Було → стало» порівнює їх. Опитує /api/enhance/jobs, поки є активні. */
import { getJSON, post } from "./api.js";
import { leftUa } from "./ai-queue.js";
import { renderCard } from "./card.js";
import { renderCues } from "./cues.js";
import { Rec } from "./rec.js";
import { S, cur } from "./state.js";
import { showTab } from "./tabs.js";
import { toast } from "./toast.js";
import { $, esc } from "./util.js";

const E = { st: null, jobs: [], at: Date.now(), timer: null, pending: null, seen: new Map(), dirty: false };
const active = () => E.jobs.filter((j) => j.state === "queued" || j.state === "running");
const own = (t) => t && !t.deleted && t.exists !== false && t.source !== "ai" && t.source !== "enhanced";
const cleaned = (p, file) => p.takes.some((t) => !t.deleted && t.enhanced_from === file);
const item = (p, file) => ({ cid: S.cat, gid: S.unit, lid: p.id, file });
export const takeNo = (file) => +(/\.take(\d+)\.wav$/.exec(file || "") || [])[1] || "?";

/** Що очищати в поточному юніті: обрані для гри власні дублі / останній дубль реплік без обраного. Уже очищені — пропуск. */
function scope() {
  const appr = [], latest = [];
  for (const p of S.phrases || []) {
    const a = p.takes.find((t) => t.file === p.approved);
    if (a) { if (own(a) && !cleaned(p, a.file)) appr.push(item(p, a.file)); continue; }
    const last = [...p.takes].reverse().find(own);
    if (last && !cleaned(p, last.file)) latest.push(item(p, last.file));
  }
  return { appr, latest };
}

const stepUa = (j) => {
  if (j.state === "queued") return j.eta && j.eta.ahead ? `у черзі (${leftUa(j.eta.ahead)})` : "у черзі";
  if (j.kind === "setup") return `встановлення${j.message ? `: ${j.message}` : "…"}`;
  if (j.phase === "loading") return "запуск моделі";
  return `очищую ${Math.min(j.done + 1, j.total)} з ${j.total}`;
};
const frac = (j) => (j.state !== "running" || !j.eta ? 0 : Math.min(0.97, Math.max(j.done / (j.total || 1), 1 - (j.eta.left - j.eta.ahead) / (j.eta.total || 1))));
const left = (j) => (j.eta ? j.eta.left - (Date.now() - E.at) / 1000 : null);
const prog = (j) => `<div class="aip enh-p" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(100 * frac(j))}">
  <div class="aip-top"><b>✨ ${esc(stepUa(j))}</b><span class="aip-left">${esc(leftUa(left(j)))}</span>
  <button class="ghost" data-enh-cancel="${esc(j.id)}">Скасувати</button></div>
  <i class="aiq-bar big"><b style="width:${Math.round(100 * frac(j))}%"></b></i></div>`;

function renderBox() {
  const box = $("#enhBox");
  if (!box || !E.st) return;
  const st = E.st, act = active(), setup = act.find((j) => j.kind === "setup"), { appr, latest } = scope();
  const keep = $("#enhApprove") ? $("#enhApprove").checked : true;
  box.innerHTML = `<h3>✨ ШІ-очищення запису</h3>
    <p class="opts-note">Прибирає луну кімнати й шум, робить голос ближчим і гучнішим. Створює <b>новий</b> дубль «очищено» — оригінал
      лишається: порівняйте («Було → стало») і оберіть кращий. ${esc(st.title)} · <a href="${esc(st.license_url)}" target="_blank" rel="noopener">${esc(st.license)}</a> · локально, ≈ 1 с на дубль.</p>
    ${st.state !== "ready" ? `<p class="enh-miss">Не встановлено${setup ? "" : ` <small>(${esc(st.detail)})</small>`}.</p>
      ${setup ? "" : `<button class="btn primary" id="enhSetup">Встановити (≈ ${st.download_mb} МБ)</button>`}`
    : `<label class="switch" title="Якщо очищаємо дубль, обраний для гри, — обрати очищений замість нього (повернути можна кнопкою «Обрати» на старому)">
        <input type="checkbox" id="enhApprove" ${keep ? "checked" : ""}><span></span>Очищені — одразу в гру</label>
      <button class="btn" id="enhAppr" ${appr.length ? "" : "disabled"}>Очистити обрані для гри · ${appr.length}</button>
      <button class="btn quiet" id="enhLatest" ${latest.length ? "" : "disabled"} title="Репліки без обраного дубля: очистити останній записаний">Очистити останні дублі (без обраного) · ${latest.length}</button>`}
    <div class="enh-progs">${act.map(prog).join("")}</div>`;
}

function renderLine() {
  const el = $("#enhLineProg"), p = cur();
  if (!el || !p) return;
  const key = `${S.cat}/${S.unit}/${p.id}`, mine = active().filter((j) => (j.keys || []).includes(key));
  el.hidden = !mine.length;
  el.innerHTML = mine.map(prog).join("");
}

function render() { renderBox(); renderLine(); }

/** Підтягнути змінені репліки поточного юніта (нові дублі «очищено») — не під час запису. */
async function refreshUnit() {
  if (Rec.on) { E.dirty = true; return; }
  E.dirty = false;
  const cid = S.cat, gid = S.unit;
  try {
    const g = await getJSON(`/api/group/${cid}/${gid}`);
    if (cid !== S.cat || gid !== S.unit) return;
    const sig = (p) => JSON.stringify(p.takes.map((t) => [t.file, t.deleted]).concat([p.approved]));
    const curId = cur()?.id;
    let card = false;
    for (const ln of g.lines) {
      const i = S.phrases.findIndex((x) => x.id === ln.id);
      if (i < 0 || sig(S.phrases[i]) === sig(ln)) continue;
      S.phrases[i] = ln;
      card ||= ln.id === curId;
    }
    renderCues();
    if (card) renderCard();
    render();
  } catch (e) { console.warn("enhance refresh", e); }
}

function finished(j, was) {
  if (was === j.state || !was) return;
  if (j.kind === "setup") {
    if (j.state === "done") {
      if (!E.pending) return toast("ШІ-очищення встановлено");
      const pd = E.pending;
      E.pending = null;
      enhanceTakes(pd.items, pd.approve, "ШІ-очищення встановлено. ");
    }
    else if (j.state === "failed") toast(`Не вдалося встановити: ${j.error}`, true, 12000);
    return;
  }
  const ok = j.results.filter((r) => !r.error), bad = j.results.filter((r) => r.error);
  if (j.state === "done" || j.state === "cancelled") {
    const gain = ok.length ? Math.round(ok.reduce((s, r) => s + r.gain_db, 0) / ok.length) : 0;
    toast(`${j.state === "cancelled" ? "Зупинено. " : ""}Очищено дублів: ${ok.length}${ok.length ? ` (гучність ${gain >= 0 ? "+" : ""}${gain} дБ)` : ""}`
      + (ok.some((r) => r.approved) ? ` · у гру: ${ok.filter((r) => r.approved).length}` : "") + (bad.length ? ` · помилок: ${bad.length}` : ""), !!bad.length && !ok.length, 7000);
  } else if (j.state === "failed") toast(`ШІ-очищення: ${j.error}`, true, 12000);
}

async function tick() {
  clearTimeout(E.timer);
  try {
    const jobs = await getJSON("/api/enhance/jobs");
    E.at = Date.now();
    let changed = false;
    for (const j of jobs) {
      const was = E.seen.get(j.id);
      if (!was || was.done !== j.done || was.state !== j.state) changed ||= j.kind === "clean" && (j.keys || []).some((k) => k.startsWith(`${S.cat}/${S.unit}/`));
      finished(j, was && was.state);
      E.seen.set(j.id, { state: j.state, done: j.done });
    }
    E.jobs = jobs;
    if (jobs.some((j) => j.kind === "setup" && j.state === "done") && E.st && E.st.state !== "ready") E.st = await getJSON("/api/enhance/status");
    if (changed || (E.dirty && !Rec.on)) await refreshUnit();
  } catch { /* студія перезапускається */ }
  render();
  if (active().length) E.timer = setTimeout(tick, 700);
}

export async function enhanceTakes(items, approve = false, note = "") {
  try {
    if (!E.st || E.st.state !== "ready") E.st = await getJSON("/api/enhance/status");
    if (E.st.state !== "ready") {
      E.pending = { items, approve };
      showTab("Proc"); render();
      $("#enhBox")?.scrollIntoView({ block: "nearest" });
      toast("Спершу встановіть ШІ-очищення (одна кнопка у вкладці «Обробка») — потім очищення почнеться саме");
      return;
    }
    const j = await post("/api/enhance", { items, approve });
    E.seen.set(j.id, { state: j.state, done: 0 });
    toast(`${note}${note ? "Очищення" : "ШІ-очищення"}: ${items.length} ${items.length === 1 ? "дубль" : "дублів"} у черзі`);
    tick();
  } catch (e) { toast(e.message, true); }
}

document.addEventListener("click", async (e) => {
  const b = e.target.closest("#enhSetup, #enhAppr, #enhLatest, [data-enh-cancel]");
  if (!b) return;
  if (b.dataset.enhCancel) { b.disabled = true; try { await post("/api/enhance/cancel", { id: b.dataset.enhCancel }); } catch (er) { toast(er.message, true); } return tick(); }
  if (b.id === "enhSetup") {
    b.disabled = true;
    try { const j = await post("/api/enhance/setup", {}); E.seen.set(j.id, { state: "queued", done: 0 }); } catch (er) { toast(er.message, true); }
    return tick();
  }
  const { appr, latest } = scope();
  enhanceTakes(b.id === "enhAppr" ? appr : latest, b.id === "enhAppr" && $("#enhApprove").checked);
});

/** Після відкриття юніта / перемальовки картки: оновити секцію й прогрес репліки. */
export function enhanceSync() { render(); }

getJSON("/api/enhance/status").then((st) => { E.st = st; E.jobs = st.jobs; E.at = Date.now(); for (const j of st.jobs) E.seen.set(j.id, { state: j.state, done: j.done }); render(); if (active().length) tick(); })
  .catch(() => {});
