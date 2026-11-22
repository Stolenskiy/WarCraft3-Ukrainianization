/* Панель «✨ Згенерувати» у картці репліки: текст для ШІ, стиль/емоція, вибір голосу-референсу, варіативність, кількість,
   «Згенерувати» / «Ще варіант»; «Ще варіант» і «На основі цього» на кожному варіанті. Параметри, яких двигун не підтримує, вимкнено з підказкою. */
import { getJSON, post } from "./api.js";
import { play, playing, stopPlay } from "./audio.js";
import { SETUP_CMD, bindEngine, engineHtml, ensureConsents, fixHint } from "./ai-engine.js";
import { AIS, curEngine, draftOf, setEngine, supports } from "./ai-state.js";
import { kick, render as renderQueue } from "./ai-queue.js";
import { S, ids } from "./state.js";
import { toast } from "./toast.js";
import { esc, fmt } from "./util.js";

const NO = "двигун не підтримує цей параметр";
const INS = [["…", "…", "Крапки «…» — пауза"], ["!!!", "!!!", "Наголос інтонації"], ["́", "́", "Наголос на голосній перед курсором (U+0301)"], ["[pause]", " [pause] ", "Пауза"]];
const refCache = new Map();

const grp = (k, eng, body, cls = "") => `<div class="ai-f ${cls} ${supports(eng, k) ? "" : "unsup"}" data-param="${k}" ${supports(eng, k) ? "" : `title="${NO}"`}>${body}</div>`;
const dis = (k, eng) => (supports(eng, k) ? "" : "disabled");

function chips(eng, d) {
  const cur = d.style.trim();
  return AIS.status.schema.style_presets.map((s) => `<button type="button" class="ai-chip ${cur === s.tag ? "on" : ""}" data-chip="${esc(s.tag)}" ${dis("style", eng)}
    title="${esc(s.uk)} (${s.verified === "docs" ? "є в документації двигуна" : "перевірено в пілоті"})">${esc(s.tag)} <small>${esc(s.uk)}</small></button>`).join("");
}

function refRows(rows, d, max) {
  if (!rows) return `<p class="ai-note">Завантаження…</p>`;
  if (!rows.length) return `<p class="ai-note">Власних дублів ${d.filter === "approved" ? "із затвердженням " : ""}ще немає — запишіть дубль, і він стане референсом голосу.</p>`;
  return rows.map((r) => `<label class="ai-ref ${r.clipped ? "clip" : ""}"><input type="checkbox" data-ref="${esc(r.key)}" ${d.refs.includes(r.key) ? "checked" : ""}
      ${!d.refs.includes(r.key) && d.refs.length >= max ? "disabled" : ""}><button type="button" class="play mini" data-ref-play="${esc(r.key)}" title="Послухати">▶</button>
      <span class="ai-ref-t"><b>${esc(r.line.replace(/\.wav$/, ""))}</b> · дубль ${r.n} <small>${fmt(r.dur)}</small> ${esc(r.text || "")}</span>
      ${r.approved ? `<span class="ai-b com">затверджений</span>` : ""}${r.clipped ? `<span class="ai-b nc" title="Звук перевантажено — поганий референс">перевантаження</span>` : ""}${
      r.same_line ? `<span class="ai-b" title="Референс повторює цільовий текст: модель може просто відтворити його">та сама репліка</span>` : ""}</label>`).join("");
}

