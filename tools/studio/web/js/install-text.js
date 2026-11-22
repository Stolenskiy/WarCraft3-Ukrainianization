/* Чекбокс «Текст» у вікні «Встановити в гру»: ціль (визначена за текою гри), сухий прогін у фоні (/api/text/plan + опитування job),
   підсумок плану (коміт upstream, файли, гарячі клавіші), запис лише кнопкою «Встановити»; у режимі «Прибрати з гри» — відкат тексту.
   Інсталятор не чіпаємо: усе робить tools/install_pack.py (бекап Backups/ua-text/, CHANGE-LOG, відкат). Докладніше: docs/plans/text-install-ui.md. */
import { getJSON, post } from "./api.js";
import { toast } from "./toast.js";
import { $, esc, sleep } from "./util.js";

const T = { on: false, voice: true, mode: "install", info: null, target: null, full: false, state: "idle", job: null, error: "", log: [] };

export const textVoiceOn = () => T.voice;
/** Є готовий (переглянутий) план тексту — «Встановити» його запише. */
export const textReady = () => T.mode === "install" && T.on && T.state === "ready";
/** Текст обрано, але план ще не переглянуто: запис заблоковано. */
export const textBlocks = () => T.mode === "install" && T.on && T.state !== "ready";

const tgt = () => (T.info?.targets || []).find((t) => t.id === T.target);

function summary(p) {
  const hk = p.hotkeys;
  return `<div class="inst-sum"><p>Ціль: <b>${esc(p.title)}</b> · корінь <code>${esc(p.root)}</code></p>
    <p>Коміт upstream <code title="sha256 архіву ${esc(p.sha256)}">${esc(String(p.commit).slice(0, 10))}</code> (${esc(p.variant)}) · файлів: <b>нових ${p.new}</b>, <b>змінюється ${p.update}</b>, без змін ${p.same}, пропущено ${p.skipped.length + p.notes_skipped.length}
      ${p.materialize ? `· тек до перетворення: ${p.materialize}` : ""}</p>
    <p>Гарячі клавіші: маркерів додано <b>${hk.markers_added}</b> у ${hk.tips_changed} підказках (${hk.sections_changed} секцій)${hk.skipped_already ? `; вже з розміткою ${hk.skipped_already}` : ""}${hk.skipped_badkey ? `; неприйнятна клавіша ${hk.skipped_badkey}` : ""}</p>
    ${p.repack ? `<p>Патч балансу репаку: додано підказок <b>${p.repack.keys}</b>, секцій ${p.repack.sections}, характеристик в описах ${p.repack.stats}${p.repack.english ? ` (англійською лишилось ${p.repack.english})` : ""}</p>` : ""}
    ${p.status !== "supported" ? `<p class="ai-warn">ЕКСПЕРИМЕНТАЛЬНО: ціль не перевірена на справжній грі. ${esc(p.notes)}</p>` : ""}
    ${[...p.skipped.map((s) => `${s.rel}: ${s.reason}`), ...p.notes_skipped].slice(0, 6).map((s) => `<p class="ai-note">пропуск: ${esc(s)}</p>`).join("")}
    <p class="ai-note">Запис — кнопкою «Встановити» (бекап оригіналів у <code>Backups/ua-text/</code>). Відкат: «Прибрати з гри» → «Прибрати текст».</p></div>`;
}

