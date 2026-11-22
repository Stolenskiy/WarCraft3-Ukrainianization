/* Спільний стан студії S і похідні (поточна репліка, адреси аудіо, мова оригіналу). */

export const S = { catalogs: [], lang: "ru", cat: null, unit: null, phrases: [], idx: 0, filter: "all", undo: null, busy: false };

export const ids = (p = cur()) => ({ cid: S.cat, gid: S.unit, lid: p.id });

export const cur = () => S.phrases[S.idx];

export const isDone = (p) => !!(p.approved || p.original);   // дубль обрано або залишено оригінал

export const aurl = (kind, name) => `/audio/${kind}/${S.cat}/${S.unit}/${encodeURIComponent(name)}`;

// мова оригіналу (налаштування в шапці): "ru" | "en"; якщо англійського файлу немає — рос.
// без російського мовного пакета (make refs) звучить лише англійський
export const refLang = (p) => ((S.lang === "en" && p.has_en) || !p.has_ru ? "en" : "ru");

export const urlRef = (p) => aurl(refLang(p) === "en" ? "ref-en" : "ref", p.id);

export const urlTake = (f) => aurl("take", f);

export const catOf = (cid = S.cat) => S.catalogs.find((c) => c.id === cid);

export const groupOf = (gid = S.unit, cid = S.cat) => catOf(cid)?.groups.find((g) => g.id === gid);
