/* Голосова картка над реплікою: чипи тембр / темп / манера з voice bible, ▶ еталон, поповер з повним текстом. */
import { play, playing, stopPlay } from "./audio.js";
import { S, groupOf, urlRef } from "./state.js";
import { $, esc } from "./util.js";

const first = (s) => s.split(/[;.]/)[0].trim();

/** traits ("Ключ: текст") → {chips, why, full}. Необов'язкове поле «Коротко: тембр | темп | манера» має перевагу. */
export function voiceInfo(traits = []) {
  const f = Object.fromEntries(traits.map((t) => { const [k, ...v] = t.split(": "); return [k, v.join(": ")]; }));
  const tim = f["Тембр"] || "", short = (f["Коротко"] || "").split("|").map((s) => s.trim());
  const parts = tim.split(";").map((s) => s.trim()).filter(Boolean);
  const pace = (tim.match(/[^,;.]*\bтемп[^,;.]*/i) || [""])[0].trim();
  const chips = [
    ["Тембр", short[0] || (parts[1] || parts[0] || "").split(",").slice(0, 2).join(",")],
    ["Темп", short[1] || pace],
    ["Манера", short[2] || first(f["Мовна манера"] || "")],
  ].filter(([, v]) => v);
  return { chips, why: tim, full: traits.filter((t) => !t.startsWith("Коротко")).map((t) => { const [k, ...r] = t.split(": "); return [k, r.join(": ")]; }) };
}

/** Еталон — перша репліка «what» (або перша з оригіналом): найхарактерніша, без команд бою. */
const refLine = () => S.phrases.find((p) => p.kind === "what" && (p.has_ru || p.has_en)) || S.phrases.find((p) => p.has_ru || p.has_en);

export function voiceHtml() {
  const g = groupOf(), v = voiceInfo(g ? g.traits : []), ref = refLine();
  if (!g || !g.traits.length) return `<div class="voice" id="voice"><span class="voice-k">Голос</span><span class="voice-none">Аркуша персонажа у voice bible ще немає.</span></div>`;
  return `<div class="voice" id="voice"><span class="voice-k">Голос</span>
    ${v.chips.map(([k, t]) => `<span class="vchip"><small>${k}</small> ${esc(t)}</span>`).join("")}
    ${ref ? `<button class="ghost vref" id="voiceRef" title="Найхарактерніша оригінальна репліка цього персонажа">▶ еталон</button>` : ""}
    <button class="linkish" id="voiceMore" aria-expanded="false" aria-controls="voiceFull">усе про персонажа</button>
    <div class="voice-full" id="voiceFull" role="region" aria-label="Про персонажа" hidden>${v.full.map(([k, t]) => `<p><b>${esc(k)}:</b> ${esc(t)}</p>`).join("")}</div></div>`;
}

export function voiceBind() {
  const more = $("#voiceMore"), full = $("#voiceFull");
  if (more) more.onclick = () => voiceToggle(full.hidden);
  const r = $("#voiceRef");
  if (r) r.onclick = () => { const p = refLine(); if (playing && playing.id === "voice-ref") return stopPlay(); play([{ url: urlRef(p), id: "voice-ref" }]); };
}

export function voiceToggle(show) {
  const more = $("#voiceMore"), full = $("#voiceFull");
  if (!more) return;
  full.hidden = !show; more.setAttribute("aria-expanded", String(show));
}

export const voiceWhy = () => voiceInfo(groupOf()?.traits).why;
