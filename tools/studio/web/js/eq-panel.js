/* Вкладка «Обробка»: вибір профілю, простий/докладний режим, збереження через API, оновлення файлів гри. */
import { getJSON, post } from "./api.js";
import { play } from "./audio.js";
import { renderCard } from "./card.js";
import { renderCues } from "./cues.js";
import { eqDraw, eqEditorSetup, eqSvg, eqTable } from "./eq-editor.js";
import { EQ, eqClone, eqDirty, eqLiveUpdate, eqOwn, eqPlain, eqRewire, eqSetBypass } from "./eq-live.js";
import { MACROS, applyMacro } from "./eq-macros.js";
import { S, cur } from "./state.js";
import { toast } from "./toast.js";
import { voiceWhy } from "./voice-card.js";
import { takeItem } from "./trim.js";
import { $, esc } from "./util.js";

try { EQ.mode = localStorage.getItem("studio.eqMode") === "bands" ? "bands" : "simple"; } catch { /* режим лише для зручності */ }

export function eqRender() {                               // зберігає фокус: інакше клавіші підуть у глобальні
  const f = document.activeElement, box0 = $("#eq");
  const attr = f && box0.contains(f) ? ["data-node", "data-macro", "data-mode"].find((a) => f.hasAttribute(a)) : null;
  const key = !f || !box0.contains(f) ? null : f.id ? `#${f.id}` : attr ? `[${attr}="${f.getAttribute(attr)}"]`
    : f.dataset.eq ? `[data-eq="${f.dataset.eq}"]${f.dataset.i != null ? `[data-i="${f.dataset.i}"]` : ":not([data-i])"}` : null;
  eqRenderInner();
  if (key) box0.querySelector(key)?.focus();
  abSync();
}

function abSync() {                                        // липка смуга A/B (поза #eq, тож не перебудовується)
  for (const [id, on] of [["eqA", !EQ.bypass], ["eqB", EQ.bypass]]) { const b = $("#" + id); b.classList.toggle("on", on); b.setAttribute("aria-pressed", on); }
  $("#abNote").textContent = EQ.prof ? `B вирівняно за гучністю з A. Профіль гри — «${(EQ.data.profiles.find((p) => p.id === EQ.data.selected) || {}).name || ""}».` : "";
}

function eqRenderInner() {
  const box = $("#eq");
  if (!EQ.data || !EQ.prof) { box.innerHTML = ""; return; }
  const P = EQ.data.profiles, own = !!eqOwn(), dirty = eqDirty(), amt = Math.round((EQ.prof.amount ?? 1) * 100), simple = EQ.mode !== "bands";
  EQ.sel = Math.min(EQ.sel, Math.max(0, EQ.prof.bands.length - 1));
  const opt = (p) => `<option value="${esc(p.id)}" ${p.id === EQ.id ? "selected" : ""}>${esc(p.name)}</option>`;
  box.innerHTML = `
    <div class="eq-head"><select id="eqSel" aria-label="Профіль">
      <optgroup label="Пресети">${P.filter((p) => p.builtin).map(opt).join("")}</optgroup>
      ${P.some((p) => !p.builtin) ? `<optgroup label="Мої профілі">${P.filter((p) => !p.builtin).map(opt).join("")}</optgroup>` : ""}
    </select>${dirty ? `<button class="linkish" data-saveas>змінено · Зберегти як…</button>` : ""}</div>
    <p class="eq-why" id="eqWhy">${voiceWhy() ? `<b>Чому так.</b> ${esc(voiceWhy())}` : ""}</p>
    ${eqSvg()}
    <div class="eq-row">
      <label class="switch"><input type="checkbox" id="eqOn" ${EQ.prof.enabled ? "checked" : ""}><span></span>Увімкнено</label>
      <div class="seg mini" id="eqMode" role="group" aria-label="Режим редактора">
        <button data-mode="simple" class="${simple ? "on" : ""}" aria-pressed="${simple}">Простий</button><button data-mode="bands" class="${simple ? "" : "on"}" aria-pressed="${!simple}">Смуги</button></div>
    </div>
    ${simple ? `<label class="eq-sl">Сила <output>${amt} %</output>
        <input type="range" data-eq="amount" aria-label="Сила профілю" min="0" max="200" step="5" value="${amt}"></label>
      <div class="eq-macros" role="group" aria-label="Швидкі правки">${Object.entries(MACROS).map(([k, m]) => `<button class="ghost" data-macro="${k}">${m[0]}</button>`).join("")}</div>`
    : `<label class="eq-sl">Підсилення (загальне) <output>${EQ.prof.gain_db} дБ</output>
        <input type="range" data-eq="gain" aria-label="Підсилення (загальне)" min="-12" max="12" step="0.5" value="${EQ.prof.gain_db}"></label>${eqTable()}`}
    <div class="eq-row">
      ${EQ.naming ? `<input type="text" id="eqName" maxlength="60" placeholder="Назва профілю" value="${esc(own ? "" : EQ.prof.name + " (копія)")}">
        <button class="ghost" id="eqSaveNew">Зберегти</button>` : `<button class="ghost" id="eqNew">Зберегти як новий профіль</button>`}
      ${own && dirty ? `<button class="ghost" id="eqUpdate">Оновити профіль</button>` : ""}
      ${own ? `<button class="ghost danger" id="eqDel">Видалити</button>` : ""}
    </div>
    <button class="ghost wide ${EQ.data.stale ? "warn" : ""}" id="eqReexport" title="Перезаписати обрані файли для гри з поточним EQ і обробкою">Оновити файли гри${EQ.data.stale ? ` (${EQ.data.stale})` : ""}</button>
    <p class="eq-hint">${P.find((p) => p.id === EQ.id).builtin ? "Пресет лише для читання: правки зберігайте як новий профіль. " : ""}Зміни чути одразу; у файли для гри вони потрапляють після «Оновити файли гри».</p>`;
  eqDraw();
  $("#procTag").textContent = `EQ · ${EQ.prof.name.split(" — ")[0]}`;
}

