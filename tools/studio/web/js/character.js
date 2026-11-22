/* Пресет персонажа (вкладка «Обробка», над EQ): висота, форманти, гроул, простір; пропозиція з voice bible;
   A/B «з пресетом / без» — сторону A дає сервер (/api/character/audio), EQ поверх накладає eq-live.js. */
import { getJSON, post } from "./api.js";
import { EQ } from "./eq-live.js";
import { eqRender, eqStaleSync } from "./eq-panel.js";
import { S } from "./state.js";
import { toast } from "./toast.js";
import { $, esc } from "./util.js";

// Пресет {enabled, pitch_st, formant_pct, drive, reverb, tail_s} (перевірка й ffmpeg — character.py)
export const CH = { data: null, p: null, cid: null, gid: null, timer: null, pending: null };

const FIELDS = [["pitch_st", "Висота", "пт", 0.1, "Тон голосу; тривалість і тембр (форманти) не змінюються"],
  ["formant_pct", "Форманти", "%", 1, "Тембр: − більший і темніший персонаж, + менший і світліший; тон той самий"],
  ["drive", "Гроул", "%", 1, "Сатурація й шорсткість — гарчання для орків, звірів, чудовиськ"],
  ["reverb", "Простір", "%", 1, "Реверберація: склеп, ліс, собор; 0 — сухо"],
  ["tail_s", "Хвіст", "с", 0.1, "Довжина хвоста простору"]];

const sign = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v);
const fmtV = (k, v) => (k === "pitch_st" ? `${sign(v)} пт` : k === "formant_pct" ? `${sign(v)} %` : k === "tail_s" ? `${v} с` : `${v} %`);
const active = () => !!(CH.p && CH.p.enabled && CH.cid === S.cat && CH.gid === S.unit);

function slider([k, label, , step, title]) {
  const [lo, hi] = CH.data.limits[k];
  return `<label class="eq-sl" title="${esc(title)}">${label} <output>${fmtV(k, CH.p[k])}</output>
    <input type="range" data-ch="${k}" aria-label="${label}" min="${lo}" max="${hi}" step="${step}" value="${CH.p[k]}"></label>`;
}

function abLabels() {
  const a = $("#eqA"), b = $("#eqB"), on = active();
  if (!a || !b) return;
  a.textContent = on ? "A · з пресетом" : "A · з EQ"; b.textContent = "B · без";
  a.title = on ? "Слухати з пресетом персонажа й EQ (клавіша A перемикає)" : "Слухати з EQ (клавіша A перемикає)";
  b.title = on ? "Слухати сирий дубль (без пресета й EQ)" : "Слухати без EQ";
}

export function charRender() {
  const box = $("#char");
  if (!box) return;
  const f = document.activeElement, focus = f && box.contains(f) ? (f.dataset.ch ? `[data-ch="${f.dataset.ch}"]` : f.id ? `#${f.id}` : null) : null;
  const d = CH.data;
  if (!d || !CH.p) { box.innerHTML = ""; abLabels(); return; }
  const on = CH.p.enabled;
  box.innerHTML = `
    <div class="ch-head"><h3>Персонаж</h3>
      <label class="switch" title="Висота, форманти й ефекти — у прослуховуванні й у файлі для гри"><input type="checkbox" id="charOn" ${on ? "checked" : ""}><span></span>Увімкнено</label></div>
    <p class="eq-why">${d.bible ? `<b>Voice bible.</b> ${esc(d.bible)}` : "У voice bible немає рядка «Обробка» — пропозиція з расової палітри."}</p>
    ${d.why.length ? `<div class="ch-why" aria-label="Пропозиція з voice bible">${d.why.map((w) => `<span class="vchip">${esc(w)}</span>`).join("")}</div>` : ""}
    <div class="ch-sliders ${on ? "" : "off"}">${FIELDS.map(slider).join("")}</div>
    <div class="eq-row">${d.custom ? `<button class="ghost" id="charReset" title="Повернути пропозицію з voice bible (пресет вимкнеться)">Скинути до voice bible</button>`
      : `<span class="eq-hint">Це пропозиція з voice bible — підлаштуйте під себе й увімкніть.</span>`}</div>
    <p class="eq-hint">A/B унизу: «A · з пресетом» — персонаж і EQ, «B · без» — сирий дубль. Висоту й ефекти чути з наступного ▶;
      у файли для гри — кнопкою «Оновити файли гри».</p>`;
  if (focus) box.querySelector(focus)?.focus();
  abLabels();
}

