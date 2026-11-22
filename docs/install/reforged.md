# Встановлення: Warcraft III: Reforged (1.32+ / 2.x / 3.x)

Статус: **EXPERIMENTAL, не перевірено** на справжньому Reforged. Текст — рідний формат upstream; голос — незалежне припущення (нижче).
Версії: Reforged 2.0.4 (січень 2026) — остання 2.0.x; 3.0.0 (12.09.2026) замінила Classic HD на «Definitive Edition» (три режими
графіки: Classic / Definitive Edition / Reforged) і оголосила застарілою систему аддонів; актуальна 3.0.1 (build 24342).
Джерела: [patch information](https://warcraft.wiki.gg/wiki/Warcraft_III_patch_information), [Patch 3.0.0](https://liquipedia.net/warcraft/Patch_3.0.0),
[нотатки патчів](https://us.forums.blizzard.com/en/warcraft3/t/warcraft-iii-reforged-forsaken-kingdom-patch-notes/38400).
Для якої версії зроблений переклад upstream, автори не пишуть (у репозиторії лише тека «Reforged 2.0» з картами); **сумісність з 3.0 не перевірено**.

## 0. Одноразово
- Корінь «вільних» файлів з 1.32.7: `<Warcraft III>\_retail_` (Windows) / `…/Warcraft III/_retail_` (macOS). Інсталятор сам бере `_retail_`.
- «Allow Local Files»: **Windows** — `reg add "HKCU\Software\Blizzard Entertainment\Warcraft III" /v "Allow Local Files" /t REG_DWORD /d 1 /f`;
  **macOS** — `defaults write "com.blizzard.Warcraft III" "Allow Local Files" -int 1` (домен із ПРОБІЛОМ, не як у репаку 1.31).
  Частина спільноти пише, що в Reforged ключ уже не потрібен, а файли в `_retail_` читаються самі, інші — що потрібен; тож ключ радимо увімкнути (він нічого не ламає). Чи працює це в 3.0 — не підтверджено ([Hive](https://www.hiveworkshop.com/threads/local-files.330849),
  [Blizzard forum](https://us.forums.blizzard.com/en/warcraft3/t/local-files/25860)).

## 1. Встановлення
`python tools/run.py install --target reforged --parts text` (або `voice`, або `text,voice`), потім з `--apply`. Розмітку клавіш не додаємо: Reforged показує їх сам.
Тека гри — `python tools/run.py game-root "<корінь Warcraft III>"` (не `_retail_`).

## 2. Голос: що відомо з публічних джерел (не перевірено нами)
- Громадський посібник Blizzard: розпаковані з класичних MPQ теки `Sound`, `Units`, `movies`, покладені в `_retail_`, підміняють голоси; у 1.32.7 це
  зламалось і було виправлено новою інструкцією ([форум](https://us.forums.blizzard.com/en/warcraft3/t/classic-pre-reforged-voices-fix-fixed-v1327-problem/24741)).
  Тобто шляхи `Units/<раса>/<юніт>/<файл>` те саме, що в Classic, імовірно працюють; формат у посібнику — wav із класичних архівів, flac у Reforged
  використовується для частини оригіналів. Наш wav 22050 Гц mono — найближче до класичних файлів.
- HD/SD: джерел про вплив режиму на loose-підміну немає; на Hive скаржаться на мовчазні HD-моделі з custom-звуками ([тред](https://www.hiveworkshop.com/threads/some-custom-units-cant-use-sound-sets-as-their-voice-lines-in-hd-need-fix-or-help.336381)).
  Перевіряйте в обох режимах; у CASC звук локалізації лежить під `_locales/<мова>.w3mod/units/…` (перевірено на 1.31).

## 3. Відкат і проблеми
`python tools/run.py uninstall --target reforged --parts text,voice`. Бекап — `_retail_/Backups/ua-text/`, `_retail_/Backups/ua-voices/`.
Якщо меню порожнє або гра лається — відкат і повідомте в issue з версією гри. Шрифти беруться з upstream як є.
