# Інтеграція української озвучки у Warcraft III Classic (lmmortal-Repack)

Статус: дослідження завершено (листопад 2026). Вся інформація нижче здобута з
read-only інспекції `/Applications/Warcraft III Classic` — жодних змін у папці
гри не вносилося.

## 1. Як влаштований лаунчер і підключення пакетів

«Лаунчер» — це не окремий додаток. Це патч `WC3Patcher.dylib`, який вбудовано в
ігровий бінарник `x86_64/Warcraft III.app/Contents/MacOS/Warcraft III`
(оригінальний клієнт 1.31.1 Public Test). Він показує стартове меню
(Play / Options / Quit) і керує пакетами через скрипти-бекенд у бандлі:

```
x86_64/Warcraft III.app/Contents/Resources/WC3Patcher/
├── backend/
│   ├── wc3-patcher.sh            # баланс 1.31.1 ↔ Reforged 2.0.4 (SLK-патч)
│   ├── wc3-language-assets.py    # мовний пакет (російська озвучка) → лінки в корінь
│   ├── wc3-ui-assets.py          # пакет Reforged UI → лінки в корінь
│   ├── wc3-model-assets.py       # пакет Reforged Models → лінки в корінь
│   ├── wc3-hero-appearances.py   # облики героїв + жіночі голоси
│   └── wc3-resource-directories.py
├── packages/Reforged UI/         # вбудований UI-пакет (встановлений разом з грою)
├── data/patch/Payload/           # SLK/TXT балансу 2.0.4
└── data/embedded/female_heroes/voice_overrides/  # приклад заміни голосів
```

### Ключовий механізм: Local Files у корені гри

**Всі пакети працюють через один і той самий механізм — loose-файли в корені
гри**, які клієнт читає поверх CASC, якщо ввімкнено `Allow Local Files`:

```
defaults write "com.blizzard.Warcraft III Public Test" "Allow Local Files" -int 1
defaults write "com.blizzard.WarcraftIII" "Allow Local Files" -int 1
```

(лаунчер робить це сам через `enable_local_files()` у `wc3-patcher.sh`; ми вже
увімкнули це вручну — підтверджено `defaults read`).

Жодних записів у CASC (`Data/`), жодних MPQ-правок, жодного монтування
`.w3mod` у `Data/` — **не відбувається**. Пакет, навіть російський із
внутрішньою структурою `ruru.w3mod/`, при активації розгортається в корінь гри
символічними лінками:

- при Play з увімкненою мовою: `wc3-language-assets.py` (функция
  `activate_ru`) створює у корені гри сімлінки/«згорнуті» директорні лінки
  `Sound → Localizations/Russian/ruru.w3mod/sound`,
  `Units/<раса>/<юніт>/*.wav → …` тощо, з журналом відкату в
  `Tools/State/Language/journal.json`;
- при вимкненій мові: лінки прибираються, оригінальні loose-файли відновлюються.

Мапа верхнього рівня (з `wc3-language-assets.py`, `TOP_LEVEL`) — саме туди
клієнт 1.31.1/«Reforged» читає локальні файли:

| шлях у пакеті | шлях у корені гри | вміст |
|---|---|---|
| `units/…` | `Units/…` | голоси юнітів, SLK/TXT даних |
| `buildings/…` | `Buildings/…` | голоси будівель |
| `abilities/…` | `Abilities/…` | звуки здібностей |
| `sound/…` | `Sound/…` | музика, ambient, UI-звуки |
| `ui/…` | `UI/…` | FDF, SoundInfo, текстови інтерфейсу |
| `fonts/…`, `movies/…`, `doodads/…`, `_balance/…` | відповідно | інше |

Перевірений приклад із самого репаку: жіночі голоси героїв
(`data/embedded/female_heroes/voice_overrides/Units/NightElf/HeroDemonHunter/*.wav`)
кладуться саме в `Units/<Раса>/<Юніт>/*.wav` кореня гри, а для **нових**
(не замінених) голосів додаються рядки в `UI/SoundInfo/UnitAckSounds.slk`.

### Reforged UI / Models / Hero Appearances

`Tools/State/Reforged UI/state.json` показує: 1065 файлів підключено
сімлінками з `WC3Patcher/packages/Reforged UI/Payload/…` у корінь гри
(`UI/console`, `UI/cursor`, `UI/glues`, `Textures/…`,
`ReplaceableTextures/…`). Те саме робить пакет Models з `Mods/Reforged Models`.
Тобто «Reforged-графіка» — це теж просто loose-файли в корені.

### Баланс 1.31.1 ↔ Reforged 2.0.4

