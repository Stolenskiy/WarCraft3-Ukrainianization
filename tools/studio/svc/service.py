"""Service — фасад: усі дії студії (реалізація по темах у міксинах)."""
from __future__ import annotations

from .ai_svc import AiMixin
from .base import Base
from .character_svc import CharacterMixin
from .enhance_svc import EnhanceMixin
from .eq_svc import EqMixin
from .export import ExportMixin
from .originals import OriginalsMixin
from .takes import TakesMixin
from .voices_svc import VoicesMixin


class Service(Base, TakesMixin, OriginalsMixin, ExportMixin, EqMixin, CharacterMixin, AiMixin, VoicesMixin,
              EnhanceMixin):
    """Усі дії студії. Потокобезпечний; стан пишеться на диск після кожної зміни.

    Ідентифікатори: cid — каталог (units-orc), gid — група (peon), lid — репліка (peonyes1.wav).
    Дії — у міксинах за темами: takes.py, originals.py, export.py, eq_svc.py, character_svc.py, ai_svc.py, voices_svc.py;
    доступ і серіалізація — base.py.
    """
