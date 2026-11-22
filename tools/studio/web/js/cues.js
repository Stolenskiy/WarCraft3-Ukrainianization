/* Список реплік і навігація (фільтр, ↑/↓, наступна незатверджена). */
import { AI } from "./ai.js";
import { stopPlay } from "./audio.js";
import { renderCard } from "./card.js";
import { saveText } from "./phrase.js";
import { Rec } from "./rec.js";
import { S, isDone } from "./state.js";
import { toast } from "./toast.js";
import { $, esc } from "./util.js";

function visible() {
  return S.phrases.map((p, i) => i).filter((i) => {
    const p = S.phrases[i];
    return S.filter === "all" || (S.filter === "done" ? isDone(p) : !isDone(p));
  });
}

export function renderCues() {
  $("#cues").innerHTML = visible().map((i) => {
    const p = S.phrases[i], n = p.takes.filter((t) => !t.deleted).length;
    const st = p.approved ? "ok" : p.original ? "orig" : n ? "has" : p.no_speech ? "mute" : "";
    return `<li class="cue ${i === S.idx ? "on" : ""} ${p.no_speech ? "mute" : ""}" data-i="${i}">
      <span class="st ${st}"></span>
      <span><div class="ru">${esc(p.ru)}</div><div class="ua">${esc(p.ua)}</div></span>
      <span class="tag">${esc(p.kind_ua)}${p.original ? `<br><b class="orig-chip" title="У грі лишається оригінал">ориг. ${p.original.lang.toUpperCase()}</b>` : n ? `<br>${n} дубл.` : ""}${AI.cueMark(p)}</span></li>`;
  }).join("") || `<li class="empty">Тут порожньо</li>`;
  $("#cues .cue.on")?.scrollIntoView({ block: "nearest" });
}

export function select(i) {
  if (Rec.on || i < 0 || i >= S.phrases.length) return;
  saveText();
  stopPlay();
  S.idx = i;
  renderCues(); renderCard();
}

export function step(d) {
  const v = visible();
  if (!v.length) return;
  const pos = v.indexOf(S.idx);
  select(v[Math.max(0, Math.min(v.length - 1, (pos < 0 ? 0 : pos + d)))]);
}

export function nextTodo() {
  const n = S.phrases.length;
  for (let k = 1; k <= n; k++) {
    const j = (S.idx + k) % n;
    if (!isDone(S.phrases[j]) && !S.phrases[j].no_speech) return select(j);
  }
  toast("Усі репліки цього юніта затверджено 🎉");
}

$("#filter").onclick = (e) => {
  const b = e.target.closest("button"); if (!b) return;
  S.filter = b.dataset.f;
  document.querySelectorAll("#filter button").forEach((x) => x.classList.toggle("on", x === b));
  renderCues();
};

$("#cues").onclick = (e) => { const li = e.target.closest("[data-i]"); if (li) select(+li.dataset.i); };
