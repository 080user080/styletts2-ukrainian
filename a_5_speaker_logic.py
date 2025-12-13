"""
a_5_speaker_logic.py
Парсинг тегів #gN, обчислення ефективної швидкості, валідація подій.
"""

import re
from typing import List


def parse_script_events(text: str, voices_flat: List[str], max_speakers: int = 30) -> List[dict]:
    """
    Парсер сценарію для Multi Dialog.
    
    Дозволяє:
      #gN[_slow|_fast|_slowNN|_fastNN] <текст>  --> подія voice
      #<sfx_id>                                 --> подія sfx
    
    Повертає список словників:
      {"type": "voice", "g": int, "suffix": str, "text": str}
      {"type": "sfx", "id": str, "params": {}}
    """
    from a_6_text_processing import normalize_text
    from a_3_sfx_engine import get_sfx_config
    
    events: List[dict] = []
    if not isinstance(text, str):
        return events
    
    lines = normalize_text(text).splitlines()
    
    # Патерн для voice: #g1: текст або #g2_fast95: текст
    voice_pat = re.compile(
        r"^#g\s*([1-9]|[12][0-9]|30)(?:_((?:slow|fast)(?:\d{1,3})?))?\s*:??\s+(.*)$",
        re.IGNORECASE
    )
    # Патерн для SFX
    sfx_pat = re.compile(r'^#([A-Za-z0-9]+)\s*$', re.IGNORECASE)
    
    for line_no, raw_ln in enumerate(lines, start=1):
        ln = raw_ln.strip()
        if not ln:
            continue
        
        m_voice = voice_pat.match(ln)
        if m_voice:
            g_str, suffix, text_body = m_voice.groups()
            g_num = int(g_str)
            suffix = suffix.lower() if suffix else ""
            if not text_body.strip():
                raise RuntimeError(f"Порожній текст після тега #g{g_num} на рядку {line_no}")
            if g_num < 1 or g_num > max_speakers:
                raise RuntimeError(f"Неприпустимий номер спікера: {g_num} на рядку {line_no}")
            events.append({"type": "voice", "g": g_num, "suffix": suffix, "text": text_body})
            continue
        
        m_sfx = sfx_pat.match(ln)
        if m_sfx:
            sfx_id = m_sfx.group(1)
            cfg = get_sfx_config()
            if sfx_id not in cfg.get('sounds', {}):
                raise RuntimeError(f"SFX із id '{sfx_id}' не знайдено у конфігу sfx.yaml (рядок {line_no})")
            events.append({"type": "sfx", "id": sfx_id, "params": {}})
            continue
        
        # Коментар або звичайний текст
        if ln.startswith('#'):
            continue
        # Звичайний текст для g1
        events.append({"type": "voice", "g": 1, "suffix": "", "text": ln})
    
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
            val = float(suf[4:]) / 100.0
            return val
        except Exception:
            pass
    
    if suf.startswith('fast') and len(suf) > 4:
        try:
            val = float(suf[4:]) / 100.0
            return val
        except Exception:
            pass
    
    # Використати значення слайдера
    if 1 <= g_num <= len(speeds_flat):
        try:
            return float(speeds_flat[g_num - 1])
        except Exception:
            return default_speed
    
    return default_speed
