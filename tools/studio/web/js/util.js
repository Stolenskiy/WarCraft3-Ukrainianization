/* Дрібні утиліти без стану: DOM-селектор, екранування, формати. */

export const $ = (s, el = document) => el.querySelector(s);

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export const fmt = (s) => `${(+s).toFixed(2)} с`;

export const initials = (t) => t.replace(/[^\p{L}\s]/gu, "").trim().slice(0, 2);

export function timeLabel(iso) {
  if (!iso) return "";
  const t = new Date(iso), today = new Date().toDateString() === t.toDateString();
  return today ? t.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" }) : t.toLocaleString("uk-UA", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export const nFiles = (n) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? "файл" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? "файли" : "файлів"}`;

export const mb = (b) => (b / 1e6).toFixed(1) + " МБ";
