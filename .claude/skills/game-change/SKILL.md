---
name: game-change
description: Use before ANY write to the installed game folder (/Applications/Warcraft III Classic) — installing approved voice files from game-files/, UI fdf/fonts, maps, txt, copying, replacing or symlinking. Safe procedure covering backup, change log, symlink pitfalls, verification and rollback.
---

# Зміна файлів у теці гри

Гра: `/Applications/Warcraft III Classic` (далі `$G`). Перед будь-яким записом — спершу
спитати користувача (це зовнішня, важко відворотна дія), якщо він не дозволив явно в цій сесії.

## Заборонено
- Писати в `$G/Data/` (CASC) і в `$G/Mods/**` (у т.ч. **крізь симлінки**).
- Видаляти чужі файли. Відкат — лише з бекапу, який створили ми.

## Процедура
1. **Ім'я зміни:** `<короткий-опис>-<YYYYMMDD>` → тека `$G/Backups/<ім'я>/`.
2. **План:** список відносних шляхів, що будуть створені/замінені. Для кожного — куди запис
   піде НАСПРАВДІ (симлінком може бути будь-який предок, напр. `Units/orc/<unit>`):
   `python3 -c "import os,sys;g=os.path.realpath(sys.argv[1]);r=os.path.realpath(sys.argv[2]);print(r, 'OK' if r.startswith(g+'/') and not r.startswith((g+'/Mods/',g+'/Data/')) else 'STOP')" "$G" "$G/<rel>"`.
   `STOP` → голоси юнітів: `$G/Units/orc/<unit>` здебільшого симлінк на `Mods/Reforged Models/...`.
   Автоматично це робить `tools/install_voices.py` (`make install-voices APPLY=1` або кнопка
   «Встановити в гру» в студії): матеріалізація = `unlink` симлінка → реальна тека з абсолютними
   симлінками на кожен елемент цілі (як у `Units/orc/peon`) → наш wav звичайним файлом; у
   `manifest.json` — шлях симлінка та його `readlink`; `--uninstall` видаляє теку (якщо в ній лише
   наші симлінки) і повертає симлінк із тим самим рядком. Вручну, якщо потрібно: зберегти лінк у бекап **як лінк** (`cp -P`, плюс записати `readlink` у лог — він
   відносний), прибрати лінк, створити реальну теку, у ній — симлінки на вміст оригінальної
   цілі + наші файли поверх. Відкат: прибрати теку, `ln -s <readlink-значення>` назад.
3. **Бекап:** кожен файл, що буде перезаписаний, скопіювати в `$G/Backups/<ім'я>/<rel>`
   (`ditto`, зберігає атрибути). Нові файли — лише перелічити.
4. **Застосувати** зміну (`ditto`/`cp -p`). Формат голосу перевірити: `afinfo` →
   `1 ch, 22050 Hz, Int16`.
5. **CHANGE-LOG.txt** у `$G/Backups/<ім'я>/` (формат як у `fix2-ukrainian-ui`): що робить зміна,
   BACKED UP (sha256 + шлях), INSTALLED FILES (sha256), SOURCES, ROLLBACK (точні команди).
   sha256: `shasum -a 256 <file>`.
6. **Перевірка:** `defaults read com.blizzard.WarcraftIII "Allow Local Files"` = 1; файли на місці;
   попросити користувача перевірити в грі (агент гру не запускає й не бачить).
7. **Документація:** рядок у `docs/STATUS.md`; якщо з'явилась нова пастка — у `docs/gotchas.md` (1 рядок).

## Відкат
Виконати ROLLBACK із CHANGE-LOG.txt; перевірити sha256 відновлених файлів проти BACKED UP.
