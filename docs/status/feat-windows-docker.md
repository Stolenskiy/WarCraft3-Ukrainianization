# feat/windows-docker
Зроблено: gameconf, run.py, opener, Windows-гілки doctor/install_voices, Dockerfile+compose (зібрано й перевірено на macOS Docker Desktop), CI windows-джоб.
Далі: після злиття з редизайном — маршрут `/api/game-root` і поле «Тека гри» (`docs/plans/game-path-ui.md`); прогнати Windows-джоб у CI й виправити те, що впаде.
Ризики: Windows не перевірено на реальній машині (лише мок-тести); `STUDIO_BIND` додано в `server.serve(host=…)` — мінімальний хук (3 рядки).
