"""Ядро студії: стан (тексти, дублі, затвердження, журнал) і всі дії над ним.

Не знає ні про UI, ні про джерело реплік (це catalog.py). Модель стану одного каталогу
(data/studio/<catalog>.json):

    {"version": 3, "groups": {<group>: {<line>: {
        "ua_text": str | None,          # None = використовується підказка з каталогу
        "approved": <take file> | None, # цей дубль скопійовано в game-files/<game_rel>
        "takes": [{"file", "created", "deleted": iso | None,    # deleted → лежить у _deleted/
                   "trim": {"start": sec, "end": sec},           # trim — необов'язкове ручне обрізання
                   "tempo": 1.15,                                # tempo — необов'язкове прискорення 0.8–1.3
                   "peak_db": dBFS, "clipped": bool,             # необов'язкові (старі дублі без них)
                   "source": "ai", "engine", "ai_file"}],        # лише дублі, взяті з ШІ-варіантів (ai.py)
        "original": {"lang": "ru"|"en", "ts": iso} | None,   # «Залишити оригінал» (взаємовиключно з approved)
        "history": [{"ts", "action"}]}}}}

Інваріанти (перевіряються тестами tests/test_studio_core.py):
  * файл дубля ніколи не перезаписується (номер = max(усі відомі) + 1);
  * видалення = переміщення в _deleted/ (відновлюється), затвердження при цьому знімається;
  * ручне обрізання (trim) не змінює файл дубля — лише копію для гри (ffmpeg atrim ПЕРШИМ у
    _export_filters; авто-обрізання тиші, якщо ввімкнене, діє після нього); зміна trim
    затвердженого дубля одразу перезаписує копію для гри;
  * затверджений дубль завжди має копію в game-files, незатверджений — не має;
  * «залишити оригінал» (звуки без слів): у game-files/<game_rel> лежить НЕОБРОБЛЕНА копія оригіналу
    (байт-у-байт, якщо це wav у форматі гри; інакше лише конвертація в 22050 Hz mono s16), а
    game-files/.originals.json {rel: {lang, sha256}} перелічує такі файли — публікація пакета ПОВИННА
    їх пропускати (це аудіо Blizzard). approved і original взаємовиключні; обидва рахуються як «готово».

Темп (tempo, 0.8–1.3, немає ключа = 1.0): ffmpeg atempo зберігає висоту голосу; файл дубля не
змінюється, зміна темпу затвердженого дубля одразу перезаписує копію для гри (як trim).

Налаштування обробки — data/studio/settings.json {auto_trim, denoise, loudness} (proc.SettingsStore;
GET/POST /api/settings). Ланцюжок копії для гри (_export_filters, ЄДИНИЙ для затвердження, перезапису
й «Як у грі» — Service.preview, кеш data/studio/preview-cache/), порядок строгий:
    ручне обрізання → авто-обрізання тиші → шумоговорення → темп → EQ → вирівнювання гучності
(volume до гучності оригіналу репліки ±18 дБ + alimiter, щоб не кліпувало). Деталі — proc.py.
Параметри trim/auto_trim у запитах — застарілий явний override налаштування auto_trim.
"""
# Реекспорт: публічний API ядра (server, aigen, тести) лишається `studio.core.*`.
from .svc.service import Service  # noqa: F401
from .svc.store import Store  # noqa: F401
from .svc.util import (  # noqa: F401
    AUTO_TRIM,
    CLIP_LEVEL,
    CLIP_MIN_SAMPLES,
    ORIGINALS_JSON,
    PREVIEW_DIR,
    TAKE_RE,
    StudioError,
    export_take,
    file_iso,
    new_entry,
    now,
    take_no,
    wav_peak,
)
