/* Вікно «Встановити в гру / Прибрати з гри». */
import { getJSON, post } from "./api.js";
import { play } from "./audio.js";
import { renderCard } from "./card.js";
import { select } from "./cues.js";
import { S, cur } from "./state.js";
import { toast } from "./toast.js";
import { $, esc, nFiles } from "./util.js";

$("#openGameDir").onclick = () => post("/api/open-dir", { cid: S.cat, gid: S.unit }).catch((e) => toast(e.message, true));

// Вікно: дерево Раса → Юніт → файли з чекбоксами (стан — самі чекбокси в DOM), режими «Встановити» / «Прибрати з гри».
const Inst = { mode: "install", busy: false };

const instModal = () => $("#installModal");

const instBoxes = (el = instModal()) => [...el.querySelectorAll("input[data-f]")];

const instShort = (t) => String(t).replace(/\s*\(.*\)\s*$/, "");

const INST_TAGS = {
  new: ["нове", "new"], update: ["оновиться", "upd"], same: ["вже в грі", "same"],
  present: ["у грі", "new"], changed: ["змінено не нами", "same"], missing: ["файлу немає", "same"],
};

const voiceUrl = (a, rel) => `/audio/voice/${encodeURIComponent(a)}/${rel.split("/").map(encodeURIComponent).join("/")}`;

const authName = (id) => ((Inst.authors || []).find((a) => a.id === id) || {}).name || id;

// Вибір голосу: <select> автора для раси / юніта / рядка (пише data/studio/voice-choice.json через /api/voices/choice).
function authSelect(attr, key, chosen, authors) {
  if ((Inst.authors || []).length < 2) return "";
  const opts = [`<option value="">за замовчуванням</option>`, ...authors.map((a) => `<option value="${esc(a)}" ${a === chosen ? "selected" : ""}>${esc(authName(a))}</option>`)];
  return `<select class="auth-sel" ${attr}="${esc(key)}" title="Чий голос">${opts.join("")}</select>`;
}

function instFile(f) {
  const [txt, cls] = INST_TAGS[f.status] || [f.status, ""];
  const off = f.status === "same" || f.status === "changed" || f.status === "missing";
  const un = Inst.mode === "uninstall";
  const who = un ? "" : (f.alts && f.alts.length > 1
    ? authSelect("data-vl", f.rel, (Inst.choice.line || {})[f.rel] || "", f.alts)
    : `<span class="tag who">${esc(authName(f.author))}</span>`) +
    (f.fallback ? `<span class="tag upd" title="Обраного автора цієї репліки немає — взято наступного за порядком">запасний: ${esc(authName(f.author))}</span>` : "") +
    `<button type="button" class="ghost play-v" data-play="${esc(f.rel)}" data-a="${esc(f.author)}" title="Послухати">▶</button>`;
  return `<li class="${off ? "dim" : ""}"><label><input type="checkbox" data-f="${esc(f.rel)}" ${off ? "" : "checked"}>
    <code>${esc(f.name)}</code><span class="tag ${cls}">${txt}</span></label>${who}</li>`;
}

function instUnit(r, u) {
  const mat = u.files.some((f) => f.materialize);
  return `<details class="inst-unit" data-key="${esc(r.id)}/${esc(u.id)}"><summary>
    <input type="checkbox" data-g title="Усі файли персонажа"><b>${esc(instShort(u.title))}</b>
    <small class="cnt"></small>${Inst.mode === "install" ? authSelect("data-vu", `${r.id}/${u.id}`, (Inst.choice.unit || {})[`${r.id}/${u.id}`] || "", Inst.authors.map((a) => a.id)) : ""}${mat ? `<span class="tag mat" title="Тека юніта в грі — симлінк на Mods/. Її буде замінено реальною текою з симлінками на оригінальні файли; відкат повертає симлінк.">потребує перетворення теки</span>` : ""}</summary>
    <ul class="inst-list">${u.files.map(instFile).join("")}</ul></details>`;
}

function instRender(pl) {
  const un = Inst.mode === "uninstall";
  Inst.authors = pl.authors || []; Inst.choice = pl.choice || { default: [], race: {}, unit: {}, line: {} };
  const body = pl.races.map((r) => `<details class="inst-race" data-key="${esc(r.id)}"><summary>
    <input type="checkbox" data-g title="Усі файли раси"><b>${esc(r.title)}</b><small class="cnt"></small>${
      Inst.mode === "install" ? authSelect("data-vr", r.id, (Inst.choice.race || {})[r.id] || "", Inst.authors.map((a) => a.id)) : ""}</summary>
    ${r.units.map((u) => instUnit(r, u)).join("")}</details>`).join("");
  $("#installBody").innerHTML = `<p class="inst-game">Тека гри: <code>${esc(pl.game)}</code></p>` +
    (body || `<p class="inst-note">${un ? "Нічого не встановлено нами." : "Немає обраних дублів у game-files/."}</p>`) +
    (pl.skipped && pl.skipped.length ? `<details class="inst-skip"><summary><b>Пропущено</b> <small>${pl.skipped.length}</small></summary><ul class="inst-list skip">${
      pl.skipped.map((s) => `<li><code>${esc(s.rel)}</code><small>${esc(s.reason)}</small></li>`).join("")}</ul></details>` : "") +
    (pl.same && !un ? `<p class="inst-note">Уже в грі й без змін: ${pl.same} (за замовчуванням не обрано)</p>` : "");
  instSync();
}

