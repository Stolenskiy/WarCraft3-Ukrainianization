# Встановлення: класичні MPQ-клієнти 1.26–1.29

Статус: **EXPERIMENTAL, не перевірено** (немає клієнта 1.26–1.29 для тесту). Нижче — що реалізовано і чесна оцінка.

## Спосіб: вільні файли, не патч-MPQ
- «Allow Local Files» у 1.2x існує (реєстр `HKCU\Software\Blizzard Entertainment\Warcraft III`, DWORD `Allow Local Files`=1; macOS-клієнт 1.26 —
  `defaults write "com.blizzard.WarcraftIII" "Allow Local Files" -int 1`) — [Hive](https://www.hiveworkshop.com/threads/allow-local-files.305678),
  [Hive](https://www.hiveworkshop.com/threads/local-files.107129/). Корінь — сама тека гри (`_retail_` лише з 1.32.7). Файл кладемо за внутрішнім
  шляхом MPQ (`Units\…`, `UI\…`).
- Патч-MPQ (`war3patch.mpq`) відхилено: потрібен запис MPQ (не stdlib), ризик зіпсувати архів, відкат складніший. Оцінка: 1-2 дні на модуль MPQ + тести.

## Що робить `install --target legacy`
Ті самі Units/UI `*.txt` з upstream, **з підсвіченими клавішами** (як Classic), без `*skin*strings.txt` і `doodads/` (їх у 1.26 немає); без шрифтів.
FDF: лише якщо ви витягнули `UI\FrameDef\*.fdf` зі свого `war3.mpq` (MPQ Editor) і дали `--fdf-template <тека>`; ідентифікатори/формат 1.2x не перевірено.

## Чесні ризики
- Переклад upstream написано під баланс Reforged: описи, ціни й нові здібності можуть не збігатись із 1.26.
- Назви файлів у 1.2x інші за регістром/складом (`UI\ChatHelp-War3-enUS.txt`); невідомі файли гра ігнорує, але повного перекладу не гарантуємо.
- Голос: ті самі шляхи `Units\<раса>\<юніт>\*.wav` (формат як в оригіналі, wav 22050 Гц mono) — найімовірніше працює, не перевірено.

## Команди
`python tools/run.py install --target legacy --parts text,voice [--fdf-template <тека>]` (план), потім `--apply`; відкат `uninstall --target legacy --parts text,voice`.
