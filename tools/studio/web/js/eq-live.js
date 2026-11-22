/* Еквалайзер: живий граф Web Audio (dry/wet), вирівнювання A/B за гучністю, чип на дублі. */
import { AC, play, playing } from "./audio.js";
import { eqRender } from "./eq-panel.js";
import { esc } from "./util.js";

// Профіль {name, enabled, gain_db, amount, bands:[{type,freq_hz,gain_db,q}]} (дані й ffmpeg — eq.py).
// Прослуховування дублів іде через BiquadFilterNode з тими самими параметрами; файл для гри
// змінюється лише кнопкою «Оновити файли гри».
export const EQ = { data: null, id: null, prof: null, bypass: false, live: null, naming: false, sel: 0, mode: "simple" };

export const eqClone = (o) => JSON.parse(JSON.stringify(o));

export const eqOwn = () => EQ.data && EQ.data.profiles.find((p) => p.id === EQ.id && !p.builtin);

export const eqDirty = () => { const b = EQ.data && EQ.data.profiles.find((p) => p.id === EQ.id); return !!b && JSON.stringify(eqPlain(b)) !== JSON.stringify(eqPlain(EQ.prof)); };

export const eqPlain = (p) => ({ name: p.name, enabled: p.enabled, gain_db: p.gain_db, amount: p.amount ?? 1, bands: p.bands });

function eqNodeSpec(b) {  // Web Audio: Q фільтрів HP/LP — у дБ
  return { type: b.type, frequency: b.freq_hz, gain: b.gain_db, Q: b.type === "highpass" || b.type === "lowpass" ? 20 * Math.log10(b.q) : b.q };
}

/** «Сила» профілю множить підсилення смуг (як у eq.to_ffmpeg), стеля ±12 дБ. */
export function eqApply(node, b, amount = EQ.prof ? EQ.prof.amount ?? 1 : 1) {
  const s = eqNodeSpec(b);
  node.type = s.type; node.frequency.value = s.frequency; node.gain.value = Math.max(-12, Math.min(12, s.gain * amount)); node.Q.value = s.Q;
}

// Граф дубля завжди: src → dry → вихід, та wsrc → [EQ-ланцюг] → wet → вихід (wsrc — «голос персонажа» з сервера,
// синхронне друге джерело; без пресета wsrc = src). A/B і зміна профілю лише перемикають гучність dry/wet
// (setTargetAtTime), тож працюють і на дублі, що вже звучить (eqRewire). A = персонаж + EQ, B = сирий дубль.
const eqOn = () => !!EQ.prof && EQ.prof.enabled && EQ.prof.amount !== 0;
const eqActive = (l = EQ.live) => !EQ.bypass && (eqOn() || !!(l && l.wsrc !== l.src));

const EQ_RAMP = 0.015;   // стала часу перемикання, с

export function eqConnect(src, id, buf, url, wsrc = null, wbuf = null) {
  EQ.live = null;
  if (!String(id).startsWith("take:") || !EQ.prof) {          // без EQ (не завантажився): A/B немає
    if (wsrc) { const mute = AC.createGain(); mute.gain.value = 0; src.connect(mute).connect(AC.destination); }
    (wsrc || src).connect(AC.destination); return;
  }
  const dry = AC.createGain(), wet = AC.createGain();
  dry.gain.value = wet.gain.value = 0;
  src.connect(dry); dry.connect(AC.destination); wet.connect(AC.destination);
  EQ.live = { src, wsrc: wsrc || src, wbuf, dry, wet, nodes: [], vol: null, head: null, n: undefined, buf, url };
  eqRewire();
}