function instSync() {                          // стани груп (повністю / частково / нічого) і лічильники
  const m = instModal();
  for (const d of m.querySelectorAll("details.inst-unit, details.inst-race")) {
    const bx = instBoxes(d), on = bx.filter((b) => b.checked).length, g = d.querySelector(":scope > summary > input[data-g]");
    g.checked = bx.length > 0 && on === bx.length; g.indeterminate = on > 0 && on < bx.length;
    d.querySelector(":scope > summary .cnt").textContent = d.classList.contains("inst-race")
      ? `· ${on} з ${bx.length} обрано` : `· ${nFiles(bx.length)}` + (on < bx.length ? ` · ${on} обрано` : "");
  }
  const n = instBoxes().filter((b) => b.checked).length, un = Inst.mode === "uninstall";
  const go = $("#installGo");
  go.textContent = (un ? "Прибрати" : "Встановити") + (n ? ` (${n})` : "");
  go.classList.toggle("warn", un); go.disabled = !n || Inst.busy;
}

async function instLoad(keep) {                   // keep = {open: [data-key], off: [rel]} — стан дерева переживає перерахунок
  const state = keep || null;
  document.querySelectorAll("#installMode button").forEach((b) => b.classList.toggle("on", b.dataset.mode === Inst.mode));
  $("#installBody").innerHTML = `<p class="inst-note">Перевіряю…</p>`;
  $("#installGo").disabled = true;
  try {
    instRender(await getJSON(Inst.mode === "install" ? "/api/install/plan" : "/api/uninstall/plan"));
    if (state) {
      instModal().querySelectorAll("details[data-key]").forEach((d) => { d.open = state.open.includes(d.dataset.key); });
      instBoxes().forEach((b) => { if (state.off.includes(b.dataset.f)) b.checked = false; });
      instSync();
    }
  }
  catch (e) { $("#installBody").innerHTML = `<p class="inst-err">${esc(e.message)}</p>`; }
}

function openInstall() { instModal().hidden = false; instLoad(); }

const closeInstall = () => { instModal().hidden = true; };

async function instRun() {
  if (Inst.busy) return;
  const files = instBoxes().filter((b) => b.checked).map((b) => b.dataset.f), un = Inst.mode === "uninstall";
  if (!files.length) return;
  Inst.busy = true; $("#installGo").disabled = true;
  try {
    const r = await post(un ? "/api/uninstall" : "/api/install", { files });
    closeInstall();
    toast(un ? `Прибрано з гри файлів: ${r.removed}` + (r.restored_links.length ? `; симлінків повернуто: ${r.restored_links.length}` : "") + "."
      : `Встановлено файлів: ${r.installed}` + (r.materialized.length ? `; теки відкріплено від Mods: ${r.materialized.length}` : "") + ". Перезапустіть гру.", false, 9000);
    if (cur()) { try { renderCard(); } catch {} }
  } catch (e) { toast("Не вдалося: " + e.message, true, 10000); closeInstall(); }
  finally { Inst.busy = false; }
}

$("#installBtn").onclick = openInstall;

$("#installClose").onclick = closeInstall;

$("#installModal").addEventListener("click", (e) => { if (e.target.id === "installModal") closeInstall(); });

$("#installMode").onclick = (e) => { const b = e.target.closest("button[data-mode]"); if (b && b.dataset.mode !== Inst.mode) { Inst.mode = b.dataset.mode; instLoad(); } };

$("#installGo").onclick = instRun;

let vPlayer = null;

$("#installBody").addEventListener("click", (e) => {            // ▶ послухати рядок (обраного/поточного автора)
  const b = e.target.closest("button[data-play]");
  if (!b) return;
  const sel = b.parentElement.querySelector("select[data-vl]");
  if (vPlayer) vPlayer.pause();
  vPlayer = new Audio(voiceUrl((sel && sel.value) || b.dataset.a, b.dataset.play));
  vPlayer.play().catch((er) => toast("Не вдалося відтворити: " + er.message, true));
});

async function instChoose(sel) {
  const kind = sel.hasAttribute("data-vr") ? ["race", "data-vr"] : sel.hasAttribute("data-vu") ? ["unit", "data-vu"] : ["line", "data-vl"];
  const body = { [kind[0]]: { ...(Inst.choice[kind[0]] || {}), [sel.getAttribute(kind[1])]: sel.value || null } };
  const keep = { open: [...instModal().querySelectorAll("details[open][data-key]")].map((d) => d.dataset.key),
    off: instBoxes().filter((b) => !b.checked).map((b) => b.dataset.f) };
  try { await post("/api/voices/choice", body); } catch (er) { toast("Не вдалося: " + er.message, true); }
  instLoad(keep);
}

$("#installBody").addEventListener("change", (e) => {
  const t = e.target;
  if (t.matches("select.auth-sel")) return instChoose(t);
  if (t.matches("input[data-g]")) instBoxes(t.closest("details")).forEach((b) => { b.checked = t.checked; });   // група → усі нащадки
  instSync();
});

document.addEventListener("keydown", (e) => {     // поки відкрито вікно — клавіші студії (Пробіл = запис) не діють
  if (instModal().hidden) return;
  if (e.code === "Escape") closeInstall();
  e.stopImmediatePropagation();
}, true);
