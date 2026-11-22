/* Поле «Тека гри»: шлях, джерело (env / налаштування / автопошук), бейдж, «Знайти автоматично», «Зберегти».
   Живе у вкладці «Обробка»; те саме поле з'являється у вікні встановлення, якщо теку гри не знайдено. */
import { getJSON, post } from "./api.js";
import { $, esc } from "./util.js";

const SRC = { env: "змінна WC3_GAME_ROOT", settings: "налаштування студії", auto: "автопошук", default: "типовий шлях (гру не знайдено)" };

function html(g, err) {
  const ro = g.env_overrides, ok = g.valid && !err;
  return `<div class="gr-row"><input type="text" class="gr-path" value="${esc(g.path)}" aria-label="Тека гри Warcraft III" spellcheck="false" ${ro ? "readonly" : ""}
      placeholder="Тека з Warcraft III (де лежить Data/)"></div>
    <div class="gr-row"><span class="gr-badge ${ok ? "ok" : "bad"}" role="status">${ok ? "✓ гру знайдено" : "✗ це не тека WC3"}</span>
      <small class="gr-src">джерело: ${esc(SRC[g.source] || g.source)}</small></div>
    ${err ? `<p class="gr-err" role="alert">${esc(err)}</p>` : ""}
    ${ro ? `<p class="gr-note">Шлях задано змінною середовища WC3_GAME_ROOT (наприклад, у Docker) — змініть її там.</p>` : ""}
    <div class="gr-row"><button class="ghost gr-detect" ${ro ? "disabled" : ""}>Знайти автоматично</button>
      <button class="ghost gr-save" ${ro ? "disabled" : ""}>Зберегти</button>
      ${g.source === "settings" && !ro ? `<button class="linkish gr-clear" title="Забути збережений шлях і шукати автоматично">скинути</button>` : ""}</div>`;
}

/** Малює поле в `el` і оновлює його після кожної дії; onChange(state) — коли шлях збережено/скинуто. */
export async function mountGameRoot(el, onChange = () => {}) {
  let g;
  try { g = await getJSON("/api/game-root"); } catch (e) { el.innerHTML = `<p class="gr-err">${esc(e.message)}</p>`; return null; }
  const draw = (state, err = "") => { g = state; el.innerHTML = html(g, err); };
  const run = async (body) => {
    try { const s = await post("/api/game-root", body); draw(s); onChange(s); }
    catch (e) { draw({ ...g, path: body.path ?? g.path, valid: false }, String(e.message || e)); }
  };
  el.onclick = (ev) => {
    if (ev.target.closest(".gr-save")) run({ path: $(".gr-path", el).value.trim() });
    else if (ev.target.closest(".gr-detect")) run({ autodetect: true });
    else if (ev.target.closest(".gr-clear")) run({ clear: true });
  };
  el.onkeydown = (ev) => { if (ev.key === "Enter" && ev.target.matches(".gr-path")) $(".gr-save", el).click(); ev.stopPropagation(); };
  draw(g);
  return g;
}

mountGameRoot($("#gameRoot")).catch(() => {});
