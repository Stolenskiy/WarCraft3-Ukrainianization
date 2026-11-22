/* Перевантаження мікрофона (clipping). */
import { Rec } from "./rec.js";
import { $ } from "./util.js";

// Живо: відлік |x| ≥ 0.98 у воркліті → метр червоніє, у панелі запису — «перевантаження» (раз на дубль, без тостів).
// Після збереження сервер дає take.clipped/peak_db → червоний бейдж у рядку дубля й тост із порадою.
const CLIP_LEVEL = 0.98;

export const CLIP_ADVICE = "Голос «рве» мікрофон: відсуньтесь на 10–15 см або зменште гучність входу в Системних параметрах → Звук → Вхід";

const Clip = { take: null, flagged: false, timer: null };

export function clipCheck(buf) {
  if (Clip.take !== Rec.t0) { Clip.take = Rec.t0; Clip.flagged = false; $("#clipFlag")?.setAttribute("hidden", ""); }
  let hit = false;
  for (let i = 0; i < buf.length; i++) if (buf[i] >= CLIP_LEVEL || buf[i] <= -CLIP_LEVEL) { hit = true; break; }
  if (!hit) return;
  const m = $("#meter"); m?.classList.add("clip");
  clearTimeout(Clip.timer); Clip.timer = setTimeout(() => $("#meter")?.classList.remove("clip"), 700);
  if (!Clip.flagged) { Clip.flagged = true; $("#clipFlag")?.removeAttribute("hidden"); }
}
