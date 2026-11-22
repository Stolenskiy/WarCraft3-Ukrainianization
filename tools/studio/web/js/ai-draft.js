/* ШІ-чернетка юніта / раси одним кліком: ШІ-заглушки (власний голос) для реплік без вашого дубля й без ШІ-варіанта;
   прогрес «живі / ШІ / оригінал» — у шапці юніта, у бічній панелі й у меню юнітів. Черга, оцінка часу й скасування — ai-queue.js.
   API: GET /api/ai/draft (план), POST /api/ai/draft, /api/ai/draft/cancel; mix — у /api/catalogs. */
import { SETUP_CMD, ensureConsents, fixHint } from "./ai-engine.js";
import { kick, leftUa, onJobs } from "./ai-queue.js";
import { AIS, curEngine, loadStatus, shortLic } from "./ai-state.js";
import { getJSON, post } from "./api.js";
import { loadCatalogs } from "./catalog.js";
import { renderCard } from "./card.js";
import { renderCues } from "./cues.js";
import { Rec } from "./rec.js";
import { S, catOf, cur, groupOf } from "./state.js";
import { toast } from "./toast.js";
import { $, esc } from "./util.js";

const D = { batches: new Map(), timer: null, approve: true };
try { D.approve = localStorage.getItem("studio.draftApprove") !== "0"; } catch { /* приватний режим */ }

