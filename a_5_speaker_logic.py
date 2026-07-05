"""
a_5_speaker_logic.py
Парсинг тегів #gN, #sfx, #p (пауза), обчислення ефективної швидкості, валідація подій.
"""

import re
from typing import List


def _is_empty_or_punctuation_only(text: str) -> bool:
    """
    Перевіряє, чи текст порожній або містить лише розділові знаки та пробіли.
    """
    if not text or not text.strip():
        return True

    cleaned = text.strip()

    punctuation_chars = {
        '"', "'", '\u201c', '\u201d', '\u2018', '\u2019', '\u00ab', '\u00bb', '\u201e', '\u201c',
        '.', ',', ';', ':', '!', '?', '\u2026', '\u2014', '\u2013', '-',
        '(', ')', '[', ']', '{', '}', '<', '>',
        '/', '\\', '|', '_', '*', '+', '=', '~', '`',
        '\u2116', '\u00a7', '\u00b0', '\u00b7', '\u2022', '\u201a', '\u201b', '\u2039', '\u203a',
        '\t', '\n', '\r', '\u00a0', '\u200b', '\ufeff'
    }

    for char in cleaned:
        if char not in punctuation_chars and not char.isspace():
            return False

    return True


def parse_script_events(text: str, voices_flat: List[str], max_speakers: int = 30) -> List[dict]:
    """
    Парсер сценарію для Multi Dialog.

    Підтримує:
      #gN[_slow|_fast|_slowNN|_fastNN] <текст>  → подія voice
      #<sfx_id>                                  → подія sfx
      #p<X.X>   або   #p(<X.X>)                 → подія pause (0.1–9.9 с)

    Порожні події або події з лише розділовими знаками ігноруються.

    Повертає список словників:
      {"type": "voice",  "g": int, "suffix": str, "text": str}
      {"type": "sfx",    "id": str, "params": {}}
      {"type": "pause",  "duration": float}          ← нове
    """
    from a_6_text_processing import normalize_text
    from a_3_sfx_engine import get_sfx_config, parse_pause_tag

    events: List[dict] = []
    if not isinstance(text, str):
        return events

    lines = normalize_text(text).splitlines()

    # Патерн для voice: #g1 текст або #g2_fast95: текст
    voice_pat = re.compile(
        r"^#g\s*([1-9]|[12][0-9]|30)(?:_((?:slow|fast)(?:\d{1,3})?))?\s*:??\s+(.*)$",
        re.IGNORECASE
    )
    # Патерн для SFX (однослівний ідентифікатор, не схожий на #p + число)
    sfx_pat = re.compile(r'^#([A-Za-z][A-Za-z0-9]*)\s*$', re.IGNORECASE)

    # Патерн для паузи: #p1.5 або #p(1.5) — весь рядок
    pause_pat = re.compile(r'^\s*#p\(?\s*([0-9](?:\.[0-9])?)\s*\)?\s*$', re.IGNORECASE)

    skipped_empty = 0

    for line_no, raw_ln in enumerate(lines, start=1):
        ln = raw_ln.strip()
        if not ln:
            continue

        # ── 1. Тег паузи (#p1.5 або #p(1.5)) ──────────────────────────────
        m_pause = pause_pat.match(ln)
        if m_pause:
            try:
                duration = parse_pause_tag(ln)
            except ValueError as e:
                raise RuntimeError(f"Некоректний тег паузи на рядку {line_no}: {e}")
            if duration is not None:
                events.append({"type": "pause", "duration": duration})
                print(f"⏸ Пауза {duration} с (рядок {line_no})")
            continue

        # ── 2. Тег голосу (#gN ...) ────────────────────────────────────────
        m_voice = voice_pat.match(ln)
        if m_voice:
            g_str, suffix, text_body = m_voice.groups()
            g_num = int(g_str)
            suffix = suffix.lower() if suffix else ""

            if _is_empty_or_punctuation_only(text_body):
                skipped_empty += 1
                print(f"⚠️ Пропущено порожню подію #g{g_num} на рядку {line_no}: '{text_body}'")
                continue

            if g_num < 1 or g_num > max_speakers:
                raise RuntimeError(f"Неприпустимий номер спікера: {g_num} на рядку {line_no}")

            events.append({"type": "voice", "g": g_num, "suffix": suffix, "text": text_body})
            continue

        # ── 3. Тег SFX (#sfx_id) ──────────────────────────────────────────
        m_sfx = sfx_pat.match(ln)
        if m_sfx:
            sfx_id = m_sfx.group(1)
            cfg = get_sfx_config()
            if sfx_id not in cfg.get('sounds', {}):
                raise RuntimeError(
                    f"SFX із id '{sfx_id}' не знайдено у конфігу sfx.yaml (рядок {line_no})"
                )
            events.append({"type": "sfx", "id": sfx_id, "params": {}})
            continue

        # ── 4. Коментар (#...) ────────────────────────────────────────────
        if ln.startswith('#'):
            continue

        # ── 5. Звичайний текст (без тегу) → g1 ───────────────────────────
        if not _is_empty_or_punctuation_only(ln):
            events.append({"type": "voice", "g": 1, "suffix": "", "text": ln})
        else:
            skipped_empty += 1
            print(f"⚠️ Пропущено порожній рядок {line_no}: '{ln}'")

    if skipped_empty > 0:
        print(f"ℹ️ Всього пропущено порожніх подій: {skipped_empty}")

    return events


def _compute_speed_effective(
    g_num: int,
    suffix: str,
    speeds_flat: List[float],
    ignore_speed: bool,
    default_speed: float = 0.88
) -> float:
    """
    Обчислює ефективну швидкість для voice-події.

    Пріоритет:
      1. Якщо ignore_speed=True → default_speed
      2. Якщо suffix='slow'/'fast' → 0.80 / 1.20
      3. Якщо suffix='slowNN'/'fastNN' → NN/100
      4. Інакше → значення слайдера для g_num
    """
    if ignore_speed:
        return default_speed

    suf = suffix.lower() if suffix else ""

    if suf == 'slow':
        return 0.80
    if suf == 'fast':
        return 1.20

    if suf.startswith('slow') and len(suf) > 4:
        try:
            return float(suf[4:]) / 100.0
        except Exception:
            pass

    if suf.startswith('fast') and len(suf) > 4:
        try:
            return float(suf[4:]) / 100.0
        except Exception:
            pass

    if 1 <= g_num <= len(speeds_flat):
        try:
            return float(speeds_flat[g_num - 1])
        except Exception:
            return default_speed

    return default_speed
