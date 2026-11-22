/* Каталоги (раси), юніти: шапка, поповер вибору, відкриття юніта. */
import { getJSON } from "./api.js";
import { stopPlay } from "./audio.js";
import { renderCard } from "./card.js";
import { renderCues } from "./cues.js";
import { eqLoad } from "./eq-panel.js";
import { saveText } from "./phrase.js";
import { Rec } from "./rec.js";
import { S, catOf, groupOf, isDone } from "./state.js";
import { $, esc, initials } from "./util.js";

export async function loadCatalogs() {
  S.catalogs = await getJSON("/api/catalogs");
  const c = catOf();
  if (c) {
    const done = c.groups.reduce((a, g) => a + g.done, 0), total = c.groups.reduce((a, g) => a + g.total, 0);
    $("#overallName").textContent = "раса";
    $("#overallNum").textContent = `${done} / ${total}`;
    $("#overallBar").style.width = `${(100 * done) / Math.max(1, total)}%`;
  }
  const g = groupOf();
  if (g) {
    $("#unitTitle").textContent = g.title;
    $("#unitSub").textContent = `${catOf().title.split(" — ")[0]} · ${g.done} з ${g.total} готово`;
    $("#unitAvatar").textContent = initials(g.title);
  }
}

let popCat = null; // яка раса відкрита в поповері

function renderUnitGrid() {
  const c = catOf(popCat) || catOf();
  const tabs = S.catalogs.map((x) => {
    const d = x.groups.reduce((a, g) => a + g.done, 0), t = x.groups.reduce((a, g) => a + g.total, 0);
    return `<button class="${x.id === c.id ? "on" : ""}" data-cat="${esc(x.id)}">${esc(x.title.split(" — ")[0])} <small>${d}/${t}</small></button>`;
  }).join("");
  const card = (g) => `<button class="unit-card ${c.id === S.cat && g.id === S.unit ? "on" : ""} ${g.done === g.total ? "complete" : ""}" data-unit="${esc(g.id)}" data-unit-cat="${esc(c.id)}">
      <span class="avatar">${esc(initials(g.title))}</span>
      <span class="meta"><b>${esc(g.title)}</b><small>${g.done} / ${g.total} · ${esc(g.id)}</small>
      <div class="bar"><i style="width:${(100 * g.done) / Math.max(1, g.total)}%"></i></div></span></button>`;
  const sections = [...new Set(c.groups.map((g) => g.section))];
  $("#unitGrid").innerHTML = `<div class="seg cat-tabs">${tabs}</div>` + sections.map((sec) =>
    `<div class="pop-group">${esc(sec)}</div><div class="pop-grid">${c.groups.filter((g) => g.section === sec).map(card).join("")}</div>`).join("");
}

export function toggleUnitPopover(show) {
  const pop = $("#unitPopover");
  show = show ?? pop.hidden;
  if (show) { popCat = S.cat; renderUnitGrid(); }
  pop.hidden = !show;
}

export async function openUnit(cid, gid) {
  if (Rec.on) return;
  saveText();
  stopPlay();
  S.cat = cid; S.unit = gid;
  try { localStorage.setItem("studio.pos", JSON.stringify({ cid, gid })); } catch {}
  const data = await getJSON(`/api/group/${cid}/${gid}`);
  S.phrases = data.lines;
  const i = S.phrases.findIndex((p) => !isDone(p) && !p.no_speech);
  S.idx = i >= 0 ? i : 0;
  await loadCatalogs();
  const g = groupOf();
  renderCues(); renderCard();
  S.eqReady = eqLoad();
}

$("#unitBtn").onclick = () => toggleUnitPopover();

$("#unitPopover").onclick = (e) => {
  const tab = e.target.closest("[data-cat]");
  if (tab) { popCat = tab.dataset.cat; return renderUnitGrid(); }
  const c = e.target.closest("[data-unit]");
  if (c) { toggleUnitPopover(false); openUnit(c.dataset.unitCat, c.dataset.unit); }
  else if (e.target.id === "unitPopover") toggleUnitPopover(false);
};
