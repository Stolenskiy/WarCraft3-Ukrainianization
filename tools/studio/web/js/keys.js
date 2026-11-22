/* Глобальні гарячі клавіші. */
import { play } from "./audio.js";
import { toggleUnitPopover } from "./catalog.js";
import { nextTodo, select, step } from "./cues.js";
import { eqToggleAB } from "./eq-live.js";
import { Rec, toggleRec } from "./rec.js";
import { cur, urlRef } from "./state.js";
import { keepOriginal } from "./takes.js";
import { runUndo } from "./toast.js";
import { takeItem } from "./trim.js";
import { voiceToggle } from "./voice-card.js";

document.addEventListener("keydown", (e) => {
  if (!e.target.matches("#eq input[type=range], #eq .eq-node") && e.target.closest("input, textarea, select, summary, .trim-h, #eq")) return;  // елементи керування мають свої клавіші (повзунки EQ — див. eqSetup)
  if ((e.metaKey || e.ctrlKey) && e.code === "KeyZ") { e.preventDefault(); return runUndo(); }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.code === "Escape") { voiceToggle(false); return toggleUnitPopover(false); }
  if (e.code === "Space") { e.preventDefault(); return toggleRec(); }
  if (Rec.on) return;
  const p = cur(); if (!p) return;
  const last = p.takes.filter((t) => !t.deleted && t.exists).slice(-1)[0];
  switch (e.code) {
    case "KeyR": play([{ url: urlRef(p), id: "ref" }]); break;
    case "KeyL": if (last) play([takeItem(p, last.file)]); break;
    case "KeyB": if (last) play([{ url: urlRef(p), id: "ref" }, takeItem(p, last.file)]); break;
    case "KeyA": eqToggleAB(); break;
    case "KeyN": nextTodo(); break;
    case "KeyO": keepOriginal(p); break;
    case "ArrowDown": e.preventDefault(); step(1); break;
    case "ArrowUp": e.preventDefault(); step(-1); break;
  }
});

document.addEventListener("click", (e) => { if (!e.target.closest(".voice")) voiceToggle(false); });
