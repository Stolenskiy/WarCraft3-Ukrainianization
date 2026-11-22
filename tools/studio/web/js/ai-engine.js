/* Двигун ШІ: вибір, ліцензія (NC / комерційне), тип, готовність, що виправити; хмара — ключ і згода на вивантаження;
   діалог першої згоди «це мій власний голос». Дані — /api/ai/status, /api/ai/engines, POST /api/ai/consent|engine. */
import { post } from "./api.js";
import { AIS, curEngine, patchEngine, setEngine, shortLic, stateUa } from "./ai-state.js";
import { toast } from "./toast.js";
import { esc } from "./util.js";

export const SETUP_CMD = "python tools/run.py ai-setup --accept-license";

/** Що саме зробити, коли двигун не готовий (порожньо, якщо готовий). */
export function fixHint(e) {
  const st = e.status;
  if (st.state === "ready") return "";
  const d = st.detail ? `${esc(st.detail)}. ` : "";
  if (st.state === "missing_key") return `${d}Вставте ключ API нижче (зберігається лише в <code>data/local/settings.json</code>).`;
  return `${d}Виправити: <code>${e.kind === "local" ? SETUP_CMD : "див. вимоги двигуна"}</code>`;
}

function badges(e) {
  const nc = !e.commercial;
  return `<span class="ai-b ${nc ? "nc" : "com"}" title="Ліцензія двигуна: ${esc(e.license)}. Результат у пакетах голосів: ${esc(e.output_license)}">${nc ? "NC · некомерційне" : "комерційне: так"}</span>
    <span class="ai-b" title="${e.kind === "local" ? "Працює на цьому комп’ютері" : "Надсилає дані стороннім сервісом"}">${e.kind === "local" ? "локально" : "хмара"}</span>
    <span class="ai-b st-${esc(e.status.state)}" data-ai-state="${esc(e.status.state)}">${esc(stateUa(e.status.state))}</span>`;
}

export function engineHtml() {
  const e = curEngine();
  if (!e) return `<p class="ai-warn">Двигунів ШІ не знайдено.</p>`;
  const fix = fixHint(e);
  return `<div class="ai-eng-row"><label>Двигун <select id="aiEngine">${AIS.engines.map((x) =>
      `<option value="${esc(x.name)}" ${x.name === e.name ? "selected" : ""}>${esc(x.title)}</option>`).join("")}</select></label>${badges(e)}
      <a href="${esc(e.license_url)}" target="_blank" rel="noopener" class="ai-lic" title="Текст ліцензії">${esc(e.license)}</a></div>
    ${e.cost_note ? `<p class="ai-note">Вартість: ${esc(e.cost_note)}</p>` : ""}
    ${(e.warnings || []).map((w) => `<p class="ai-warn">${esc(w)}</p>`).join("")}
    ${fix ? `<p class="ai-fix" data-ai-fix>${fix}</p>` : ""}
    ${e.kind === "cloud" ? `<div class="ai-cloud"><label class="ai-chk"><input type="checkbox" id="aiUpload" ${e.upload_consent ? "checked" : ""}>
        Дозволяю вивантажити мої власні дублі стороннім сервісом (референс голосу)</label>
      <div class="ai-key"><input type="password" id="aiKey" placeholder="API-ключ (лише data/local, назад не показується)" autocomplete="off">
        <button class="btn" id="aiKeySave">Зберегти ключ</button></div></div>` : ""}
    <p class="ai-note">Результат: ${esc(shortLic(e.output_license) ? e.output_license : "CC BY-NC 4.0")}${e.commercial ? "" : " — лише некомерційне використання"}.</p>`;
}

/** Вішає обробники блоку двигуна; onChange() — перемалювати форму (двигун змінив підтримувані параметри). */
export function bindEngine(box, onChange) {
  box.onchange = async (ev) => {
    const t = ev.target;
    if (t.id === "aiEngine") { setEngine(t.value); onChange(); }
    if (t.id === "aiUpload") {
      try { patchEngine(await post("/api/ai/engine", { name: AIS.engine, upload_consent: t.checked })); }
      catch (er) { toast(er.message, true); t.checked = !t.checked; }
      onChange();
    }
  };
  box.onclick = async (ev) => {
    if (ev.target.id !== "aiKeySave") return;
    const key = box.querySelector("#aiKey").value.trim();
    if (!key) return toast("Вставте ключ", true);
    try { patchEngine(await post("/api/ai/engine", { name: AIS.engine, api_key: key })); toast("Ключ збережено в data/local/settings.json"); }
    catch (er) { toast(er.message, true); }
    onChange();
  };
}

/** Перша генерація: «це мій власний голос»; хмара — ще й згода на вивантаження. Повертає true, якщо все дозволено. */
export function ensureConsents(e) {
  const needOwn = !AIS.status.consent, needUp = e.kind === "cloud" && !e.upload_consent;
  if (!needOwn && !needUp) return Promise.resolve(true);
  return new Promise((resolve) => {
    const m = document.createElement("div");
    m.className = "modal"; m.id = "aiConsent"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true");
    m.innerHTML = `<div class="modal-box ai-consent"><div class="modal-head"><h3>Згода на ШІ-голос</h3></div><div class="modal-body">
      ${needOwn ? `<label class="ai-chk"><input type="checkbox" data-c="own"> ${esc(AIS.status.consent_text)}</label>` : ""}
      ${needUp ? `<label class="ai-chk"><input type="checkbox" data-c="up"> Дозволяю вивантажити мої власні дублі сервісу «${esc(e.title)}» (референс голосу). ${esc((e.warnings || []).join(" "))}</label>` : ""}
      <p class="ai-note">Клонується лише ваш голос; усі ШІ-репліки позначаються «ШІ».</p></div>
      <div class="modal-foot"><button class="ghost" data-c-cancel>Скасувати</button><button class="btn primary" data-c-ok disabled>Продовжити</button></div></div>`;
    const ok = m.querySelector("[data-c-ok]"), boxes = [...m.querySelectorAll("input[data-c]")];
    const close = (v) => { m.remove(); document.removeEventListener("keydown", onKey, true); resolve(v); };
    const onKey = (ev) => { if (ev.code === "Escape") close(false); ev.stopImmediatePropagation(); };
    document.addEventListener("keydown", onKey, true);
    m.addEventListener("change", () => { ok.disabled = !boxes.every((b) => b.checked); });
    m.querySelector("[data-c-cancel]").onclick = () => close(false);
    ok.onclick = async () => {
      try {
        if (needOwn) AIS.status.consent = (await post("/api/ai/consent", { accept: true })).ai_consent;
        if (needUp) patchEngine(await post("/api/ai/engine", { name: e.name, upload_consent: true }));
        close(true);
      } catch (er) { toast(er.message, true); close(false); }
    };
    document.body.appendChild(m);
    boxes[0]?.focus();
  });
}
