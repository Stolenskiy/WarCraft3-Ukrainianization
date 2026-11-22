/* Макроси простого режиму: маленька зміна поверх профілю (видно на кривій). */
import { EQ } from "./eq-live.js";

// [тип, частота Гц, підсилення дБ, Q]; якщо поруч уже є смуга того ж типу — додаємо до неї, інакше нова смуга
export const MACROS = {
  warm: ["Тепліше", [["lowshelf", 200, 2, 0.71]]],
  bright: ["Яскравіше", [["peaking", 3000, 2, 1]]],
  dense: ["Щільніше", [["peaking", 150, 2, 0.9], ["peaking", 400, -1.5, 1]]],
  clean: ["Чистіше", [["peaking", 300, -2, 1]]],
};

export function applyMacro(key) {
  for (const [type, freq_hz, gain, q] of MACROS[key][1]) {
    const near = EQ.prof.bands.find((b) => b.type === type && Math.abs(Math.log(b.freq_hz / freq_hz)) < 0.2);
    if (near) near.gain_db = Math.max(-12, Math.min(12, Math.round((near.gain_db + gain) * 10) / 10));
    else if (EQ.prof.bands.length < 8) EQ.prof.bands.push({ type, freq_hz, gain_db: gain, q });
  }
}
