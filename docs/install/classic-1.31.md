# Встановлення: Warcraft III Classic 1.31 (RoC + TFT)

Статус: **підтримується** (перевірено на репаку 1.31.1.12173, macOS). RoC і TFT — один клієнт і один набір файлів, тож ставиться все разом.
Windows: логіка та сама, але **не перевірено на реальній Windows**.

## 0. Одноразово
1. Python 3.11 і репозиторій: `python tools/run.py setup` (macOS: `make setup`). Для шрифтів і FDF потрібен PyCASC: `make setup-refs`.
2. Дозвіл на «вільні» файли (гра читає файли з кореня гри поверх CASC):
   - **macOS:** `defaults write "com.blizzard.WarcraftIII" "Allow Local Files" -int 1` (перевірка: `defaults read "com.blizzard.WarcraftIII"`).
   - **Windows:** `reg add "HKCU\Software\Blizzard Entertainment\Warcraft III" /v "Allow Local Files" /t REG_DWORD /d 1 /f` (це робите ви самі).
3. Тека гри: `python tools/run.py game-root` (автопошук; інакше `python tools/run.py game-root "<шлях>"`).

## 1. Встановлення (три шляхи)
Спершу завжди **план** (нічого не пишемо), потім `--apply`:

| Хочу | Команда |
|---|---|
| лише текст | `python tools/run.py install --target classic-1.31 --parts text` |
| лише голос | `python tools/run.py install --target classic-1.31 --parts voice` |
| усе разом | `python tools/run.py install --target classic-1.31 --parts text,voice` |

macOS-скорочення: `make install-text`, `make install-voices`, `make install` (додайте `APPLY=1`, щоб справді записати).
`--full` додає кампанії й субтитри (~1 ГБ); типово LIGHT (~2 МБ потрібного). `--ref <sha|тег>` фіксує версію перекладу, інакше береться найновіша.

Що робить текст: завантажує переклад [warcraft-in-ua](https://github.com/warcraft-in-ua/WarCraft3-Reforged-Ukrainian) у локальний кеш
(`docs/decisions/0006-text-pack-sourcing.md`), додає підсвічені гарячі клавіші `Атака (|cffffcc00A|r)`, будує FDF формату 1.31 із ваших власних
файлів гри, бере кириличні шрифти з вашої гри. Перезапустіть гру (вийти повністю і Play).

## 2. Відкат
`python tools/run.py uninstall --target classic-1.31 --parts text,voice` — повертає оригінали з `Backups/ua-text/` і `Backups/ua-voices/`;
змінене вами після встановлення не чіпає. Журнал із комітом upstream та sha256: `Backups/ua-text/CHANGE-LOG.txt`.

## 3. Відомі проблеми
- Порожні кнопки меню: лишились FDF Reforged — `uninstall --parts text`, або видаліть `UI/framedef/*.fdf` (`docs/fix-blank-ui.md`).
- Квадратики замість літер: не встановились кириличні шрифти (немає PyCASC/мовного пакета) — `make setup-refs` і повторіть, або `--fonts-from <тека>`.
- Лаунчер «repair» перезаписує файли — повторіть `install`.
- Гарячі клавіші: Reforged-переклад їх не містить, ми додаємо в Tip (і до кожного рівня героїчних здібностей); значення `Hotkey=` не змінюємо.
- Симлінки репаку (`Units/orc/<юніт>` → `Mods/…`): інсталятор матеріалізує теку з відкатом; у `Mods/` нічого не пишемо.
