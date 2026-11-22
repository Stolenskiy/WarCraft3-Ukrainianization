/* ШІ-варіанти реплік (голос ШІ, клонований із ВЛАСНИХ дублів користувача).
   Хуки: AI.mount(p) в кінці renderCard (card.js), AI.cueMark(p) у renderCues (cues.js). Усе інше — тут.
   Дані: p.ai = [{file, n, engine, cer, similarity, dur, style, adopted}], аудіо — /audio/ai/<cid>/<gid>/<file>. */

import { again, basedOn, mountGen } from "./ai-gen.js";
import { onLine } from "./ai-queue.js";
import { AIS, loadStatus, shortLic } from "./ai-state.js";
import { getJSON } from "./api.js";
import { loadBuf, play, playing, stopPlay } from "./audio.js";
import { renderCues } from "./cues.js";
import { act, putPhrase } from "./phrase.js";
import { Rec } from "./rec.js";
import { S, aurl, cur, ids, urlRef } from "./state.js";
import { toast } from "./toast.js";
import { takeItem } from "./trim.js";
import { esc, fmt } from "./util.js";
import { drawWave, waves } from "./wave.js";

export const AI = (() => {
  const urlAi = (f) => aurl("ai", f);
  const aiItem = (f) => ({ url: urlAi(f), id: "ai:" + f });
  const ownTakes = (p) => p.takes.filter((t) => !t.deleted && t.exists && t.source !== "ai");
  /** Мій дубль для порівняння: затверджений (якщо це не ШІ), інакше останній власний. */
  const ownTake = (p) => { const a = p.takes.find((t) => t.file === p.approved && !t.deleted && t.source !== "ai"); return a || ownTakes(p).slice(-1)[0] || null; };
  const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);

  /** Позначка в списку реплік: є ШІ-варіанти, а власного дубля ще немає. */
  const cueMark = (p) => (p.ai && p.ai.length && !ownTakes(p).length
    ? `<br><span class="ai-mark" title="Є ШІ-варіанти (власних дублів ще немає)">ШІ ${p.ai.length}</span>` : "");

  function quality(v) {
    const sim = v.similarity, cer = v.cer;
    const simCls = sim == null ? "" : sim >= 0.9 ? "good" : sim >= 0.8 ? "long" : "bad";
    const cerCls = cer == null ? "" : cer <= 0.1 ? "good" : cer <= 0.3 ? "long" : "bad";
    return `<span class="ai-q ${simCls}" title="Схожість голосу на ваші дублі (косинус x-vector): ≥ 90 % — дуже схоже, < 80 % — схоже слабо">схожість ${pct(sim)}</span>
      <span class="ai-q ${cerCls}" title="Розбірливість: частка символів, які Whisper почув не так, як у тексті (CER). 0 % — ідеально">CER ${pct(cer)}</span>`;
  }

  /** Параметри варіанта (з побічного json): коротко + повний json у розкривному блоці. */
  function paramsLine(v) {
    const q = v.params;
    if (!q) return "";
    const refs = (v.refs || []).map((r) => `${r.take}${r.approved ? "" : " (не затв.)"}`).join(", ");
    return `<details class="ai-params"><summary>параметри: seed ${esc(v.seed ?? q.seed ?? "—")} · варіативність ${esc(q.variability ?? "—")}${q.style ? ` · стиль ${esc(q.style)}` : ""}${refs ? ` · референси: ${esc(refs)}` : ""}</summary>
      <pre>${esc(JSON.stringify({ params: q, license: v.license, refs: v.refs }, null, 2))}</pre></details>`;
  }

  function row(p, v) {
    const id = "ai:" + v.file, own = ownTake(p);
    return `<div class="take ai-take ${v.adopted ? "adopted" : ""}" data-ai-row="${esc(v.file)}">
      <button class="play" data-play="${esc(id)}" title="Послухати ШІ-варіант (клавіша ${v.n})">▶</button>
      <div><div class="take-head"><span class="badge-ai" title="Згенеровано ШІ з вашим голосом${v.license ? `. Ліцензія результату: ${esc(v.license)}` : ""}">ШІ${v.license ? ` · ${esc(shortLic(v.license))}` : ""}</span><b>Варіант ${v.n}</b>
        <span class="ai-engine">${esc(v.engine || "")}</span>
        <span class="fit">${v.dur != null ? fmt(v.dur) : ""}</span>${quality(v)}
        ${v.style ? `<span class="ai-style" title="Стильова підказка з «Як грати»">${esc(v.style)}</span>` : ""}
        ${v.adopted ? `<span class="ai-adopted" title="Уже скопійовано у ваші дублі">У ДУБЛЯХ</span>` : ""}</div>
        <div class="wave-box"><canvas class="wave" data-wave="${esc(id)}"></canvas></div>${paramsLine(v)}</div>
      <div class="take-actions">
        <button class="btn" data-ai-ab-ref="${esc(v.file)}" title="Спершу оригінал, потім ШІ-варіант">Оригінал → ШІ</button>
        <button class="btn" data-ai-ab-own="${esc(v.file)}" ${own ? "" : "disabled"} title="${own ? `Мій дубль ${own.n}, потім ШІ-варіант (Shift+${v.n})` : "Власних дублів ще немає"}">Мій дубль ↔ ШІ</button>
        <button class="btn" data-ai-again="${esc(v.file)}" title="Ще один варіант: ті самі параметри, новий seed">Ще варіант</button>
        <button class="btn" data-ai-based="${esc(v.file)}" ${v.params ? "" : "disabled"} title="${v.params ? "Скопіювати параметри цього варіанта у форму «Згенерувати»" : "У цього варіанта немає збережених параметрів"}">На основі цього</button>
        <button class="btn primary" data-ai-adopt="${esc(v.file)}" ${v.adopted ? "disabled" : ""} title="Скопіювати в дублі як новий дубль (з позначкою ШІ); далі — як будь-який дубль">Взяти в дублі</button>
        <button class="btn icon" data-ai-discard="${esc(v.file)}" title="Сховати цей варіант">✕</button></div></div>`;
  }

  async function drawWaves(p, sec) {
    for (const v of p.ai) {
      const c = sec.querySelector(`canvas[data-wave="${CSS.escape("ai:" + v.file)}"]`);
      if (!c) continue;
      try {
        const b = await loadBuf(urlAi(v.file));
        if (cur() !== p || !c.isConnected) return;
        waves.set("ai:" + v.file, { canvas: c, buf: b, opts: { color: "#7a5fb5", played: "#b39ae8", scale: Math.max(p.ru_dur || 0, b.duration) } });
        drawWave("ai:" + v.file);
      } catch (e) { console.warn("wave ai", e); }
    }
  }

  async function adopt(p, file) {
    const where = ids(p), res = await act("/api/ai/adopt", { lid: p.id, file });
    if (!res) return;
    const t = res.takes.filter((x) => x.source === "ai").slice(-1)[0];
    putPhrase(where, res, t && t.file);
    toast(`ШІ-варіант взято в дублі як Дубль ${t ? t.n : "?"} (позначка «ШІ»)`);
  }
  async function discard(p, file) {
    stopPlay();
    const where = ids(p), res = await act("/api/ai/discard", { lid: p.id, file });
    if (res) putPhrase(where, res);
  }

  function bind(p, sec) {
    sec.onclick = (e) => {
      const b = e.target.closest("button, canvas");
      if (!b) return;
      e.stopPropagation();                                   // не дійти до обробника дублів у card.js
      const d = b.dataset, own = ownTake(p);
      if (d.play || d.wave) {
        const id = d.play || d.wave;
        return playing && playing.id === id ? stopPlay() : play([aiItem(id.slice(3))]);
      }
      if (d.aiAbRef) return play([{ url: urlRef(p), id: "ref" }, aiItem(d.aiAbRef)]);
      if (d.aiAbOwn && own) return play([takeItem(p, own.file), aiItem(d.aiAbOwn)]);
      if (d.aiAgain) return again(p, d.aiAgain);
      if (d.aiBased) return basedOn(p, d.aiBased, () => mountPanel(p, sec.querySelector(".ai-gen-host")));
      if (d.aiAdopt) return adopt(p, d.aiAdopt);
      if (d.aiDiscard) return discard(p, d.aiDiscard);
    };
  }

  const listHtml = (p) => (p.ai.length ? p.ai.map((v) => row(p, v)).join("") : `<p class="ai-note">Варіантів ще немає — відкрийте «✨ Згенерувати».</p>`);

  function mountPanel(p, host) {
    if (AIS.status) return mountGen(p, host);
    host.innerHTML = `<p class="ai-note">Завантаження налаштувань ШІ…</p>`;
    loadStatus().then(() => { if (host.isConnected && cur() === p) mountGen(p, host); })
      .catch((e) => { host.innerHTML = `<p class="ai-warn">ШІ недоступний: ${esc(e.message)}</p>`; });
  }

  /** Перемальовує лише список варіантів (панель і фокус у формі не чіпаємо). */
  function renderList(p) {
    const sec = document.querySelector("#aiSection");
    if (!sec) return;
    sec.querySelector(".ai-count").textContent = `${p.ai.length} · голос ШІ, клонований з ваших дублів`;
    sec.querySelector(".takes").innerHTML = listHtml(p);
    drawWaves(p, sec);
  }

  function mount(p) {
    document.querySelector("#aiSection")?.remove();
    const anchor = document.querySelector("#main .rec-zone");
    if (!anchor) return;
    const sec = document.createElement("div");
    sec.id = "aiSection"; sec.className = "ai-section";
    sec.innerHTML = `<div class="section-h"><h3>ШІ-варіанти</h3><span class="ai-count"></span>
        <span class="ai-keys"><kbd>1</kbd><kbd>2</kbd><kbd>3</kbd> слухати · <kbd>⇧</kbd>+<kbd>1</kbd>… мій дубль ↔ ШІ</span></div>
      <div class="ai-gen-host"></div>
      <div class="takes"></div>
      <p class="ai-note">Це синтез, а не запис. Для гри варіант треба «Взяти в дублі» (з’явиться дубль із позначкою «ШІ»), потім — «Обрати».</p>`;
    anchor.insertAdjacentElement("afterend", sec);
    bind(p, sec);
    mountPanel(p, sec.querySelector(".ai-gen-host"));
    renderList(p);
  }

  /** Черга щось змінила в поточній групі: підтягнути ШІ-варіанти поточної репліки (нові з’являються без перезавантаження). */
  onLine(async () => {
    const p = cur(), cid = S.cat, gid = S.unit;
    if (!p) return;
    try {
      const g = await getJSON(`/api/group/${cid}/${gid}`), ln = g.lines.find((x) => x.id === p.id);
      if (!ln || cid !== S.cat || gid !== S.unit || cur()?.id !== p.id) return;
      const sig = (a) => JSON.stringify(a.map((v) => [v.file, v.cer, v.similarity, v.adopted]));
      if (sig(ln.ai) === sig(p.ai)) return;
      p.ai = ln.ai;
      renderList(p); renderCues();
    } catch (e) { console.warn("ai refresh", e); }
  });

  // клавіатура: 1–3 — слухати варіант, Shift+1–3 — «мій дубль ↔ ШІ»
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, select, #eq") || e.metaKey || e.ctrlKey || e.altKey || Rec.on) return;
    const m = /^Digit([1-9])$/.exec(e.code), p = cur();
    const v = m && p && p.ai && p.ai.find((x) => x.n === +m[1]);
    if (!v) return;
    e.preventDefault();
    const own = ownTake(p);
    if (e.shiftKey && own) play([takeItem(p, own.file), aiItem(v.file)]);
    else if (!e.shiftKey) play([aiItem(v.file)]);
  });

  return { mount, cueMark };
})();
