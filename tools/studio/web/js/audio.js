/* Web Audio: контекст, декодування, програвання черги, «Як у грі». */
import { charUrl } from "./character.js";
import { EQ, eqChip, eqConnect, eqMatch } from "./eq-live.js";
import { S } from "./state.js";
import { toast } from "./toast.js";
import { sleep } from "./util.js";
import { drawWave } from "./wave.js";

export const AC = new (window.AudioContext || window.webkitAudioContext)();

// Контекст «будимо» синхронно в будь-якому жесті: після await (діалог дозволу мікрофона)
// браузер уже не вважає це дією користувача, і resume() зависає.
for (const ev of ["pointerdown", "keydown"]) document.addEventListener(ev, () => { if (AC.state !== "running") AC.resume(); }, true);

// Декодуємо в OfflineAudioContext — працює навіть коли AC ще «спить» або немає виходу звуку.
export const DEC = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, 1, 44100);

export const bufCache = new Map();

export function loadBuf(url) {
  if (!bufCache.has(url)) {
    bufCache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error("audio " + r.status); return r.arrayBuffer(); })
      .then((b) => DEC.decodeAudioData(b)).catch((e) => { bufCache.delete(url); throw e; }));
  }
  return bufCache.get(url);
}

export let playToken = null, playing = null; // playing: {id, src, t0, dur}
let tail = null;                              // «голос персонажа» (друге джерело) може звучати довше за дубль: хвіст простору
const CHAR_TAIL = 1.2;                        // с, скільки хвоста дозволити після кінця дубля

export async function play(items) {
  stopPlay();
  const token = {};
  playToken = token;
  if (AC.state !== "running") AC.resume();
  for (const it of items) {
    let buf;
    try { buf = await loadBuf(it.url); } catch { toast("Не вдалося відкрити аудіо", true); return; }
    if (it.nocache) bufCache.delete(it.url);           // «Як у грі»: той самий url не тримаємо, налаштування могли змінитись
    if (playToken !== token) return;
    let wbuf = null, key = it.url;
    if (String(it.id).startsWith("take:")) {         // EQ і пресет персонажа мають встигнути завантажитись
      await S.eqReady;
      const cu = await charUrl(it.id.slice(5));
      if (cu) { try { wbuf = await loadBuf(cu); key = cu; } catch { toast("Голос персонажа не підготувався — звучить без нього", true); } }
      if (EQ.prof && (EQ.prof.enabled || wbuf)) await eqMatch(buf, key, wbuf);
      if (playToken !== token) return;
    }
    await new Promise((res) => {
      const src = AC.createBufferSource(), w = wbuf && AC.createBufferSource();
      src.buffer = buf; if (w) w.buffer = wbuf;
      eqConnect(src, it.id, buf, key, w, wbuf); src.onended = res;
      const off = it.start || 0, len = (it.end ?? buf.duration) - off; // ручне обрізання дубля
      playing = { id: it.id, src, t0: AC.currentTime, dur: len, off, full: buf.duration };
      src.start(0, off, len);
      if (w && off < wbuf.duration) { tail = w; w.start(0, off, Math.min(wbuf.duration - off, len + CHAR_TAIL)); }
      markPlaying();
    });
    if (playToken !== token) return;
    if (playing) drawWave(playing.id);
    playing = null; markPlaying();
    await sleep(220);
  }
}

export function stopPlay() {
  playToken = null;
  if (tail) { try { tail.stop(); } catch {} tail = null; }
  if (playing) { try { playing.src.onended = null; playing.src.stop(); } catch {} drawWave(playing.id); playing = null; }
  markPlaying();
}

export function markPlaying() {
  if (!playing) EQ.live = null;
  document.querySelectorAll("[data-play]").forEach((b) => {
    const on = playing && b.dataset.play === playing.id;
    b.classList.toggle("playing", !!on); b.textContent = on ? "■" : "▶";
  });
  eqChip();
}

(function anim() {
  if (playing) drawWave(playing.id, ((playing.off || 0) + AC.currentTime - playing.t0) / (playing.full || playing.dur));
  requestAnimationFrame(anim);
})();

/** «Як у грі» для будь-якого дубля: сервер збирає той самий ланцюжок, що й копія для гри (EQ уже всередині). */
export function playPreview(p, file) {
  const id = "preview:" + file;
  if (playing && playing.id === id) return stopPlay();
  const q = new URLSearchParams({ cid: S.cat, gid: S.unit, lid: p.id, file, v: Date.now() });
  play([{ url: `/api/preview?${q}`, id, nocache: true }]);
}
