/* Спільний стан ШІ-студії на фронті: статус і двигуни з /api/ai/status, чернетки форми «Згенерувати» (по одній на репліку). */
import { getJSON } from "./api.js";
import { S } from "./state.js";

export const AIS = { status: null, engines: [], engine: null, drafts: new Map() };

const STATE_UA = { ready: "готово", missing_model: "нема моделі", missing_key: "нема ключа", missing_env: "нема середовища" };
export const stateUa = (st) => STATE_UA[st] || st;

export async function loadStatus() {
  AIS.status = await getJSON("/api/ai/status");
  AIS.engines = AIS.status.engines;
  let saved = null;
  try { saved = localStorage.getItem("studio.aiEngine"); } catch { /* приватний режим */ }
  if (!AIS.engines.some((e) => e.name === AIS.engine)) {
    AIS.engine = [saved, AIS.status.schema.defaults.engine].find((n) => AIS.engines.some((e) => e.name === n)) || AIS.engines[0]?.name;
  }
  return AIS.status;
}

export const curEngine = () => AIS.engines.find((e) => e.name === AIS.engine) || AIS.engines[0] || null;

export function setEngine(name) {
  AIS.engine = name;
  try { localStorage.setItem("studio.aiEngine", name); } catch { /* не критично */ }
}

export function patchEngine(e) {
  const i = AIS.engines.findIndex((x) => x.name === e.name);
  if (i >= 0) AIS.engines[i] = e;
}

export const supports = (eng, k) => !!eng && eng.supports.includes(k);

export const lineKey = (p) => `${S.cat}/${S.unit}/${p.id}`;

/** Чернетка форми для репліки: text=null — «текст репліки»; refs=[] — автовибір затверджених. */
export function draftOf(p) {
  const k = lineKey(p);
  if (!AIS.drafts.has(k)) AIS.drafts.set(k, { open: false, text: null, style: "", variability: 0.5, n: 1, refs: [], filter: "approved", seed: "" });
  return AIS.drafts.get(k);
}

/** «CC BY-NC 4.0» → «CC BY-NC» для бейджа. */
export const shortLic = (l) => String(l || "").replace(/\s+\d+(\.\d+)?$/, "");