Виконуваного файлу «Reforged 2.04» немає. Режим «Reforged 2.0.4» досягається
заміною таблиць даних у корені гри (`Units/UnitBalance.slk`,
`UnitData.slk`, `UnitWeapons.slk`, `UnitAbilities.slk`, `UpgradeData.slk`,
`AbilityData.slk`, `ItemData.slk`, `MiscGame.txt`, `*UnitFunc.txt`,
`*AbilityStrings.txt`, `*UnitStrings.txt` тощо) з
`WC3Patcher/data/patch/Payload/` — див. `core_plan()` у `wc3-patcher.sh`.
Стан визначається хешем `Units/UnitBalance.slk` (`balance_status()`).
Перед установкою лаунчер робить снапшот у
`Tools/State/Balance/snapshots/core02/` (наразі там всі 36 позицій
«absent/original» — тобто **Reforged-баланс зараз НЕ встановлений, гра в
класиці 1.31.1**, що збігається зі спостереженням користувача).

## 2. Куди класти наші українські озвучки

### Рекомендація: корінь гри, ті самі шляхи, що й в оригіналі

Наші згенеровані `.wav` кладемо прямо в корінь гри зі шляхами, що відтворюють
оригінальні (реєстр на macOS нечутливий, але тримаємо канонічний вигляд):

```
/Applications/Warcraft III Classic/
├── Units/Orc/Peon/PeonYes1.wav            (заміна голосу піона)
├── Units/Human/Peasant/PeasantWhat1.wav   … тощо
├── Units/Undead/Acolyte/AcolytePissed1.wav
├── Buildings/Human/Farm/FarmWhat1.wav     (голоси будівель, якщо робимо)
└── Sound/…                                (музика/ambient, якщо колись)
```

Чому саме так:

1. Це єдиний механізм, який цей репак використовує для **всіх** замін
   (російська локалізація, Reforged UI, Models, жіночі голоси) — перевірено
   кодом лаунчера.
2. Працює однаково і в 1.31.1, і в «Reforged 2.0.4» (це той самий бінарник,
   різниця лише в SLK-таблицях, які ми не чіпаємо).
3. Не ламає журнали/стани лаунчера: наші файли лежать у директоріях, які
   лаунчер уважає «своїми» лише за точними хешами; чужі файли він не чіпає
   (усі cleanup-функції видаляють тільки файли з відомим хешем).
4. Не потребує ані CASC-запису, ані власного `.w3mod`-пакета.

### Іменування файлів

Ім'я файлу має точно збігатися з оригінальним звуковим ресурсом юніта
(`PeonYes1.wav`, `PeonWhat3.wav`, `PeonPissed5.wav`, `PeonDeath1.wav` тощо).
Список шляхів для кожного юніта беремо з нашого інвентаря (`data/`) та
голосової біблії (`docs/voice-bible/`). Формат: PCM WAV, як в оригіналі
(перевірити частоту/канали оригіналу — відкрите питання №3).

### Альтернативи, які ми відхилили

- **(b) власний `.w3mod` + paths-файл у `Localizations/`** — це формат
  встановлених PKG-пакетів; лаунчер жорстко валідує маніфест
  (`ruru_paths.txt` із фіксованою SHA-256) і вміст, чужий пакет він не
  підхопить без перепаковки PKG. Надмірно для нашого завдання.
- **(c) всередину бандла `Warcraft III.app`** — бандл підписаний
  (локальний підпис відновлюється інсталятором), зміни ламають підпис і
  губляться при перевстановленні.

### Якщо колись захочемо ДОДАВАТИ нові репліки (не заміняти)

Нова озвучка, якої немає в оригіналу, потребує правки таблиць
`UI/SoundInfo/*.slk` (UnitsoundData / UnitAckSounds) у корені гри — саме так
лаунчер підключає жіночі голоси героїв. Це окрема задача, зараз не потрібна.

## 3. Відмінності для клієнта 1.31.1 (класика)

Ніяких окремих дій: клієнт 1.31.1 з `Allow Local Files=1` читає loose-файли з
кореня гри так само. Російський пакет взагалі розрахований на «Warcraft III
1.31.1» (текст помилки валідації: «Unsupported Russian package manifest for
Warcraft III 1.31.1») і працює через ті самі кореневі сімлінки.

### Статус текстових файлів українського перекладу (warcraft-in-ua)

Ми вже поклали в корінь гри: `UI/`, `Units/` (txt/slk), `classic/`,
`reforged/`, `movies/`, `fonts/`, `webui/`. Оцінка:

- `UI/`, `Units/*.txt`, `fonts/` — кореневі шляхи, клієнт 1.31.1 їх читає
  через Local Files. Ок.
- `classic/roc|tft`, `reforged/roc|tft` (відео `.w3m`) — це **layout
  сучасного Reforged 2.0+ CASC** (розділення класичних/рефордж-сінематиків).
  Клієнт 1.31.1 шукає сінематики в `Movies/`, тому ці папки, найімовірніше,
  просто ігноруються. Не шкодять.
- `webui/` — для вбудованих веб-екранів (Battle.net glue). Під 1.31.1
 -sumнівно, перевірити фактично.

## 4. Як перемкнути гру на Reforged 2.0.4 (інструкція користувачу)

Джерело: рядки UI з `WC3Patcher.dylib` + `Launcher ru.json`.

