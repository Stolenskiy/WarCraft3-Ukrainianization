/* Перемикачі обробки (сервер), мова оригіналу, «Слухати після запису». */
import { getJSON, post } from "./api.js";
import { stopPlay } from "./audio.js";
import { renderCard } from "./card.js";
import { S, cur } from "./state.js";
import { toast } from "./toast.js";
import { $ } from "./util.js";

// Перемикачі обробки живуть на сервері (data/studio/settings.json): ті самі для затвердження, перезапису й «Як у грі».
const SETTING_IDS = { optTrim: "auto_trim", optDenoise: "denoise", optLoudness: "loudness" };

export async function settingsSetup() {
  let cfg = {};
  try { cfg = await getJSON("/api/settings"); } catch (e) { toast("Налаштування не завантажились: " + e.message, true); }
  for (const [id, key] of Object.entries(SETTING_IDS)) {
    const el = $("#" + id);
    if (key in cfg) el.checked = !!cfg[key];
    el.onchange = async () => {
      syncOpts();
      try { await post("/api/settings", { [key]: el.checked }); } catch (e) { el.checked = !el.checked; syncOpts(); toast(e.message, true); return; }
      if (key !== "auto_trim") toast("Діє на нові вибори; обрані файли оновить «Оновити файли гри» (вкладка «Обробка»)", false, 6000);
    };
  }
  syncOpts();
}

// мова оригіналу
try { S.lang = localStorage.getItem("studio.lang") || "ru"; } catch { S.lang = "ru"; }

function renderLang() {
  for (const b of document.querySelectorAll("#optLang button")) b.classList.toggle("on", b.dataset.lang === S.lang);
}

$("#optLang").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-lang]");
  if (!b || b.dataset.lang === S.lang) return;
  S.lang = b.dataset.lang;
  try { localStorage.setItem("studio.lang", S.lang); } catch {}
  renderLang(); stopPlay(); if (cur()) renderCard();
});

renderLang();

{ // «Слухати після запису» — лише налаштування цього браузера; решта перемикачів — на сервері (settingsSetup)
  const el = $("#optAutoplay");
  try { const v = localStorage.getItem("studio.optAutoplay"); if (v !== null) el.checked = v === "1"; } catch {}
  el.onchange = () => { try { localStorage.setItem("studio.optAutoplay", el.checked ? "1" : "0"); } catch {} };
}

function syncOpts() { document.body.classList.toggle("no-autotrim", !$("#optTrim").checked); }

$("#optTrim").addEventListener("change", () => { if (cur()) renderCard(); });   // ручки стають на нові авто-межі

syncOpts();
