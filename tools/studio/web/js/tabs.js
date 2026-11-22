/* Вкладки бічної панелі «Репліки | Обробка»: кожна має власний скрол, неактивна лишається в DOM (scrollTop зберігається). */
import { $ } from "./util.js";

const TABS = ["Cues", "Proc"];

export function showTab(name) {
  for (const t of TABS) {
    const on = t === name, tab = $("#tab" + t), pane = $("#pane" + t);
    tab.classList.toggle("on", on); tab.setAttribute("aria-selected", on); tab.tabIndex = on ? 0 : -1;
    pane.classList.toggle("on", on); pane.inert = !on;
  }
}

$(".side-tabs").addEventListener("click", (e) => { const b = e.target.closest("[role=tab]"); if (b) showTab(b.id.slice(3)); });
$(".side-tabs").addEventListener("keydown", (e) => {          // ←/→ між вкладками; ↑/↓ лишаються за списком реплік
  if (e.code !== "ArrowLeft" && e.code !== "ArrowRight") return;
  e.preventDefault(); e.stopPropagation();
  const name = TABS[(TABS.indexOf($("[role=tab].on").id.slice(3)) + (e.code === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
  showTab(name); $("#tab" + name).focus();
});
