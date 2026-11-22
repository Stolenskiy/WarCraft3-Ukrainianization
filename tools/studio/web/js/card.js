/* Картка репліки: розмітка, рядок дубля, обробники кліків. */
import { AI } from "./ai.js";
import { CLIP_ADVICE } from "./clip.js";
import { play, playPreview, playing, stopPlay } from "./audio.js";
import { select } from "./cues.js";
import { EQ, eqChip, eqToggleAB } from "./eq-live.js";
import { saveText } from "./phrase.js";
import { MAX_REC, Rec, renderMicSel, setRecUI, switchMic, toggleRec } from "./rec.js";
import { S, aurl, cur, ids, refLang, urlRef } from "./state.js";
import { approve, clearOriginal, del, keepOriginal, restore, unapprove } from "./takes.js";
import { saveTempo, tempoBadge, tempoClick, tempoLabel, tempoOf, tempoPanel } from "./tempo.js";
import { resetTrim, takeItem } from "./trim.js";
import { $, esc, fmt, timeLabel } from "./util.js";
import { voiceBind, voiceHtml } from "./voice-card.js";
import { loadWaves } from "./wave.js";

function takeRowHtml(p, t, isNew) {
  const id = "take:" + t.file, appr = p.approved === t.file && !t.deleted;
  const actions = t.deleted
    ? `<button class="btn" data-restore="${esc(t.file)}">↩ Відновити</button>`
    : `<button class="btn" data-ab="${esc(t.file)}" title="Спершу оригінал, потім цей дубль">Оригінал → дубль</button>
       <button class="btn quiet" data-preview="${esc(t.file)}" title="Як цей дубль прозвучить у грі: обрізання, темп, шумоговорення, EQ, гучність">▶ У грі</button>
       <button class="btn icon tempo-btn" data-tempo-toggle="${esc(t.file)}" title="Темп: прискорити голос без зміни висоти">⏩</button>
       ${appr ? "" : `<button class="btn primary" data-approve="${esc(t.file)}" title="Цей дубль піде в гру">✓ Обрати</button>`}
       <button class="btn icon" data-del="${esc(t.file)}" title="У кошик (можна відновити)">🗑</button>`;
  return `<div class="take ${appr ? "approved" : ""} ${t.deleted ? "deleted" : ""} ${isNew ? "new" : ""}">
    <button class="play" data-play="${esc(id)}" ${t.exists ? "" : "disabled"}>▶</button>
    <div><div class="take-head"><b>Дубль ${t.n || "?"}</b>
      <span class="fit" data-fit="${esc(t.file)}">${t.exists ? fmt(t.dur) : "файл відсутній"}</span>
      ${appr ? `<span class="badge-game">У ГРІ</span>` : ""}${t.source === "ai" ? `<span class="badge-ai" title="Взято з ШІ-варіантів (${esc(t.engine || "ШІ")})">ШІ</span>` : ""}<span class="trim-info" data-trim-info="${esc(t.file)}"></span>${tempoBadge(t)}
      <span class="time">${t.deleted ? "видалено " + timeLabel(t.deleted) : timeLabel(t.created)}</span></div>
      <div class="wave-box"><canvas class="wave" data-wave="${esc(id)}"></canvas></div>${t.deleted ? "" : tempoPanel(t)}</div>
    <div class="take-actions">${actions}</div></div>`;
}

