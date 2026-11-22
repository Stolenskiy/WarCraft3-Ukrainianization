/* Відповідь сервера → стан (putPhrase), act, збереження тексту. */
import { post } from "./api.js";
import { renderCard } from "./card.js";
import { loadCatalogs } from "./catalog.js";
import { renderCues } from "./cues.js";
import { S, cur, ids } from "./state.js";
import { setUndo, toast } from "./toast.js";
import { $ } from "./util.js";

// Відповідь сервера кладемо за (каталог, юніт, id репліки), а не за поточним індексом:
// поки йшов запит, користувач міг перейти на іншу репліку чи юніт.
export function putPhrase(where, res, newFile) {
  if (!res || where.cid !== S.cat || where.gid !== S.unit) { loadCatalogs(); return; }
  const i = S.phrases.findIndex((x) => x.id === res.id);
  if (i < 0) return;
  S.phrases[i] = res;
  renderCues();
  if (i === S.idx) renderCard(newFile);
  loadCatalogs();
}

export async function act(path, body) {
  try { return await post(path, { ...ids(), ...body }); }
  catch (e) { toast(e.message, true); return null; }
}

export async function saveText() {
  const ua = $("#ua"), p = cur();
  if (!ua || !p || ua.value.trim() === p.ua) return;
  const where = ids(), prev = p.ua;
  const res = await act("/api/text", { text: ua.value });
  if (!res) return;
  if (where.cid === S.cat && where.gid === S.unit) {
    const i = S.phrases.findIndex((x) => x.id === res.id);
    if (i >= 0) S.phrases[i] = res;
    renderCues();
    if (cur()?.id === res.id) { const st = $("#uaState"); if (st) st.textContent = "✓ збережено"; }
  }
  setUndo("Текст змінено", async () => putPhrase(where, await post("/api/text", { ...where, text: prev })));
}