let eqLoadSeq = 0;

export async function eqLoad() {
  const my = ++eqLoadSeq;
  EQ.prof = null;   // поки профіль не прийшов, play() чекає S.eqReady, а не грає з профілем попереднього юніта
  try { EQ.data = await getJSON(`/api/eq?cid=${encodeURIComponent(S.cat)}&gid=${encodeURIComponent(S.unit)}`); } catch (e) { EQ.data = null; eqRender(); toast(`Еквалайзер не завантажився: ${e.message || e}`, true); return; }
  if (my !== eqLoadSeq) return;
  EQ.id = EQ.data.selected; EQ.naming = false; EQ.bypass = false; EQ.sel = 0;
  EQ.prof = eqClone(eqPlain(EQ.data.profiles.find((p) => p.id === EQ.id)));
  eqRender(); eqRewire(); eqStaleSync();
}

/** Позначки «файл застарів» у репліках групи (після зміни призначеного EQ сервер знає, що файли гри відстали). */
async function eqStaleSync() {
  try {
    const g = await getJSON(`/api/group/${encodeURIComponent(S.cat)}/${encodeURIComponent(S.unit)}`), by = Object.fromEntries(g.lines.map((l) => [l.id, l.stale]));
    let changed = false;
    for (const p of S.phrases) if (p.id in by && !!p.stale !== by[p.id]) { p.stale = by[p.id]; changed = true; }
    if (changed) renderCard();
  } catch { /* позначка необовʼязкова */ }
}

async function eqCommit(path, body, msg) {  // відповідь — новий стан /api/eq
  try {
    EQ.data = await post(path, { cid: S.cat, gid: S.unit, ...body });
    EQ.id = EQ.data.saved_id || EQ.data.selected; EQ.naming = false;
    EQ.prof = eqClone(eqPlain(EQ.data.profiles.find((p) => p.id === EQ.id)));
    eqRender(); eqRewire(); if (msg) toast(msg);
    eqStaleSync();
    return true;
  } catch (e) { toast(String(e.message || e), true); return false; }
}

