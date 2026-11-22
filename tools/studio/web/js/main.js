/* Точка входу: імпорт модулів, старт, налагоджувальна поверхня window.__studio. */
import { getJSON } from "./api.js";
import { playing, stopPlay } from "./audio.js";
import { openUnit } from "./catalog.js";
import { clipCheck } from "./clip.js";
import { EQ } from "./eq-live.js";
import { eqLoad, eqSetup } from "./eq-panel.js";
import "./install.js";
import "./keys.js";
import "./voices.js";
import { Rec } from "./rec.js";
import { settingsSetup } from "./settings.js";
import { S, cur } from "./state.js";
import { takeRow } from "./card.js";
import { $, esc } from "./util.js";
import { drawWave, waves } from "./wave.js";

eqSetup();

/** Налагоджувальна поверхня для e2e-тестів (page.evaluate); застосунок її не використовує. */
window.__studio = { S, EQ, Rec, waves, cur, takeRow, clipCheck, stopPlay, eqLoad, get playing() { return playing; } };

window.addEventListener("resize", () => waves.forEach((_, id) => drawWave(id)));

window.addEventListener("beforeunload", (e) => { if (Rec.on) { e.preventDefault(); e.returnValue = ""; } });

(async () => {
  await settingsSetup();
  S.catalogs = await getJSON("/api/catalogs");
  let pos = null;
  try { pos = JSON.parse(localStorage.getItem("studio.pos") || "null"); } catch {}
  if (!pos || !S.catalogs.some((c) => c.id === pos.cid && c.groups.some((g) => g.id === pos.gid))) {
    const c = S.catalogs[0];
    pos = c && { cid: c.id, gid: c.groups[0]?.id };
  }
  if (pos) await openUnit(pos.cid, pos.gid);
})().catch((e) => { $("#main").innerHTML = `<div class="empty">Помилка: ${esc(e.message)}</div>`; });
