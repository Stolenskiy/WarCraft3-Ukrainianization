/* Шапка: меню розділеної кнопки «Встановити в гру ▾» і висувна бічна панель (< 1000 px). */
import { getJSON } from "./api.js";
import { $ } from "./util.js";

const nAuthors = (n) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? "автор" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? "автори" : "авторів"}`;

export function toggleMenu(show) {
  const m = $("#installMenu"), b = $("#installMenuBtn");
  show = show ?? m.hidden;
  m.hidden = !show; b.setAttribute("aria-expanded", String(show));
  if (show) {
    m.querySelector("button").focus();
    getJSON("/api/voices").then((v) => { $("#voicesCount").textContent = nAuthors(v.authors.length); }).catch(() => {});
  }
}

export function toggleSide(show) {
  show = show ?? !document.body.classList.contains("side-open");
  document.body.classList.toggle("side-open", show);
  $("#sideScrim").hidden = !show; $("#sideToggle").setAttribute("aria-expanded", String(show));
}

$("#installMenuBtn").addEventListener("click", () => toggleMenu());
$("#installMenu").addEventListener("click", () => toggleMenu(false));      // будь-який пункт закриває меню; свою дію він виконує сам
$("#installMenu").addEventListener("keydown", (e) => {
  const items = [...$("#installMenu").querySelectorAll("button")], i = items.indexOf(document.activeElement);
  if (e.code === "ArrowDown") items[(i + 1) % items.length].focus();
  else if (e.code === "ArrowUp") items[(i + items.length - 1) % items.length].focus();
  else if (e.code === "Escape") { toggleMenu(false); $("#installMenuBtn").focus(); }
  else return;
  e.preventDefault(); e.stopPropagation();
});
document.addEventListener("click", (e) => { if (!e.target.closest("#installSplit")) toggleMenu(false); });
$("#sideToggle").addEventListener("click", () => toggleSide());
$("#sideScrim").addEventListener("click", () => toggleSide(false));
$("#side").addEventListener("click", (e) => { if (e.target.closest(".cue")) toggleSide(false); });
document.addEventListener("keydown", (e) => { if (e.code === "Escape") toggleSide(false); });
