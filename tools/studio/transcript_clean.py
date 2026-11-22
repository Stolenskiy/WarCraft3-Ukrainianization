"""Очищення транскриптів оригіналів від «галюцинацій» Whisper (показ у студії; дані в data/local/ не змінюються)."""
import re

# Whisper «галюцинує» ці фрази на звуках без мови (крики, смерть) і дописує їх у хвіст справжніх реплік — це НЕ вотермарки.
HALLUCINATION_RE = re.compile(
    r"продолжение следует\.*|субтитры\s+(?:создавал|сделал|подготовил)\w*\s+\S+|dimatorzok"
    r"|редактор субтитров.*?корректор\s+\S+(?:\s*\S+)?|воодушевляющая музыка|спасибо за просмотр|подписывайтесь\S*", re.I)
_LATIN_RE = re.compile(r"[A-Za-zÀ-ÿ]{2,}")          # рос. транскрипт із латиницею = Whisper «перемкнув мову» (nonsense)
_RUN_RE = re.compile(r"(.)\1{5,}", re.I)            # «Оооооо…», «РАРРРРР…» — вигук без слів
_LAUGH_RUN_RE = re.compile(r"((?:[ХхГг][аеиі]-?){3})(?:[ХхГг][аеиі]-?)+")    # «ха-ха-ха-ха-…» → «ха-ха-ха…»
UNRELIABLE = "(розпізнавання ненадійне — слухайте оригінал)"
NO_SPEECH = "(без розбірливих слів — крик / звук)"


def clean_ru(text: str) -> tuple[str, str | None]:
    """Текст транскрипту для показу + позначка: None (гаразд), "no_speech" (вигук/порожньо), "unreliable" (сміття Whisper).
    Галюцинації вирізаються з хвоста справжніх реплік, а не знищують їх; зовнішні «» прибираються (UI додає свої)."""
    t = HALLUCINATION_RE.sub(" ", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    if t.startswith("«") and t.endswith("»"):
        t = t[1:-1].strip()
    if not t or _RUN_RE.search(t):
        return NO_SPEECH, "no_speech"
    if _LATIN_RE.search(t):
        return UNRELIABLE, "unreliable"
    t = _LAUGH_RUN_RE.sub(lambda m: m.group(1).rstrip("-") + "…", t)
    return t, None
