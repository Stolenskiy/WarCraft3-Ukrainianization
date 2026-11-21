# Українська AI-озвучка Warcraft III

**wc3-ua-voice** — фанатський проєкт, який створює повноцінну українську
озвучку юнітів Warcraft III Classic за допомогою AI-синтезу мовлення
(TTS з клонуванням тембру). Грає у melee/локальній грі сьогодні;
у перспективі — озвучення кампанійних місій.

У Warcraft III досі **не існує української голосової локалізації**: є російська,
польська, чеська — а українські гравці десятиліттями чують своїх піонів,
гронтів і лицарів чужою мовою. Ми хочемо це виправити — силами спільноти,
інструментами open source, без жодного комерційного інтересу.

---

## Що вже зроблено

- **Інвентар звуків.** `data/inventory-units.csv` — 2401 голосовий файл,
  155 типів юнітів, з типами реплік (confirm / question / annoyed / attack /
  death / warcry…) і тривалістю кожної фрази. Це наш master backlog.
- **Російські еталони + розшифровки.** Російська озвучка з репаку витягнута
  в `reference/units/<раса>/<юніт>/` і прогнана через Whisper
  (mlx-whisper large-v3-turbo) — транскрипти лежать у `data/transcripts-*.json`
  (23 юніти вже розшифровано: орки, нежить, нічні ельфи, селянин, піон).
- **Текстова локалізація в грі.** Українські текстові файли (warcraft-in-ua)
  вже встановлені в корінь гри — меню й інтерфейс українською працюють.
- **Голосовий біблія.** Методологія + аркуші персонажів:
  `docs/voice-bible/README.md` — правила і шаблон; усі чотири ігрові раси
  готові: `human.md` (15 юнітів), `orc.md` (15), `undead.md` (13),
  `nightelf.md` (12). Разом — **55 аркушів** з характером, тембром,
  обробкою та фразами на кожен файл.
- **PoC-експерименти TTS** (юніт Peon/Роботяга, 15 фраз у трьох системах —
  повний звіт і наступні кроки: `docs/improve-and-elevenlabs.md`):
  - **Piper** (`uk_UA-ukrainian_tts-medium`) — рідна українська модель:
    розбірливо, але голос один на всіх юнітів, інтонація нейтральна —
    «єдиний диктор», не годиться.
  - **XTTS-v2** (Coqui, клонування тембру з російського еталона) — тембр
    переносить, але української мови в базовій моделі немає: текст доводиться
    транслітерувати і синтезувати з тегом `ru` — зрозуміло, але з сильним
    акцентом.
  - **Fish Speech S2-Pro** — найкращий із безкоштовних: жива інтонація,
    прийнятна вимова, клонування тембру з референсу. Усі 15 фраз згенеровано.
    Але це все ще не дубляж-рівень.

**Чесний підсумок:** конвеєр працює від кінця до кінця на одному юніті,
безкоштовні локальні моделі свого стелі досягли. Наступний крок —
ElevenLabs (офіційна підтримка української + клонування тембру,
~$22–50 на весь проєкт) — план у `docs/improve-and-elevenlabs.md`.

## Як влаштований конвеєр

```text
гра (репак)                      наш репозиторій
┌──────────────────┐
│ російська        │  витягнути          reference/units/orc/Peon/*.wav
│ озвучка (еталон) │ ────────────────►          │
└──────────────────┘                            │ tools/transcribe.py
                                                │ (mlx-whisper large-v3-turbo)
                                                ▼
                                     data/transcripts-orc-peon.json
                                                │
                                                │ редактор тексту (людина!)
                                                ▼
                                     docs/voice-bible/orc.md
                                     (характер, тембр, українські фрази
                                      + «як озвучувати»)
                                                │
                                                │ TTS з клонуванням тембру
                                                │ (Fish Speech S2-Pro /
                                                │  XTTS-v2, еталон = рос. wav)
                                                ▼
                                     audio/experiments/peon/*.wav
                                                │ відбір варіантів (вуха!)
                                                ▼
корінь гри ◄──────────────────  Units/Orc/Peon/Peonyes1.wav
Warcraft III Classic            (loose-файл поверх CASC,
 Allow Local Files = 1)          той самий шлях, що в оригіналі)
```

Технічна основа інтеграції — той самий механізм, яким репак підключає
російську озвучку та Reforged-пакети: **loose-файли в корені гри** зі шляхами,
що дзеркалять CASC (`Units/Orc/Peon/Peonyes1.wav`), і опція
`Allow Local Files`. Деталі — в `docs/integration.md`.

## Планка якості

Правила зафіксовані в `docs/voice-bible/README.md`, коротко:

1. **Характер > краса.** Голос упізнається за перші 0.5 секунди; кожен юніт —
   архетип.
2. **Расова палітра.** Люди — суха «казарма/собор», орки — низький степ,
   нежить — холодний склеп, ельфи — нічний ліс. Індивідуальність — всередині
   палітри.
