"""
a_7_utils.py
Допоміжні утиліти загального призначення.
"""

class NoProgress:
    """Мінімальний об'єкт-заглушка для інтерфейсу progress."""
    def tqdm(self, iterable):
        return iterable


def _safe_float(value, default: float = 1.0) -> float:
    """Безпечно перетворює значення у float, повертає default при помилці."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_text_source(text_input: str | None, file_path: str | None) -> str:
    """Читає текст із поля або файлу, повертає обов'язково str."""
    if text_input and text_input.strip():
        return text_input
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    raise RuntimeError("Немає тексту для озвучення")


def _should_use_single_voice(voice: str | None) -> bool:
    """Перевіряє, чи потрібно використовувати single-voice режим (для Філатова)."""
    if not voice:
        return False
    vname_l = voice.lower()
    return ("філат" in vname_l) or ("filat" in vname_l)


def _needs_plbert_fallback(error_text: str) -> bool:
    """Перевіряє, чи потрібна fallback-стратегія при помилці токена."""
    return (
        "must match the existing size (512)" in error_text
        or "expanded size of the tensor" in error_text
    )


def format_hms(seconds):
    """Форматує секунди як HH:MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"
