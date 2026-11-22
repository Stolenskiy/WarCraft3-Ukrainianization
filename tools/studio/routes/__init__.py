"""Маршрути API по фічах; імпорт модулів реєструє їх у registry.ROUTES."""
from . import catalogs, eq, install, process, static, voices  # noqa: F401  (порядок: voice-аудіо раніше за загальне /audio/…)
