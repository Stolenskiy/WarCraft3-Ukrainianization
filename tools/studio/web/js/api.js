/* HTTP-клієнт: getJSON / post (X-Studio). */

export async function getJSON(url) {
  const r = await fetch(url);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}

export async function post(path, body, isAudio = false) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "X-Studio": "1", "Content-Type": isAudio ? "audio/wav" : "application/json" },
    body: isAudio ? body : JSON.stringify(body),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}