let loadSeq = 0;

export async function charLoad() {
  const my = ++loadSeq;
  if (CH.timer) save();
  CH.data = CH.p = null; CH.cid = S.cat; CH.gid = S.unit;
  charRender();
  try {
    const r = await getJSON(`/api/character?cid=${encodeURIComponent(S.cat)}&gid=${encodeURIComponent(S.unit)}`);
    if (my !== loadSeq) return;
    CH.data = r; CH.p = { ...r.preset };
  } catch (e) { if (my === loadSeq) toast(`Пресет персонажа не завантажився: ${e.message || e}`, true); }
  charRender();
}

function applied(r) {                     // відповідь сервера → стан, позначки «файл гри застарів»
  const wasCustom = CH.data && CH.data.custom;
  CH.data = r;
  if (EQ.data) { EQ.data.stale = r.stale; eqRender(); }
  eqStaleSync();
  if (wasCustom !== r.custom) charRender(); else abLabels();
}

function save() {
  clearTimeout(CH.timer); CH.timer = null;
  const body = { cid: CH.cid, gid: CH.gid, preset: { ...CH.p } };
  CH.pending = post("/api/character", body)
    .then((r) => { if (CH.cid === body.cid && CH.gid === body.gid) applied(r); })
    .catch((e) => toast(String(e.message || e), true));
  return CH.pending;
}

/** Адреса «голосу персонажа» для дубля, якщо пресет увімкнено (спершу дочекатися збереження правок). */
export async function charUrl(file) {
  if (CH.timer) save();
  await CH.pending;
  if (!active() || !CH.data) return null;
  const p = S.phrases.find((x) => x.takes.some((t) => t.file === file));
  if (!p) return null;
  return `/api/character/audio?${new URLSearchParams({ cid: S.cat, gid: S.unit, lid: p.id, file, v: JSON.stringify(CH.data.preset) })}`;
}

const box = $("#char");
box.addEventListener("input", (ev) => {
  const k = ev.target.dataset.ch;
  if (!k || !CH.p) return;
  CH.p[k] = +ev.target.value;
  ev.target.parentElement.querySelector("output").textContent = fmtV(k, CH.p[k]);
  clearTimeout(CH.timer); CH.timer = setTimeout(save, 500);
});
box.addEventListener("change", (ev) => {
  if (ev.target.id !== "charOn" || !CH.p) return;
  CH.p.enabled = ev.target.checked;
  box.querySelector(".ch-sliders")?.classList.toggle("off", !CH.p.enabled);
  save().then(() => toast(CH.p && CH.p.enabled ? "Пресет персонажа ввімкнено — «Оновити файли гри», щоб записати у гру" : "Пресет персонажа вимкнено"));
  abLabels();
});
box.addEventListener("click", async (ev) => {
  if (ev.target.id !== "charReset") return;
  clearTimeout(CH.timer); CH.timer = null;
  try {
    const r = await post("/api/character", { cid: CH.cid, gid: CH.gid, preset: null });
    CH.p = { ...r.preset }; applied(r); charRender();
    toast("Пресет скинуто до пропозиції voice bible");
  } catch (e) { toast(String(e.message || e), true); }
});
// Глобальні клавіші всередині панелі не діють, крім A, B, L і Пробілу на повзунках (як в EQ)
box.addEventListener("keydown", (ev) => {
  if (!(ev.target.matches("input[type=range]") && ["KeyL", "KeyB", "KeyA", "Space"].includes(ev.code))) ev.stopPropagation();
});