1. Закрити гру, якщо запущена (лаунчер відмовляється міняти файли за
   іншого запущеного процесу гри).
2. Відкрити `x86_64/Warcraft III.app` — з'явиться стартовий лаунчер
   (Play / Options / Quit).
3. Натиснути **Options (Настройки)**.
4. У секції **Game Mode (Режим игры)** вибрати один із варіантів:
   - **Classic 1.31.1** — поточний режим;
   - **Reforged 2.0.4 + UI** — баланс 2.0.4 + інтерфейс Reforged
     (рекомендовано; UI-пакет вбудований, доступний завжди);
   - **Reforged 2.0.4 + UI + Models (Test)** — те саме + повний пакет
     моделей/оточення з `Mods/Reforged Models`.
5. Натиснути **Apply (Застосувати)** — з'явиться «Applying options…» /
   «Installing patch…». Лаунчер: зробить снапшот, укачає SLK 2.0.4 у
   `Units/`, увімкне `Allow Local Files`, підключить UI-пакет сімлінками.
   Для `Reforged 2.0.4 + UI + Models` знадобиться включити пакет моделей:
   **Mods (Моди)** — пункт під Options у головному меню лаунчера; там же
   Enable/Disable/Remove для встановлених пакетів (російська мова тощо).
6. Закрити Options і натиснути **Play (Играть)**.
7. Перевірка: версія в меню гри залишиться «1.31.1» (бінарник той самий), але
   дані/інтерфейс — Reforged 2.0.4. Об'єктивна перевірка — хеш
   `Units/UnitBalance.slk` або вигляд інтерфейсу.

Відкат: Options → Game Mode → Classic 1.31.1 → Apply (лаунчер відновить
снапшот `Tools/State/Balance/snapshots/core02`), або Balance Patch → Restore.

Наші голоси з п.2 переживають перемикання без змін: перемикається лише
вміст `Units/*.slk|txt` (лаунчер перезаписує тільки файли зі своїми
хешами), голосові `.wav` у `Units/<Раса>/<Юніт>/` він не чіпає. Якщо наш
`.wav` лежить поруч із файлом, який лаунчер замінює (наприклад,
`Units/Human/Peasant/`) — конфлікту нема: це різні файли.

## 5. Відкриті питання

1. **Параметри WAV.** Треба зняти формат оригінальних голосів із CASC
   (частота, біти, канали — очікуємо 22/44 kHz mono PCM) і генерувати наші
   файли в тому ж форматі, інакше можливі артефакти/тиша.
2. **`Tools/State/Optional Packages.json` = `{"language": true, "models": true}`**,
   але `Localizations/` порожній і `Tools/State/Language` містить лише
   `lock` (журналу немає). Схоже, російський пакет був «Disable»-нутий
   (файли мали б залишитися на місці) або взагалі Remove-нутий. Перед
   тестами варто переконатися, що стан мови «english», щоб Play не
   спробував напівактивувати російський оверлей.
3. **Пріоритет локальних файлів vs CASC у 1.31.1** — треба один експеримент:
   покласти тестовий `Units/Human/Peasant/PeasantWhat1.wav` (тиха або
   whistle-запис) у корінь і запустити бій, переконатися, що локальний файл
   грає замість CASC. Це єдине, що не доказано кодом (лаунчер так працює з
   російською озвучкою, тож очікуємо «так»).
4. Чи грає 1.31.1 `.wav` з кореневих шляхів із Великими літерами
   (`Units/Human/...`) — з російського пакету видно, що так (мапа
   TOP_LEVEL робить `units→Units`), але в його маніфесті всі імена в
   нижньому регістрі; на APFS-case-insensitive це не має значення.
5. Чи потрібні правки `UI/SoundInfo/UnitsoundData.slk` при простій заміні
   файлів — ні, якщо імена/шляхи збігаються 1:1; потрібні лише для нових
   звуків.

## Джерела (read-only інспекція)

- `…/Resources/WC3Patcher/backend/wc3-patcher.sh` — `enable_local_files`,
  `balance_files`, `core_plan`, `apply_core_files`, `restore_snapshot`,
  `balance_status`.
- `…/backend/wc3-language-assets.py` — `TOP_LEVEL`, `activate_ru`,
  `restore_en`, сімлінки в корінь гри.
- `…/backend/wc3-hero-appearances.py` — голосові оверрайди
  (`voice_overrides/Units/...`, `UI/SoundInfo/UnitAckSounds.slk`).
- `Tools/State/Reforged UI/state.json`, `Tools/State/Reforged Models/state.json`
  — сімлінки пакетів у корінь гри.
- `Tools/State/Balance/snapshots/core02/snapshot.tsv` — усі 36 цілей
  «absent/original» → класика активна.
- `WC3Patcher.dylib` + `WC3Patcher/ui/Launcher ru.json` — тексти UI лаунчера
  (Game Mode: Classic 1.31.1 / Reforged 2.0.4 + UI / … + Models (Test)).
- `Folder Guide.txt`, `Readme.txt`, `Tools/Check Installation.command`.
