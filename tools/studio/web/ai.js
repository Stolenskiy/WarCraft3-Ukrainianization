"use strict";
/* ШІ-варіанти реплік (голос ШІ, клонований із ВЛАСНИХ дублів користувача). Підключається після app.js.
   Хуки в app.js: AI.mount(p) в кінці renderCard, AI.cueMark(p) у renderCues. Усе інше — тут.
   Дані: p.ai = [{file, n, engine, cer, similarity, dur, style, adopted}], аудіо — /audio/ai/<cid>/<gid>/<file>. */

const AI = (() => {
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

  function row(p, v) {
    const id = "ai:" + v.file, own = ownTake(p);
    return `<div class="take ai-take ${v.adopted ? "adopted" : ""}" data-ai-row="${esc(v.file)}">
      <button class="play" data-play="${esc(id)}" title="Послухати ШІ-варіант (клавіша ${v.n})">▶</button>
      <div><div class="take-head"><span class="badge-ai" title="Згенеровано ШІ з вашим голосом">ШІ</span><b>Варіант ${v.n}</b>
        <span class="ai-engine">${esc(v.engine || "")}</span>
        <span class="fit">${v.dur != null ? fmt(v.dur) : ""}</span>${quality(v)}
        ${v.style ? `<span class="ai-style" title="Стильова підказка з «Як грати»">${esc(v.style)}</span>` : ""}
        ${v.adopted ? `<span class="ai-adopted" title="Уже скопійовано у ваші дублі">У ДУБЛЯХ</span>` : ""}</div>
        <div class="wave-box"><canvas class="wave" data-wave="${esc(id)}"></canvas></div></div>
      <div class="take-actions">
        <button class="btn" data-ai-ab-ref="${esc(v.file)}" title="Спершу оригінал, потім ШІ-варіант">Оригінал → ШІ</button>
        <button class="btn" data-ai-ab-own="${esc(v.file)}" ${own ? "" : "disabled"} title="${own ? `Мій дубль ${own.n}, потім ШІ-варіант (Shift+${v.n})` : "Власних дублів ще немає"}">Мій дубль ↔ ШІ</button>
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
      e.stopPropagation();                                   // не дійти до обробника дублів у app.js
      const d = b.dataset, own = ownTake(p);
      if (d.play || d.wave) {
        const id = d.play || d.wave;
        return playing && playing.id === id ? stopPlay() : play([aiItem(id.slice(3))]);
      }
      if (d.aiAbRef) return play([{ url: urlRef(p), id: "ref" }, aiItem(d.aiAbRef)]);
      if (d.aiAbOwn && own) return play([takeItem(p, own.file), aiItem(d.aiAbOwn)]);
      if (d.aiAdopt) return adopt(p, d.aiAdopt);
      if (d.aiDiscard) return discard(p, d.aiDiscard);
    };
  }

  function mount(p) {
    document.querySelector("#aiSection")?.remove();
    if (!p.ai || !p.ai.length) return;
    const anchor = document.querySelector("#main .rec-zone");
    if (!anchor) return;
    const sec = document.createElement("div");
    sec.id = "aiSection"; sec.className = "ai-section";
    sec.innerHTML = `<div class="section-h"><h3>ШІ-варіанти</h3><span>${p.ai.length} · голос ШІ, клонований з ваших дублів</span>
        <span class="ai-keys"><kbd>1</kbd><kbd>2</kbd><kbd>3</kbd> слухати · <kbd>⇧</kbd>+<kbd>1</kbd>… мій дубль ↔ ШІ</span></div>
      <div class="takes">${p.ai.map((v) => row(p, v)).join("")}</div>
      <p class="ai-note">Це синтез, а не запис. Для гри варіант треба «Взяти в дублі» (з’явиться дубль із позначкою «ШІ»), потім — «Обрати».</p>`;
    anchor.insertAdjacentElement("afterend", sec);
    bind(p, sec);
    drawWaves(p, sec);
  }

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