3. **Хронометраж.** Українська фраза вписується в тривалість оригіналу
   (тривалості є в `data/inventory-units.csv`). Не влазить — переписуємо
   текст, не розтягуємо звук.
4. **Жива українська мова.** Без суржику, без русизмів.
5. **Не клонуємо голоси реальних акторів.** Тільки спроєктовані або
   бібліотечні голоси.

## Дорожня карта

1. **Голосові біблії по расах** ✅ — усі 4 раси, 55 юнітів.
2. **Вибір TTS-рушія** ← *ми тут*. Локальні безкоштовні протестовані
   (Piper / XTTS-v2 / Fish Speech S2-Pro), стелі досягнуто; наступний крок —
   ElevenLabs PoC (`docs/improve-and-elevenlabs.md`).
3. **Генерація по юнітах.** Роботяга → Ґронт → …: масова генерація,
   обробка расовою палітрою, QA по тривалості й гучності.
4. **Реліз для melee/локальної гри.** Голосовий пак «поклади папку — і грає»
   (`docs/install-local.md`).
5. **Кампанійні місії.** Діалоги місій, транскрипція, адаптація за глосарієм
   термінів, генерація по персонажах, синхронізація з сінематиками.

## Як долучитися

Головний документ — **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)**.

Корисні документи:
- **[docs/install-local.md](docs/install-local.md)** — встановити текстовий
  українізатор + голосовий пак у свою гру (покроково, з відкатом)
- **[docs/improve-and-elevenlabs.md](docs/improve-and-elevenlabs.md)** — як
  покращити якість озвучки та план переходу на ElevenLabs
- **[docs/voice-bible/README.md](docs/voice-bible/README.md)** — методологія
  озвучення, расові палітри, шаблон персонажа
- **[docs/ukrainian-ui-131.md](docs/ukrainian-ui-131.md)** — як влаштована
  українізація меню для клієнта 1.31.1
- **[docs/ukrainian-maps.md](docs/ukrainian-maps.md)** — патч назв/описів карт

Покрокові інструкції для трьох ролей:

| Роль | Що робить | Потрібно |
|---|---|---|
| **Редактор тексту** | Українські фрази + характер персонажа у voice bible | тільки вуха й рідна мова, **без коду** |
| **Генератор озвучки** | Обгортка середовища, генерація, відбір варіантів | Mac з Apple Silicon, ~15 ГБ диска |
| **Редактор місій (кампанія)** | Адаптація діалогів місій за шаблоном voice bible | те саме, що редактор тексту |

Найбільше зараз потрібно саме **редакторів тексту** — без хороших українських
фраз синтезувати нічого.

## Етика і ліцензії

- Це **фанатський, некомерційний проєкт** для власників гри. Ніяких продажів,
  донатів, реклам. **Blizzard не має до проєкту стосунку**; Warcraft III —
  торговельна марка Blizzard Entertainment.
- **Не клонуємо голоси реальних акторів** для публічного поширення —
  ні оригінальних англійських, ні російських акторів озвучки. Еталонні
  російські wav використовуються лише як технічний референс тембру в межах
  команди; у реліз потрапляють тільки синтезовані голоси.
- Ліцензії моделей: **XTTS-v2 — Coqui Public Model License (CPML)**;
  **Fish Speech S2-Pro — Fish Audio Community License** (ваги — Fish Audio
  Research License). Обидві дозволяють некомерційне використання такого роду;
  перед релізом звіримо умови ще раз.
- Розповсюдження — тільки як мод-файли до легальної копії гри, окремо від неї.

---

## English summary

**wc3-ua-voice** is a non-commercial fan project building a full Ukrainian
AI voice-over for Warcraft III Classic (melee/local play first, campaign
missions later). No Ukrainian voice localization has ever existed for the game.

**How it works:** Russian reference voice files are extracted from the game
repack, transcribed with Whisper, and adapted into Ukrainian scripts with
per-character voice direction (the "voice bible"). A voice-cloning TTS model
(Piper / XTTS-v2 / Fish Speech S2-Pro — currently evaluating) generates
Ukrainian lines that are dropped as loose WAV files into the game root,
mirroring the original CASC paths (e.g. `Units/Orc/Peon/Peonyes1.wav`) —
the same mechanism the repack uses for its own language and Reforged packages
(see `docs/integration.md`).

**Status:** sound inventory done (2401 files, 155 unit types), Russian
references transcribed for 23 units, text localization installed in-game,
voice bible methodology written (Human race complete, Night Elves in progress),
TTS proof-of-concept generated for the Peon unit in three systems.

**Want to help?** The biggest need is **Ukrainian text editors** — no coding
required. See `docs/CONTRIBUTING.md`. This is a fan project for game owners;
we do not clone real actors' voices for public distribution, and model weights
are used under their respective licenses (CPML for XTTS-v2, Fish Audio
Community License for S2-Pro).