function html(p, eng, d) {
  const sc = AIS.status.schema, v = sc.variability;
  return `<div class="ai-gen-body"><div id="aiEngBox">${engineHtml()}</div>
    ${grp("text_override", eng, `<span class="ai-l">Текст для ШІ</span><textarea id="aiText" rows="2" maxlength="${sc.max_text}" ${dis("text_override", eng)}>${esc(d.text ?? p.ua ?? "")}</textarea>
      <span class="ai-ins">${INS.map(([l, t, h]) => `<button type="button" class="ghost" data-ins="${esc(t)}" title="${esc(h)}" ${dis("text_override", eng)}>${esc(l)}</button>`).join("")}
      <button type="button" class="ghost" data-text-reset title="Повернути текст репліки" ${dis("text_override", eng)}>↺ текст репліки</button></span>`)}
    ${grp("style", eng, `<span class="ai-l">Стиль / емоція</span><span class="ai-chips" id="aiChips">${chips(eng, d)}</span>
      <input id="aiStyle" value="${esc(d.style)}" placeholder="або своя англійська фраза: whisper" maxlength="40" ${dis("style", eng)}>`)}
    ${grp("ref_takes", eng, `<span class="ai-l">Голос-референс <small>(типово — автовибір затверджених; до ${sc.max_refs})</small></span>
      <span class="seg mini" id="aiRefFilter"><button type="button" data-rf="approved" class="${d.filter === "approved" ? "on" : ""}" ${dis("ref_takes", eng)}>Затверджені</button><button type="button" data-rf="all" class="${d.filter === "all" ? "on" : ""}" ${dis("ref_takes", eng)}>Усі мої дублі</button></span>
      <div class="ai-refs" id="aiRefs">${refRows(refCache.get(refKey(p, d)), d, sc.max_refs)}</div>`)}
    <div class="ai-row">${grp("variability", eng, `<label class="ai-l">Варіативність <output id="aiVarOut">${d.variability}</output></label>
        <input type="range" id="aiVar" min="${v.min}" max="${v.max}" step="0.05" value="${d.variability}" ${dis("variability", eng)}>`, "grow")}
      <div class="ai-f"><label class="ai-l" for="aiN">Варіантів</label><select id="aiN">${Array.from({ length: sc.max_n }, (_, i) => `<option ${d.n === i + 1 ? "selected" : ""}>${i + 1}</option>`).join("")}</select></div>
      ${grp("seed", eng, `<label class="ai-l" for="aiSeed">Seed</label><input id="aiSeed" type="number" min="0" placeholder="випадковий" value="${esc(d.seed)}" ${dis("seed", eng)}>`)}</div>
    <div class="ai-actions"><button class="btn primary" id="aiGo" data-ai-go>✨ Згенерувати</button>
      <button class="btn" id="aiMore" data-ai-more title="Ще один варіант із цими параметрами і новим seed">Ще варіант</button>
      <span class="ai-note" id="aiHint"></span></div></div>`;
}

const refKey = (p, d) => `${S.cat}/${S.unit}/${p.id}/${d.filter}`;

async function loadRefs(p, d, host) {
  const k = refKey(p, d);
  if (!refCache.has(k)) {
    const q = new URLSearchParams({ ...ids(p), approved: d.filter === "approved" ? "1" : "0" });
    try { refCache.set(k, await getJSON(`/api/ai/refs?${q}`)); } catch (e) { toast(e.message, true); refCache.set(k, []); }
  }
  const box = host.querySelector("#aiRefs");
  if (box && box.isConnected) box.innerHTML = refRows(refCache.get(k), d, AIS.status.schema.max_refs);
}

function collect(p, eng, d) {
  const q = { engine: eng.name, n: d.n };
  const t = (d.text ?? p.ua ?? "").trim();
  if (supports(eng, "text_override") && t && t !== (p.ua || "").trim()) q.text_override = t;
  if (supports(eng, "style") && d.style.trim()) q.style = d.style.trim().replace(/^\[|\]$/g, "");
  if (supports(eng, "ref_takes") && d.refs.length) q.ref_takes = d.refs;
  if (supports(eng, "variability")) q.variability = d.variability;
  if (supports(eng, "seed") && d.seed !== "") q.seed = +d.seed;
  return q;
}

/** Готовність → згоди → POST; усі відмови показуються тостом з точною підказкою. */
async function submit(p, params, path = "/api/ai/generate", extra = {}) {
  const eng = AIS.engines.find((e) => e.name === (params?.engine || AIS.engine)) || curEngine();
  if (!eng) return toast("Немає двигунів ШІ", true);
  if (eng.status.state !== "ready") {
    return toast(`Двигун «${eng.title}» не готовий: ${eng.status.state === "missing_key" ? "потрібен ключ API" : `виконайте ${SETUP_CMD}`}`, true, 9000);
  }
  if (!(await ensureConsents(eng))) return null;
  try {
    const job = await post(path, { ...ids(p), ...extra, ...(params ? { params } : {}) });
    (job.warnings || []).forEach((w) => toast(w, false, 7000));
    toast(`У черзі ШІ: ${job.params.n} ${job.params.n === 1 ? "варіант" : "варіанти"} · результат ${job.license}`);
    kick();
    return job;
  } catch (e) { toast(e.message, true, 9000); return null; }
}

export const again = (p, file) => submit(p, null, "/api/ai/again", { file });