function renderCardHtml(newFile) {
  const p = cur(), main = $("#main");
  if (!p) { main.innerHTML = `<div class="empty">Немає реплік</div>`; return; }
  const active = p.takes.filter((t) => !t.deleted).reverse(), trash = p.takes.filter((t) => t.deleted).reverse();
  const apprTake = p.takes.find((t) => t.file === p.approved);
  const textState = p.ua_custom ? "ваш текст" : p.ua_hint ? "пропозиція з voice bible — можна змінити" : "введіть український текст";
  main.innerHTML = `<div class="card">
    ${voiceHtml()}
    <div class="eyebrow"><span class="chip type">${esc(p.kind_ua)}</span>
      <span>Репліка ${S.idx + 1} з ${S.phrases.length}</span><span class="dot-sep">${esc(p.id)}</span>
      ${p.no_speech ? `<span class="chip warn">без слів — крик / звук</span>` : ""}</div>

    <div class="lang"><div class="lang-tag" id="refTag">${refLang(p).toUpperCase()}</div><div>
      <h1 class="ru-text">«${esc(p.ru)}»</h1>
      ${S.lang === "en" && p.has_en ? `<div class="ua-meta">звук — англійський оригінал; текст — з російського транскрипту</div>`
        : S.lang === "en" ? `<div class="ua-meta">англійського оригіналу для цієї репліки немає — звучить російський</div>` : ""}
      ${S.lang === "ru" && !p.has_ru ? `<div class="ua-meta">російського оригіналу немає (потрібен мовний пакет — README) — звучить англійський</div>` : ""}
      <div class="wave-row"><button class="play big" data-play="ref" title="Оригінал (R)">▶</button>
        <canvas class="wave" data-wave="ref"></canvas><span class="dur" id="refDur">${fmt(p.ru_dur)}</span></div>
      <div class="orig-row"><button class="btn quiet" id="keepOrig" ${p.original && p.original.lang === refLang(p) ? "disabled" : ""} title="Для звуків без слів (Угу, сміх, крики): у гру піде оригінал без переозвучення (O)">Залишити оригінал (${refLang(p).toUpperCase()})</button>
        ${p.orig_hint && !p.original ? `<span class="chip hint" title="Короткий вигук чи звук без слів">Можна залишити оригінал</span>` : ""}</div></div></div>

    <div class="lang ua-block"><div class="lang-tag">UA</div><div>
      <input class="ua-input" id="ua" value="${esc(p.ua)}" placeholder="Український текст репліки" spellcheck="true">
      <div class="ua-meta"><span id="uaState">${textState}</span>
        ${p.ua_custom && p.ua_hint && p.ua_hint !== p.ua ? `<button class="linkish" id="resetText">повернути «${esc(p.ua_hint)}»</button>` : ""}</div>
      ${p.direction ? `<div class="direction"><b>Як грати</b>${esc(p.direction)}</div>` : ""}
      ${p.original ? `<div class="approved-banner orig"><span>♪</span><span class="grow">Залишено оригінал (${p.original.lang.toUpperCase()}) — переозвучення не потрібне → <code>game-files/${esc(p.game_rel)}</code></span>
        <button class="btn quiet" id="playGame" title="Грає файл, що зараз лежить у грі">▶ Файл у грі</button><button class="btn quiet" id="clearOrig">Скасувати</button></div>` : ""}
      ${p.approved ? `<div class="approved-banner"><span>✓</span><span class="grow">У грі — <b>Дубль ${apprTake ? apprTake.n : "?"}</b> → <code>game-files/${esc(p.game_rel)}</code>${p.stale ? ` <b class="stale-chip" title="Файл у грі зроблено з іншим EQ чи обробкою — оновіть у вкладці «Обробка»">файл застарів</b>` : ""}</span>
        <button class="btn quiet" id="playGame" title="Грає файл, що зараз лежить у грі">▶ Файл у грі</button><button class="btn quiet" id="unapprove">Скасувати вибір</button></div>` : ""}
    </div></div>

    <div class="rec-zone">
      <button class="rec-btn" id="recBtn" title="Запис / стоп (Пробіл)"></button>
      <div class="rec-info"><div class="rec-title" id="recTitle"></div><div class="rec-sub" id="recSub"></div>
        <div class="meter" id="meter">${"<i></i>".repeat(20)}</div>
        <label class="mic-pick" title="Звідки записувати звук">🎙 <select id="micSel"></select></label></div>
      <div class="timer" id="timer">0.0 с<small>макс. ${MAX_REC} с</small></div>
    </div>

    <div class="section-h"><h3>Дублі</h3><span>${active.length ? `${active.length} · новіші зверху` : ""}</span>
      ${active.length ? `<details class="legend"><summary title="Що означають позначки">? Як читати</summary><div>
        <p><i class="lg-mark"></i><b>Помаранчевий пунктир «оригінал»</b> — де закінчився б голос, якби ви говорили
          так само довго, як в оригіналі (відлік від початку вашого голосу). Ваша хвиля помітно далі за пунктир —
          репліка задовга, у грі звучатиме повільніше за анімацію.</p>
        <p><span class="fit good">голос 0.80 с · +0.05 с</span> довжина вашого голосу без тиші на краях і різниця з оригіналом:
          <b class="ok-t">зелений</b> — вкладаєтесь (до +10 %), <b class="warn-t">жовтий</b> — трохи довше (до +30 %),
          <b class="bad-t">червоний</b> — задовго, краще сказати швидше чи коротше.</p>
        <p><b>Тиша на початку й у кінці</b> (<i class="lg-auto"></i>заштрихована частина хвилі) у файлі для гри обрізається
          автоматично, якщо в шапці увімкнено «Обрізати тишу»; сам дубль не змінюється, тож у студії тишу чути.
          Почути точно як у грі — «▶ Як у грі» на будь-якому дублі (з обрізанням, темпом, шумоговоренням, EQ і гучністю оригіналу).</p>
        <p><b>⏩ Темп</b> — прискорює голос без зміни висоти (×0.8–×1.3). «Під довжину оригіналу» ставить темп так, щоб
          голос не перевищував оригінал; підпис «голос … с» уже враховує темп. Звичайне ▶ темп не чує — для цього «▶ Як у грі».</p>
        <p><b>Ручки на хвилі</b> — межі того, що піде в гру. З «Обрізати тишу» вони одразу стоять на краях голосу,
          тож ▶ і «Оригінал → дубль» звучать уже обрізаними. Тягніть, щоб обрізати сильніше (затемнене відкидається)
          або розсунути — тоді видно штриховану тишу. ←/→ на ручці — крок 10 мс, подвійний клік — повернути ручку,
          «Скинути» — обидві. Файл дубля не змінюється.</p>
        <p><kbd>A</kbd> — порівняти звучання з EQ і без нього (A/B) просто під час прослуховування; те саме — клік по чипу «EQ · профіль» на дублі.
          «Без EQ» вирівняно за гучністю, тож різниця — у тембрі, а не в голосності.</p>
        <p><b>Еквалайзер</b> (ліва панель) — дублі в студії звучать уже з EQ персонажа; «Слухаю без EQ» — порівняти.
          Новий вибір для гри отримує поточний профіль; уже обрані файли оновлює «Застосувати до обраних дублів».</p></div></details>` : ""}</div>
    <div class="takes">${active.length ? active.map((t) => takeRow(p, t, t.file === newFile)).join("")
      : `<div class="empty-takes">Ще немає дублів. Послухайте оригінал і запишіть перший — <kbd>Пробіл</kbd></div>`}</div>

    ${trash.length ? `<details class="fold"><summary>Кошик · ${trash.length}</summary><div class="takes">${trash.map((t) => takeRow(p, t)).join("")}</div></details>` : ""}
    <details class="fold"><summary>Журнал дій · ${p.history.length}</summary><ul class="history">
      ${p.history.slice().reverse().map((h) => `<li><time>${esc(timeLabel(h.ts))}</time><span>${esc(h.action)}</span></li>`).join("") || "<li>—</li>"}</ul></details>
  </div>`;
  setRecUI(Rec.on);                                  // перемальовка під час запису не «зупиняє» UI
  renderMicSel();
  $("#micSel").onchange = (e) => { e.target.blur(); switchMic(e.target.value); };  // Пробіл знову = запис
  bindCard(p);
  voiceBind();
  loadWaves(p);
  AI.mount(p);
}

