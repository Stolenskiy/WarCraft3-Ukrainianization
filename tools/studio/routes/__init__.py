"""Маршрути API по фічах; імпорт модулів реєструє їх у registry.ROUTES."""
from . import aistudio, catalogs, eq, gameroot, install, process, static, textinstall, voices  # noqa: F401  (порядок: voice-аудіо раніше за загальне /audio/…)
