# Українська озвучка Warcraft III

[![CI](https://github.com/Stolenskiy/WarCraft3-Ukrainianization/actions/workflows/ci.yml/badge.svg)](https://github.com/Stolenskiy/WarCraft3-Ukrainianization/actions/workflows/ci.yml)

**Що це.** Фанатський некомерційний проєкт: повна **українська голосова озвучка** юнітів
Warcraft III Classic (а згодом — кампанійних місій), плюс уже готова текстова українізація
меню, текстів і карт. Офіційної української озвучки гри ніколи не існувало.

**Для чого.** Щоб піони, ґрунти й лицарі заговорили українською — живою мовою, з характером,
у хронометражі оригіналу. Озвучуємо **власними голосами** в локальній студії запису
(і, можливо, згодом — AI-синтезом).

**Кому корисно.** Гравцям, які хочуть грати українською; **акторам-аматорам і всім із
мікрофоном**, хто хоче озвучити улюбленого юніта; **редакторам тексту** (без коду) —
українські репліки й характери персонажів; розробникам — інструменти й тести.

![Студія запису](docs/img/studio.png)

## Як долучитися локально (озвучити своїм голосом)

Потрібні: Mac або Linux, Python 3.11 (або [uv](https://docs.astral.sh/uv/) — поставить сам), `ffmpeg`, Google Chrome, мікрофон і **власна
копія Warcraft III Classic** (оригінальні голоси беруться з неї; у репозиторії аудіо гри немає).

1. **Склонувати й налаштувати:**
   `git clone https://github.com/Stolenskiy/WarCraft3-Ukrainianization.git && cd WarCraft3-Ukrainianization && make setup`
2. **Витягти оригінали з гри:** `make refs` — англійські голоси з вашої гри (~5 хв).
   Гра не в `/Applications/Warcraft III Classic`? — `WC3_GAME_ROOT=/шлях make refs`.
   Російські (необов'язково) — якщо маєте російську локалізацію гри, вкажіть теку `ruru.w3mod`:
   `RU_PACK=<…>/Localizations/Russian/ruru.w3mod make refs`.
3. **Запустити студію:** `make studio` → відкриється http://127.0.0.1:8765 (усе офлайн).
4. **Озвучити:** раса й юніт угорі → послухати оригінал (`R`; мова **RU/EN** — перемикач
   «Оригінал») → прочитати «Як грати» → `Пробіл` запис / стоп → порівняти (`B`) →
   **✓ Обрати** найкращий дубль. Усе змінюване: кошик, `⌘Z`.
5. **Почути в грі:** у студії кнопка **«Встановити в гру»** (показує план → «Встановити»;
   «Прибрати з гри» — відкат). Те саме з терміналу: `make install-voices` (план) →
   `make install-voices APPLY=1`; відкат — `make uninstall-voices`. Обрані дублі з `game-files/`
   копіюються в гру з бекапом; теки юнітів-симлінків (`Units/orc/grunt` → `Mods/...`) стають
   реальними текою з симлінками на оригінальні файли, `Mods/` не змінюється.
6. **Поділитися:** тексти й характери — PR у `docs/voice-bible/`; записи — домовтеся
   в Issues (аудіо в репозиторій не комітимо). Детально — [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

---

## Що вже зроблено

- **Текстова українізація** меню 1.31, текстів і 203 карт — встановлюється в гру
  ([docs/ukrainian-ui-131.md](docs/ukrainian-ui-131.md), [docs/ukrainian-maps.md](docs/ukrainian-maps.md)).
- **Інвентар** 2401 голосового файлу 155 юнітів (`data/inventory-units.csv`) і транскрипти
  російських оригіналів (`data/transcripts-*.json`).
- **Voice bible** — 55 аркушів персонажів 4 рас: характер, тембр, українські репліки,
  «як грати» ([docs/voice-bible/](docs/voice-bible/README.md)).
- **Студія запису** власним голосом з оригіналом RU/EN ([tools/studio/README.md](tools/studio/README.md)).
- **TTS-експерименти** (Piper, XTTS-v2, Fish Speech) — не дотягли до планки якості
  ([docs/improve-and-elevenlabs.md](docs/improve-and-elevenlabs.md)).
- Поточний стан і наступні кроки — [docs/STATUS.md](docs/STATUS.md).

## Як влаштований конвеєр

```text
гра (репак)                      наш репозиторій
┌──────────────────┐
│ російська        │  витягнути          reference/units/orc/peon/*.wav
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
                                                │ власний голос у студії
                                                │ (або TTS — ElevenLabs, на паузі)
                                                ▼
                                     game-files/Units/orc/peon/*.wav
                                                │ найкращий дубль (вуха!)
                                                ▼
корінь гри ◄──────────────────  Units/orc/peon/peonyes1.wav
Warcraft III Classic            (loose-файл поверх CASC,
 Allow Local Files = 1)          той самий шлях, що в оригіналі)
```

Технічна основа інтеграції — той самий механізм, яким репак підключає
російську озвучку та Reforged-пакети: **loose-файли в корені гри** зі шляхами,
що дзеркалять CASC (`Units/orc/peon/peonyes1.wav`), і опція
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
2. **Студія запису власним голосом** ✅ — озвучуємо Орду ← *ми тут*.
3. **TTS-рушій.** Локальні безкоштовні (Piper / XTTS-v2 / Fish Speech S2-Pro) не дотягли
   до планки; наступний крок — ElevenLabs PoC (`docs/improve-and-elevenlabs.md`).
4. **Озвучка по юнітах.** Роботяга → Ґронт → …: масова генерація,
   обробка расовою палітрою, QA по тривалості й гучності.
5. **Реліз для melee/локальної гри.** Голосовий пак «поклади папку — і грає»
   (`docs/install-local.md`).
6. **Кампанійні місії.** Діалоги місій, транскрипція, адаптація за глосарієм
   термінів, генерація по персонажах, синхронізація з сінематиками.

## Етика і ліцензії

- Це **фанатський, некомерційний проєкт** для власників гри. Ніяких продажів,
  донатів, реклам. **Blizzard не має до проєкту стосунку**; Warcraft III —
  торговельна марка Blizzard Entertainment.
- **Не клонуємо голоси реальних акторів** для публічного поширення —
  ні оригінальних англійських, ні російських акторів озвучки. Еталонні
  російські wav використовуються лише як технічний референс тембру в межах
  команди; у реліз потрапляють тільки синтезовані голоси або записані учасниками
  власним голосом (за їхньою згодою).
- Ліцензії моделей: **XTTS-v2 — Coqui Public Model License (CPML)**;
  **Fish Speech S2-Pro — Fish Audio Community License** (ваги — Fish Audio
  Research License). Обидві дозволяють некомерційне використання такого роду;
  перед релізом звіримо умови ще раз.
- Розповсюдження — тільки як мод-файли до легальної копії гри, окремо від неї.

## Для AI-агентів

- Почати з [CLAUDE.md](CLAUDE.md) (правила, карта документації) і [docs/STATUS.md](docs/STATUS.md)
  (що зроблено / що далі — оновлювати в кінці сесії).
- Студія: архітектура, дані, як додати расу чи місії — [tools/studio/README.md](tools/studio/README.md).
- Перед комітом — `make check` (те саме, що CI: ruff, тести з Chrome, покриття не нижче порогу).
- Аудіо гри, записи, `reference*/`, `game-files/` — **ніколи не комітити**. Зміни в теці гри —
  лише за процедурою [.claude/skills/game-change/SKILL.md](.claude/skills/game-change/SKILL.md).

## English summary

Non-commercial fan project: a full **Ukrainian voice-over** for Warcraft III Classic units
(campaign later), plus an installed Ukrainian text localization. Contributors record lines
**with their own voice** in a local browser studio (`make setup && make refs && make studio`):
listen to the Russian or English original, record takes, pick the best one — it is exported
in the game's format and dropped into the game root as a loose file. Requires your own copy of
the game; no game audio is published here. Agents: start with `CLAUDE.md` and `docs/STATUS.md`.