function bindCard(p) {
  const ua = $("#ua");
  ua.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); ua.blur(); }
    if (e.key === "Escape") { ua.value = p.ua; ua.blur(); }
    e.stopPropagation();
  });
  ua.addEventListener("blur", saveText);
  $("#resetText")?.addEventListener("click", () => { ua.value = p.ua_hint; saveText(); });
  $("#recBtn").addEventListener("click", toggleRec);
  $("#unapprove")?.addEventListener("click", unapprove);
  $("#keepOrig")?.addEventListener("click", () => keepOriginal(p));
  $("#clearOrig")?.addEventListener("click", clearOriginal);
  $("#playGame")?.addEventListener("click", () => play([{ url: aurl("game", p.id) + `?v=${Date.now()}`, id: "game" }]));
  $("#main").oninput = (e) => { const r = e.target.closest("[data-tempo-range]"); if (r) tempoLabel(r); };
  $("#main").onchange = (e) => { const r = e.target.closest("[data-tempo-range]"); if (r) saveTempo(ids(p), r.dataset.tempoRange, tempoOf(p, r.dataset.tempoRange), +r.value); };
  $("#main").onclick = (e) => {
    const b = e.target.closest("button, canvas");
    if (!b) return;
    const d = b.dataset;
    if (d.eqChip !== undefined) return eqToggleAB();
    if (d.play || d.wave) {
      const id = d.play || d.wave;
      if (playing && playing.id === id) return stopPlay();
      return play([id === "ref" ? { url: urlRef(p), id } : takeItem(p, id.slice(5))]);
    }
    if (d.preview) return playPreview(p, d.preview);
    if (d.tempoToggle || d.tempoFit || d.tempoReset) return tempoClick(p, d);
    if (d.ab) return play([{ url: urlRef(p), id: "ref" }, takeItem(p, d.ab)]);
    if (d.trimReset) return resetTrim(p, d.trimReset);
    if (d.approve) return approve(d.approve);
    if (d.del) return del(d.del);
    if (d.restore) return restore(d.restore);
  };
}

/** Рядок дубля; з бейджем «перевантаження», якщо сервер позначив дубль clipped. */
export function takeRow(p, t, ...a) {
  const html = takeRowHtml(p, t, ...a);
  return t.clipped ? html.replace('<span class="trim-info"',
    `<span class="badge-clip" title="${esc(CLIP_ADVICE)}">перевантаження</span><span class="trim-info"`) : html;
}

/** Картка репліки; індикатор перевантаження — у панелі запису після кожної перемальовки. */
export function renderCard(...a) {
  renderCardHtml(...a);
  $("#recSub")?.insertAdjacentHTML("afterend", `<span class="clip-flag" id="clipFlag" title="${esc(CLIP_ADVICE)}" hidden>перевантаження</span>`);
}