export function eqSetup() {
  const box = $("#eq");
  let editTimer = null;
  const edited = (now) => { clearTimeout(editTimer); if (now) eqRender(); else editTimer = setTimeout(eqRender, 400); };   // «змінено» — після паузи, фокус вузла зберігається
  eqEditorSetup(box, edited);
  box.addEventListener("input", (ev) => {
    const el = ev.target, k = el.dataset.eq;
    if (!k || !EQ.prof || el.value === "" || !el.checkValidity()) return;
    const v = +el.value, b = el.dataset.i != null ? EQ.prof.bands[+el.dataset.i] : null;
    if (k === "amount") { const was = EQ.prof.amount; EQ.prof.amount = v / 100; if (!was || !v) eqRewire(); }
    else if (!b) EQ.prof.gain_db = v;
    else if (k === "freq") b.freq_hz = v;
    else if (k === "gain") b.gain_db = v;
    else b.q = v;
    const out = el.parentElement.querySelector("output");
    if (out) out.textContent = k === "amount" ? `${v} %` : `${v} дБ`;
    eqLiveUpdate(); eqDraw();
  });
  box.addEventListener("change", (ev) => {
    if (ev.target.id === "eqSel") {
      const prev = EQ.id;
      eqCommit("/api/eq/assign", { profile_id: ev.target.value }).then((ok) => { if (!ok) { ev.target.value = prev; } });
    } else if (ev.target.id === "eqOn") {
      EQ.prof.enabled = ev.target.checked; eqRender(); eqRewire();
    } else if (ev.target.dataset.eq) eqRender();   // оновити мітку «змінено» й кнопки
  });
  box.addEventListener("click", (ev) => {
    const id = ev.target.id, m = ev.target.closest("[data-macro]"), mode = ev.target.closest("[data-mode]");
    if (m) { applyMacro(m.dataset.macro); eqRender(); eqRewire(); }
    else if (mode) { EQ.mode = mode.dataset.mode; try { localStorage.setItem("studio.eqMode", EQ.mode); } catch { /* лише зручність */ } eqRender(); }
    else if (id === "eqNew" || "saveas" in ev.target.dataset) { EQ.naming = true; eqRender(); $("#eqName").focus(); }
    else if (id === "eqSaveNew") {
      const name = $("#eqName").value.trim();
      if (!name) return toast("Вкажіть назву профілю", true);
      eqCommit("/api/eq/profile", { profile: { ...EQ.prof, name } }, `Профіль «${name}» збережено`);
    } else if (id === "eqUpdate") eqCommit("/api/eq/profile", { id: EQ.id, profile: EQ.prof }, "Профіль оновлено");
    else if (id === "eqDel") { if (confirm(`Видалити профіль «${EQ.prof.name}»?`)) eqCommit("/api/eq/delete", { id: EQ.id }, "Профіль видалено"); }
    else if (id === "eqReexport") eqReexport();
  });
  // Усередині #eq глобальні клавіші не діють, крім L, B, A і Пробілу на повзунках і вузлах (стрілки лишаються їм)
  box.addEventListener("keydown", (ev) => {
    if (!(ev.target.matches("input[type=range], .eq-node") && ["KeyL", "KeyB", "KeyA", "Space"].includes(ev.code))) ev.stopPropagation();
    if (ev.key === "Enter" && ev.target.id === "eqName") $("#eqSaveNew").click();
  });
  $("#abBar").addEventListener("click", (ev) => {
    const id = ev.target.closest("button")?.id;
    if (id === "eqA") eqSetBypass(false);
    else if (id === "eqB") eqSetBypass(true);
    else if (id === "eqRepeat") {
      const p = cur(), last = p && p.takes.filter((t) => !t.deleted && t.exists).slice(-1)[0];
      if (last) play([takeItem(p, last.file)]);
    }
  });
}

async function eqReexport() {
  if (eqDirty() || !EQ.data.profiles.find((p) => p.id === EQ.id)) return toast("Спершу збережіть профіль", true);
  if (EQ.data.selected !== EQ.id && !(await eqCommit("/api/eq/assign", { profile_id: EQ.id }))) return;
  try {
    const r = await post("/api/eq/reexport", { cid: S.cat, gid: S.unit });
    const byId = Object.fromEntries(r.lines.map((l) => [l.id, l]));
    S.phrases = S.phrases.map((p) => byId[p.id] || p);
    EQ.data.stale = r.lines.filter((l) => l.stale).length;
    renderCues(); renderCard(); eqRender();
    toast(r.done.length ? `EQ застосовано до ${r.done.length} дубл. ${r.failed.length ? `(помилок: ${r.failed.length})` : ""}` : "Немає обраних дублів", !r.done.length);
  } catch (e) { toast(String(e.message || e), true); }
}