function render() {
  const box = $("#installText"), i = T.info;
  $("#installParts").hidden = T.mode !== "install";
  $("#installBody").hidden = T.mode === "install" && !T.voice;
  box.hidden = !((T.mode === "install" && T.on) || (T.mode === "uninstall" && i));
  if (box.hidden) return;
  if (!i) { box.innerHTML = `<p class="inst-note">Завантаження цілей…</p>`; return; }
  if (T.mode === "uninstall") {
    const ins = i.targets.filter((t) => t.installed);
    box.innerHTML = ins.length ? ins.map((t) => `<div class="inst-tx"><span>Текст встановлено: <b>${esc(t.title)}</b> · файлів ${t.installed.files}
      ${t.installed.source ? `· коміт <code>${esc(String(t.installed.source.commit).slice(0, 10))}</code>` : ""}</span>
      <button class="btn warn" data-tx-un="${esc(t.id)}">Прибрати текст</button></div>`).join("") : "";
    box.hidden = !ins.length;
    return;
  }
  const opts = i.targets.map((t) => `<option value="${esc(t.id)}" ${t.id === T.target ? "selected" : ""}>${esc(t.title)}${t.status !== "supported" ? " [EXPERIMENTAL]" : ""}</option>`).join("");
  const run = T.state === "running";
  box.innerHTML = `<div class="inst-tx"><label>Ціль <select id="txTarget" ${run ? "disabled" : ""}>${opts}</select></label>
      <small class="cnt">визначено за текою гри: ${esc(i.detected)}</small>
      <label class="ai-chk" title="Кампанії й відео з upstream: ≈ 1 ГБ завантаження"><input type="checkbox" id="txFull" ${T.full ? "checked" : ""} ${run ? "disabled" : ""}> з кампаніями (FULL)</label>
      <button class="btn ${T.state === "ready" ? "" : "primary"}" id="txPlan" ${run ? "disabled" : ""}>${T.state === "ready" ? "Перерахувати план" : "Показати план тексту"}</button></div>
    ${run ? `<p class="inst-note" data-tx-run>Готую (завантаження upstream і збірка)… ${esc(T.log.slice(-1)[0] || "")}</p>` : ""}
    ${T.state === "error" ? `<p class="inst-err" data-tx-err>${esc(T.error)}</p>` : ""}
    ${T.state === "ready" ? summary(T.job.plan) : T.state === "idle" ? `<p class="inst-note">Спершу перегляньте план (у гру нічого не пишеться), потім «Встановити».</p>` : ""}`;
}

async function plan() {
  T.state = "running"; T.log = []; T.job = null; render(); changed();
  try {
    let j = await post("/api/text/plan", { target: T.target, full: T.full });
    while (j.state === "running") { await sleep(600); j = await getJSON(`/api/text/job?id=${j.id}`); T.log = j.log; if (!$("#installModal").hidden) render(); }
    T.job = j; T.state = j.state === "ready" ? "ready" : "error"; T.error = j.error || "";
  } catch (e) { T.state = "error"; T.error = e.message; }
  render(); changed();
}

/** Записує підготовлений план у гру (викликає install.js; помилка → виняток із текстом українською). */
export async function textApply() {
  const r = await post("/api/text/apply", { id: T.job.id });
  T.state = "idle"; T.job = null;
  return r;
}

let changed = () => {};

/** Викликається з install.js при відкритті/перемиканні режиму; onChange — перерахувати кнопку «Встановити». */
export async function textSetup(mode, onChange) {
  changed = onChange;
  T.mode = mode;
  try { T.info = await getJSON("/api/text/targets"); T.target = T.target && T.info.targets.some((t) => t.id === T.target) ? T.target : T.info.detected; }
  catch (e) { T.info = null; toast(e.message, true); }
  render(); changed();
}

export function textOpen() { T.state = "idle"; T.job = null; T.info = null; }

$("#partText").onchange = (e) => { T.on = e.target.checked; render(); changed(); };
$("#partVoice").onchange = (e) => { T.voice = e.target.checked; render(); changed(); };
$("#installText").addEventListener("change", (e) => {
  if (e.target.id === "txTarget") { T.target = e.target.value; T.state = "idle"; T.job = null; render(); changed(); }
  if (e.target.id === "txFull") { T.full = e.target.checked; T.state = "idle"; T.job = null; render(); changed(); }
});
$("#installText").addEventListener("click", async (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.id === "txPlan") plan();
  if (b.dataset.txUn && confirm("Прибрати встановлений текст і повернути оригінали з бекапу?")) {
    b.disabled = true;
    try { toast(`Текст прибрано: файлів ${(await post("/api/text/uninstall", { target: b.dataset.txUn })).removed}. Перезапустіть гру.`, false, 8000); }
    catch (er) { toast("Не вдалося: " + er.message, true, 9000); }
    textSetup("uninstall", changed);
  }
});
