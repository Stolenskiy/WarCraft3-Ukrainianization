// Синтаксис усіх ES-модулів студії (node --check не приймає файл як модуль без package.json, тож читаємо через stdin).
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const dir = fileURLToPath(new URL("./studio/web/js/", import.meta.url));
let bad = 0;
for (const f of readdirSync(dir).filter((n) => n.endsWith(".js"))) {
  try { execFileSync(process.execPath, ["--input-type=module", "--check"], { input: readFileSync(dir + f), stdio: ["pipe", "inherit", "inherit"] }); }
  catch { console.error(`синтаксична помилка: ${f}`); bad = 1; }
}
process.exit(bad);