const EMPTY = { live: 0, ai: 0, orig: 0, ai_game: 0, kept: 0, total: 0 };
const nLines = (n) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? "репліка" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? "репліки" : "реплік"}`;

/** Сума mix по групах раси. */
export const raceMix = (c) => (c ? c.groups.reduce((a, g) => { for (const k in a) a[k] += (g.mix || EMPTY)[k]; return a; }, { ...EMPTY }) : { ...EMPTY });

export const mixText = (m) => `живі ${m.live} · ШІ ${m.ai} · ориг. ${m.orig}`;
export const mixTitle = (m) => `Живі — є ваш запис: ${m.live}\nШІ — лише ШІ-чернетка: ${m.ai} (з них обрано для гри ${m.ai_game})\n`
  + `Оригінал — ще звучить оригінал: ${m.orig}${m.kept ? ` (з них свідомо залишено ${m.kept})` : ""}`;

/** Три сегменти: живі (зелений) / ШІ (фіолетовий) / оригінал (фон); з текстом, якщо text. */
export function mixHtml(m = EMPTY, text = true) {
  const w = (n) => `${(100 * n) / Math.max(1, m.total)}%`;
  return `<span class="mix" title="${esc(mixTitle(m))}"><span class="mixbar" aria-hidden="true"><i class="m-live" style="width:${w(m.live)}"></i><i class="m-ai" style="width:${w(m.ai)}"></i></span>${
    text ? `<small class="mix-t"><b class="m-live">живі ${m.live}</b> · <b class="m-ai">ШІ ${m.ai}</b> · ориг. ${m.orig}</small>` : ""}</span>`;
}

/** Шапка юніта й бічна панель — після кожного loadCatalogs (catalog.js). */
export function renderDraftBar() {
  const g = groupOf(), bar = $("#draftBar"), m = g?.mix || EMPTY;
  $("#unitMix").textContent = g ? ` · ${mixText(m)}` : "";
  $("#unitMix").title = g ? mixTitle(m) : "";
  if (!bar) return;
  bar.innerHTML = g ? `${mixHtml(m)}<button class="btn quiet" id="draftBtn" title="ШІ озвучить вашим голосом репліки, де ще немає ні вашого дубля, ні ШІ-варіанта">✨ ШІ-чернетка…</button>` : "";
}

function dialog(plan, cid, scope) {
  const eng = curEngine(), c = catOf(cid), unit = cid === S.cat ? plan.groups.find((g) => g.gid === S.unit) : null;
  const sc = unit ? scope : "race", n = sc === "unit" ? unit.todo.length : plan.todo;
  const raceN = plan.todo, est = n * plan.per_line, fix = fixHint(eng);
  return `<div class="modal-box draft-box"><div class="modal-head"><h3>✨ ШІ-чернетка</h3></div><div class="modal-body">
    <p>ШІ озвучить <b>вашим голосом</b> репліки, де ще немає ні вашого дубля, ні ШІ-варіанта — гра одразу звучить українською,
      а живі записи замінюють чернетку поступово. Кожна така репліка позначена «ШІ».</p>
    <div class="seg draft-scope" role="radiogroup">${unit ? `<button data-scope="unit" class="${sc === "unit" ? "on" : ""}">Юніт «${esc(groupOf()?.title || S.unit)}» · ${nLines(unit.todo.length)}</button>` : ""}
      <button data-scope="race" class="${sc === "race" ? "on" : ""}">Уся раса «${esc((c?.title || cid).split(" — ")[0])}» · ${nLines(raceN)}</button></div>
    <p class="draft-mix">${mixHtml(sc === "unit" ? unit.mix : raceMix(c))}</p>
    <p class="ai-note">Двигун: <b>${esc(eng.title)}</b> (змінити — у панелі «✨ Згенерувати» репліки) · результат ${esc(shortLic(plan.license) || plan.license)}.
      Референси — ваші обрані дублі цього юніта, а якщо їх ще немає — найдовші обрані дублі раси.</p>
    ${fix ? `<p class="ai-fix">${fix}</p>` : ""}
    ${plan.refs ? "" : `<p class="ai-warn" data-draft-norefs>Спершу запишіть і оберіть для гри хоча б один власний дубль цієї раси — ШІ клонує лише ваш голос.</p>`}
    <label class="ai-chk"><input type="checkbox" id="draftApprove" ${D.approve ? "checked" : ""}> Одразу обрати як чернетку для гри
      <small>— лише там, де нічого не обрано й немає вашого запису; живий запис завжди має пріоритет</small></label>
    <p class="draft-eta" id="draftEta">${n ? `Оцінка: ${esc(leftUa(est))} на ${nLines(n)}${plan.ahead ? ` + спершу поточна черга ${esc(leftUa(plan.ahead))}` : ""}
      — за попередніми генераціями; прогрес і скасування — в індикаторі «ШІ» вгорі.` : "Усі репліки вже мають ваш запис або ШІ-варіант (чи вже в черзі) — нічого ставити."}</p>
    ${plan.active ? `<p class="ai-note">Уже в черзі завдань чернетки: ${plan.active} <button class="ghost" data-draft-stop>Скасувати їх</button></p>` : ""}</div>
    <div class="modal-foot"><button class="ghost" data-draft-close>Закрити</button>
      <button class="btn primary" data-draft-go data-n="${n}" ${n && plan.refs ? "" : "disabled"}>✨ Поставити в чергу · ${n}</button></div></div>`;
}

/** Діалог чернетки: scope "unit" | "race"; cid — раса (з меню юнітів може бути не поточна). */
export async function openDraft(cid = S.cat, scope = "unit") {
  let plan;
  try {
    if (!AIS.status) await loadStatus();
    plan = await getJSON(`/api/ai/draft?${new URLSearchParams({ cid, engine: curEngine()?.name || "" })}`);
  } catch (e) { return toast(`ШІ недоступний: ${e.message}`, true); }
  if (!curEngine()) return toast("Немає двигунів ШІ", true);
  document.querySelector("#draftModal")?.remove();
  const m = document.createElement("div");
  m.className = "modal"; m.id = "draftModal"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true");
  const draw = () => { m.innerHTML = dialog(plan, cid, scope); };
  const close = () => { m.remove(); document.removeEventListener("keydown", onKey, true); };
  const onKey = (ev) => { if (ev.code === "Escape" && !document.querySelector("#aiConsent")) { close(); ev.stopImmediatePropagation(); } };
  document.addEventListener("keydown", onKey, true);
  m.onchange = (ev) => { if (ev.target.id === "draftApprove") { D.approve = ev.target.checked; try { localStorage.setItem("studio.draftApprove", D.approve ? "1" : "0"); } catch { /* */ } } };
  m.onclick = async (ev) => {
    const b = ev.target.closest("button");
    if (ev.target === m || b?.dataset.draftClose !== undefined) return close();
    if (!b) return;
    if (b.dataset.scope) { scope = b.dataset.scope; return draw(); }
    const gid = scope === "unit" && cid === S.cat ? S.unit : undefined;
    if (b.dataset.draftStop !== undefined) {
      b.disabled = true;
      try { toast(`Скасовано завдань чернетки: ${(await post("/api/ai/draft/cancel", { cid, gid })).cancelled}`); } catch (e) { toast(e.message, true); }
      kick(); return close();
    }
    if (b.dataset.draftGo !== undefined) { b.disabled = true; if (await submit(cid, gid)) close(); else b.disabled = false; }
  };
  draw();
  document.body.appendChild(m);
  m.querySelector("[data-draft-go]").focus();
}

/** Готовність двигуна → та сама згода «це мій голос», що й у генерації → POST; відмови — тостом. */
async function submit(cid, gid) {
  const eng = curEngine();
  if (eng.status.state !== "ready") {
    toast(`Двигун «${eng.title}» не готовий: ${eng.status.state === "missing_key" ? "потрібен ключ API" : `виконайте ${SETUP_CMD}`}`, true, 9000);
    return false;
  }
  if (!(await ensureConsents(eng))) return false;
  try {
    const r = await post("/api/ai/draft", { cid, gid, engine: eng.name, approve: D.approve });
    if (r.batch) D.batches.set(r.batch, { total: r.queued, cid });
    toast(r.queued ? `ШІ-чернетка: у черзі ${nLines(r.queued)} · результат ${r.license}${D.approve ? " · одразу в гру, де нічого не обрано" : ""}`
      : "Нічого ставити: усі репліки вже мають запис або ШІ-варіант", false, 7000);
    if (r.skipped.length) toast(`Пропущено ${nLines(r.skipped.length)}: ${r.skipped[0].reason}`, true, 9000);
    kick();
    return true;
  } catch (e) { toast(e.message, true, 9000); return false; }
}

/** Підтягнути змінені репліки поточного юніта (нові ШІ-варіанти / обрані чернетки) і прогрес — не під час запису. */
async function refresh() {
  await loadCatalogs().catch(() => {});
  if (Rec.on) return;
  const cid = S.cat, gid = S.unit, curId = cur()?.id;
  try {
    const g = await getJSON(`/api/group/${cid}/${gid}`);
    if (cid !== S.cat || gid !== S.unit) return;
    const sig = (p) => JSON.stringify([p.approved, p.takes.map((t) => t.file), p.ai.map((v) => v.file)]);
    let card = false;
    for (const ln of g.lines) {
      const i = S.phrases.findIndex((x) => x.id === ln.id);
      if (i < 0 || sig(S.phrases[i]) === sig(ln)) continue;
      S.phrases[i] = ln;
      card ||= ln.id === curId;
    }
    renderCues();
    if (card && cur()?.id === curId) renderCard();
  } catch (e) { console.warn("draft refresh", e); }
}

onJobs((jobs, before) => {
  const fin = (s) => s === "done" || s === "failed" || s === "cancelled";
  if (jobs.some((j) => j.draft && j.state === "done" && before.get(j.id)?.state !== "done") && !D.timer) {
    D.timer = setTimeout(() => { D.timer = null; refresh(); }, 600);    // пакет із сотень завдань — не частіше ніж раз на ~0.6 с
  }
  for (const [id, b] of D.batches) {
    const mine = jobs.filter((j) => j.draft && j.draft.batch === id);
    if (mine.length < b.total || !mine.every((j) => fin(j.state))) continue;
    D.batches.delete(id);
    const ok = mine.filter((j) => j.state === "done").length, bad = mine.filter((j) => j.state === "failed");
    toast(`ШІ-чернетка готова: ${ok} з ${b.total}${bad.length ? ` · помилок ${bad.length} (${bad[0].error || "двигун"})` : ""}`, !ok && !!bad.length, 9000);
  }
});

document.addEventListener("click", (e) => { if (e.target.closest("#draftBtn")) openDraft(S.cat, "unit"); });