export function eqRewire() {  // стан EQ (увімкнено / A-B / профіль) → живий граф і чип
  const l = EQ.live;
  if (!l || !EQ.prof) return eqChip();
  const on = eqActive(l), P = EQ.prof, want = eqOn() ? P.bands.length : -1;
  if (on ? l.n !== want : l.n === undefined) {   // змінилась кількість смуг, EQ увімкнули/вимкнули або перша збірка
    if (l.head) { try { l.wsrc.disconnect(l.head); } catch {} }
    [...l.nodes, l.vol].forEach((n) => { try { n && n.disconnect(); } catch {} });
    if (on && want >= 0) {
      l.nodes = P.bands.map((b) => { const n = AC.createBiquadFilter(); eqApply(n, b); return n; });
      l.vol = AC.createGain();
      const chain = [l.wsrc, ...l.nodes, l.vol, l.wet];
      chain.reduce((x, n) => (x.connect(n), n));
      l.head = chain[1]; l.n = P.bands.length;
    } else { l.nodes = []; l.vol = null; l.wsrc.connect(l.wet); l.head = l.wet; l.n = -1; }
  }
  if (on) eqLiveUpdate();
  const t = AC.currentTime;
  l.wet.gain.setTargetAtTime(on ? 1 : 0, t, EQ_RAMP);
  l.dry.gain.setTargetAtTime(on ? 0 : eqMatched(l), t, EQ_RAMP);   // B (без EQ) вирівняно за гучністю з A
  if (!on && l.buf && !eqMatchVal.has(eqMatchKey(l.url))) eqMatch(l.buf, l.url, l.wbuf).then(() => { if (EQ.live === l) eqRewire(); });
  eqChip();
}

export function eqLiveUpdate() {  // слайдери під час прослуховування
  const l = EQ.live;
  if (!l || !l.vol || l.nodes.length !== EQ.prof.bands.length) return;
  EQ.prof.bands.forEach((b, i) => eqApply(l.nodes[i], b));
  l.vol.gain.value = Math.pow(10, EQ.prof.gain_db / 20);
}

// Вирівнювання A/B за гучністю: RMS(дубль [голос персонажа] через EQ) / RMS(дубль), раз на (дубль, профіль, пресет)
const eqMatchVal = new Map(), eqMatchJobs = new Map();

const eqMatchKey = (url) => url + "|" + JSON.stringify(eqPlain(EQ.prof));

const eqMatched = (l) => (l.url && eqMatchVal.get(eqMatchKey(l.url))) || 1;

export function eqMatch(buf, url, wbuf = null) {
  const key = eqMatchKey(url);
  if (!eqMatchJobs.has(key)) {
    const P = eqClone(EQ.prof), useEq = P.enabled && (P.amount ?? 1) !== 0, a = wbuf || buf;
    eqMatchJobs.set(key, (async () => {
      let g = 1;
      try {
        const oc = new OfflineAudioContext(a.numberOfChannels, a.length, a.sampleRate);
        const s = oc.createBufferSource(); s.buffer = a;
        const nodes = useEq ? P.bands.map((b) => { const n = oc.createBiquadFilter(); eqApply(n, b, P.amount ?? 1); return n; }) : [];
        const vol = oc.createGain(); vol.gain.value = useEq ? Math.pow(10, P.gain_db / 20) : 1;
        [s, ...nodes, vol, oc.destination].reduce((x, n) => (x.connect(n), n));
        s.start();
        const out = await oc.startRendering();
        const rms = (b) => { let sum = 0, n = 0; for (let c = 0; c < b.numberOfChannels; c++) for (const v of b.getChannelData(c)) { sum += v * v; n++; } return Math.sqrt(sum / (n || 1)); };
        const d = rms(buf), w = rms(out);
        if (d > 1e-6 && w > 1e-6) g = Math.min(4, Math.max(0.25, w / d));
      } catch (e) { console.warn("eq match", e); }
      eqMatchVal.set(key, g);
    })());
  }
  return eqMatchJobs.get(key);
}

export function eqSetBypass(v) { EQ.bypass = v; eqRender(); eqRewire(); }

export const eqToggleAB = () => eqSetBypass(!EQ.bypass);

export function eqChip() {  // чип «EQ · профіль» на дублі, що звучить: золотий — з EQ, сірий — без (B); клік / A — перемкнути
  document.querySelectorAll("[data-eq-chip]").forEach((c) => c.remove());
  if (!playing || !EQ.live || !EQ.prof) return;
  const head = document.querySelector(`[data-play="${CSS.escape(playing.id)}"]`)?.closest(".take")?.querySelector(".wave-box");  // накладка: розмітку не зсуває
  if (!head) return;
  const on = eqActive(), ch = EQ.live.wsrc !== EQ.live.src;
  head.insertAdjacentHTML("beforeend", `<button class="eq-chip ${on ? "on" : ""}" data-eq-chip aria-pressed="${on}"
    title="${on ? (ch ? "Звучить з пресетом персонажа" : "Звучить з EQ") : "Звучить без обробки (B)"} — клік або A: порівняти">${ch ? "Персонаж · " : ""}EQ · ${esc(EQ.prof.name)}</button>`);
}