/** «На основі цього»: параметри варіанта → форма (нічого не запускає). */
export async function basedOn(p, file, rerender) {
  try {
    const q = await post("/api/ai/based-on", { ...ids(p), file }), d = draftOf(p);
    Object.assign(d, { open: true, text: q.text_override ?? null, style: q.style || "", variability: q.variability ?? 0.5,
      n: q.n || 1, seed: q.seed ?? "", refs: q.ref_takes || [] });
    if (AIS.engines.some((e) => e.name === q.engine)) setEngine(q.engine);
    rerender();
    toast("Параметри варіанта скопійовано у форму «Згенерувати»");
    document.querySelector("#aiSection details.ai-gen")?.scrollIntoView({ block: "nearest" });
  } catch (e) { toast(e.message, true); }
}

export function mountGen(p, host) {
  refCache.clear();                      // дублі могли змінитись — список референсів завантажимо знову
  const d = draftOf(p);
  const render = () => {
    host.innerHTML = `<details class="ai-gen" ${d.open ? "open" : ""}><summary>✨ Згенерувати</summary><div id="aiGenBody"></div></details>
      <div class="ai-line-prog" id="aiLineProg" data-lid="${esc(p.id)}" hidden></div>`;   // під кнопкою — там, де з’являться варіанти
    renderQueue();
    body();
  };
  const body = () => {
    const eng = curEngine(), b = host.querySelector("#aiGenBody");
    if (!eng) { b.innerHTML = engineHtml(); return; }
    b.innerHTML = html(p, eng, d);
    bindEngine(b.querySelector("#aiEngBox"), () => { body(); });
    if (supports(eng, "ref_takes")) loadRefs(p, d, host);
    const hint = b.querySelector("#aiHint");
    hint.innerHTML = eng.status.state === "ready" ? "" : fixHint(eng);
    if (!AIS.status.consent) hint.textContent = "Перед першою генерацією потрібна згода «це мій власний голос».";
  };
  render();
  host.querySelector("details").ontoggle = (e) => { d.open = e.target.open; };
  host.oninput = (e) => {
    const t = e.target;
    if (t.id === "aiText") d.text = t.value;
    if (t.id === "aiStyle") { d.style = t.value; host.querySelectorAll("[data-chip]").forEach((c) => c.classList.toggle("on", c.dataset.chip === t.value.trim())); }
    if (t.id === "aiVar") { d.variability = +t.value; host.querySelector("#aiVarOut").textContent = t.value; }
    if (t.id === "aiN") d.n = +t.value;
    if (t.id === "aiSeed") d.seed = t.value;
  };
  host.onchange = (e) => {
    const t = e.target;
    if (t.id === "aiN") d.n = +t.value;
    if (t.dataset.ref) { d.refs = t.checked ? [...d.refs, t.dataset.ref] : d.refs.filter((r) => r !== t.dataset.ref); loadRefs(p, d, host); }
  };
  host.onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const x = b.dataset, eng = curEngine();
    if (x.chip) { d.style = d.style.trim() === x.chip ? "" : x.chip; host.querySelector("#aiStyle").value = d.style; host.querySelector("#aiChips").innerHTML = chips(eng, d); }
    else if (x.ins != null) {
      const ta = host.querySelector("#aiText"), s = ta.selectionStart, en = ta.selectionEnd;
      ta.setRangeText(x.ins, s, en, "end"); d.text = ta.value; ta.focus();
    } else if (b.matches("[data-text-reset]")) { d.text = null; host.querySelector("#aiText").value = p.ua || ""; }
    else if (x.rf) { d.filter = x.rf; host.querySelectorAll("[data-rf]").forEach((r) => r.classList.toggle("on", r.dataset.rf === x.rf)); loadRefs(p, d, host); }
    else if (x.refPlay) {
      const r = (refCache.get(refKey(p, d)) || []).find((z) => z.key === x.refPlay);
      if (!r) return;
      const id = "airef:" + r.key;
      if (playing && playing.id === id) stopPlay();
      else play([{ url: `/audio/take/${S.cat}/${encodeURIComponent(r.gid)}/${encodeURIComponent(r.take)}`, id }]);
    } else if (b.matches("[data-ai-go]")) submit(p, collect(p, eng, d));
    else if (b.matches("[data-ai-more]")) submit(p, { ...collect(p, eng, d), n: 1, seed: undefined });
  };
}

