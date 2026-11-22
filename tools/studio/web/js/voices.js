/* Вікно «Голоси спільноти»: порядок авторів, публікація власного голосу. */
import { getJSON, post } from "./api.js";
import { toast } from "./toast.js";
import { $, esc, mb, nFiles } from "./util.js";

// Автори й порядок пріоритету (↑↓, чекбокс «використовувати»), публікація власного голосу зі згодою CC BY 4.0.
const Vs = { v: null, order: [], on: new Set(), result: null };

const voicesModal = () => $("#voicesModal");

function vCoverage(a) {
  const c = Object.entries(a.coverage).map(([r, u]) => `${esc(r)}: ${Object.values(u).reduce((x, y) => x + y, 0)}`);
  return c.join(" · ") || "порожньо";
}

function vRender() {
  const v = Vs.v, by = Object.fromEntries(v.authors.map((a) => [a.id, a]));
  const rows = Vs.order.map((id, i) => { const a = by[id]; return `<li class="v-row" data-id="${esc(id)}">
    <input type="checkbox" data-von ${Vs.on.has(id) ? "checked" : ""} title="Використовувати при встановленні">
    <span class="v-name"><b>${esc(a.name)}</b><small>${a.local ? "ваші затверджені дублі (game-files/)" : esc(a.license) + " · " + mb(a.bytes)}
      · ${nFiles(a.files)}${a.ai ? ` · <span class="tag upd" title="Згенеровано ШІ власним голосом автора">ШІ ${a.ai}</span>` : ""} · ${vCoverage(a)}</small></span>
    <button class="ghost" data-vup ${i ? "" : "disabled"} title="Вище (пріоритетніший)">↑</button>
    <button class="ghost" data-vdown ${i < Vs.order.length - 1 ? "" : "disabled"} title="Нижче">↓</button></li>`; }).join("");
  const r = Vs.result;
  $("#voicesBody").innerHTML = `<h4>Порядок за замовчуванням <small>перший, у кого є репліка, виграє; вибір для раси/юніта — у вікні «Встановити в гру»</small></h4>
    <ul class="v-list">${rows}</ul>
    <h4>Опублікувати мій голос</h4>
    <p class="inst-note">Експортуються лише ваші затверджені дублі з game-files/ (FLAC, ${esc(v.license)}). Git ми не запускаємо — лише підкажемо команди.</p>
    <div class="v-pub"><input id="vNick" placeholder="нікнейм (a-z, 0-9, -)" maxlength="32" value="${esc(v.nickname)}" autocomplete="off">
      <button class="btn primary" id="vPublish">Опублікувати</button></div>
    <label class="v-consent"><input type="checkbox" id="vConsent"> ${esc(v.consent_text)}</label>
    ${r ? `<div class="v-result"><p>+${r.added} нових · ${r.updated} оновлено · ${r.removed} прибрано · ${r.unchanged} без змін · усього ${nFiles(r.files)}, ${r.total_mb} МБ
      ${r.skipped.length ? ` · пропущено ${r.skipped.length}` : ""}</p><p class="inst-note">Далі виконайте в терміналі (репозиторій проєкту):</p><pre>${esc(r.git.join("\n"))}</pre></div>` : ""}`;
}

async function vSaveOrder() {
  try { Vs.v = await post("/api/voices/choice", { default: Vs.order.filter((id) => Vs.on.has(id)) }); }
  catch (e) { toast("Не вдалося: " + e.message, true); }
}

async function openVoices() {
  voicesModal().hidden = false;
  $("#voicesBody").innerHTML = `<p class="inst-note">Завантажую…</p>`;
  try {
    const v = Vs.v = await getJSON("/api/voices"), all = v.authors.map((a) => a.id);
    Vs.on = new Set(v.choice.default);
    Vs.order = [...v.choice.default.filter((id) => all.includes(id)), ...all.filter((id) => !v.choice.default.includes(id))];
    Vs.result = null; vRender();
  } catch (e) { $("#voicesBody").innerHTML = `<p class="inst-err">${esc(e.message)}</p>`; }
}

const closeVoices = () => { voicesModal().hidden = true; };

$("#voicesBtn").onclick = openVoices;

$("#voicesClose").onclick = closeVoices;

voicesModal().addEventListener("click", async (e) => {
  if (e.target.id === "voicesModal") return closeVoices();
  const row = e.target.closest(".v-row"), pub = e.target.closest("#vPublish");
  if (row && (e.target.closest("[data-vup]") || e.target.closest("[data-vdown]"))) {
    const i = Vs.order.indexOf(row.dataset.id), j = i + (e.target.closest("[data-vup]") ? -1 : 1);
    [Vs.order[i], Vs.order[j]] = [Vs.order[j], Vs.order[i]];
    await vSaveOrder(); vRender();
  }
  if (pub) {
    const nick = $("#vNick").value.trim(), consent = $("#vConsent").checked;
    if (!consent) return toast("Підтвердьте, що це ваш голос і ліцензію CC BY 4.0.", true);
    pub.disabled = true;
    try { Vs.result = await post("/api/voices/publish", { nickname: nick, consent }); Vs.v = await getJSON("/api/voices"); vRender(); }
    catch (er) { toast("Не вдалося: " + er.message, true, 8000); pub.disabled = false; }
  }
});

voicesModal().addEventListener("change", async (e) => {
  const row = e.target.closest(".v-row");
  if (row && e.target.matches("[data-von]")) {
    e.target.checked ? Vs.on.add(row.dataset.id) : Vs.on.delete(row.dataset.id);
    await vSaveOrder();
  }
});

document.addEventListener("keydown", (e) => {
  if (voicesModal().hidden) return;
  if (e.code === "Escape") closeVoices();
  e.stopImmediatePropagation();                 // у вікні клавіші студії (Пробіл = запис) не діють
}, true);
