# Runbook: додати двигун ШІ-голосу

Двигун — один файл `tools/aistudio/engines/<ім'я>.py` (реєстр знаходить його автоматично, `engines.list_engines()`).
Контракт — `tools/aistudio/engines/base.py` (`EngineInfo`, `Engine`); еталон — `fish.py`; контракт доводить тест із
фейковими двигунами (`tests/test_aistudio.py`: `FakeEngine`, `FakeCloud`).

1. **Метадані** `info = EngineInfo(name, title, kind="local"|"cloud", license, license_url, commercial, languages, supports, cost_note,
   requirements, output_license)`. `supports` — підмножина `text_override, style, ref_takes, variability, seed`; усе інше UI
   покаже як «не підтримується» (`map_params` повертає непідтримувані, їх не гублять мовчки).
   `output_license` — ліцензія ШІ-реплік у пакетах: лише `CC BY-NC 4.0` або `CC BY 4.0`; не впевнені — залиште NC (ADR 0007).
2. **`status()`** — швидко, без мережі й важких імпортів: `ready | missing_model | missing_key | missing_env` + `detail`.
3. **`generate(jobs, raws, log)`** — `jobs` це `studio.aigen.Job` (text, seed, temperature, top_p, refs[{audio,text}], max_new);
   пишіть сирий wav у `raws[i]` (формат гри й гучність нормалізує конвеєр), викликайте `log({"out": …})` після кожного файлу.
   `cancel()` має реально зупиняти роботу (для підпроцесу — `engines/procrun.WorkerRunner`, для HTTP — обрив запиту) і `generate` кидає `Cancelled`.
4. **Хмарний двигун** (`kind="cloud"`): ключ — лише `config.api_key(name, "ENV_VAR")` (env або `data/local/settings.json`, ніколи в git;
   `make guard` ловить ключі в закомічених файлах); `check_ready()` уже вимагає явну згоду
   `config.upload_consent(name)` (власні дублі йдуть стороннім); `warnings()` — вартість, ліміти, приватність.
   Референси — лише власні дублі (`refs.py` це гарантує до виклику двигуна). Результат — той самий формат і метадані (`engine`, `license`).
5. **Тест**: двигун-пустушка поводиться за контрактом (`list_engines`, `map_params`, `status`, згода, ліцензія); справжніх моделей/мережі в тестах немає.
6. Документація: рядок у `docs/plans/ai-studio-ui.md` не потрібен — UI бере все з `list_engines()`. Якщо ліцензія вільніша за NC — новий ADR.

Заборонено: двигуни з голосами акторів, клонування чужого голосу, `reference*/` як референс, публікація без позначки «ШІ».
