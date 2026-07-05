"""
a_3_sfx_engine.py
Читання sfx.yaml, завантаження аудіо, нормалізація, fade.
Підтримка генерації пауз (#p1.5 або #p(1.5), 0.1–9.9 секунд).
"""

import os
import re
import math
import numpy as np
import soundfile as sf
import yaml
from scipy import signal
from typing import Tuple


# ---------------------------------------------------------------------------
# Утиліти паузи
# ---------------------------------------------------------------------------

# Підтримуємо обидва формати: #p1.5  і  #p(1.5)
# Використовується лише для валідації/витягування значення — парсинг рядків у a_5.
_PAUSE_VALUE_RE = re.compile(r'^\s*#p\(?\s*([0-9](?:\.[0-9])?)\s*\)?\s*$', re.IGNORECASE)


def parse_pause_tag(line: str) -> float | None:
    """
    Намагається розпізнати рядок як тег паузи.

    Підтримувані формати (на початку рядка, весь рядок):
        #p1.5     → 1.5
        #p(1.5)   → 1.5
        #p0.1     → 0.1
        #p9.9     → 9.9

    Returns:
        float — тривалість у секундах, або None якщо не розпізнано.

    Raises:
        ValueError — якщо синтаксис правильний, але значення поза [0.1, 9.9].
    """
    m = _PAUSE_VALUE_RE.match(line)
    if not m:
        return None
    duration = float(m.group(1))
    if not (0.1 <= duration <= 9.9):
        raise ValueError(
            f"Тривалість паузи {duration!r} поза допустимим діапазоном 0.1–9.9 с: '{line.strip()}'"
        )
    return duration


def generate_pause(duration_sec: float, sample_rate: int) -> np.ndarray:
    """
    Генерує масив нулів (тиша) заданої тривалості.

    Args:
        duration_sec: тривалість паузи в секундах (0.1–9.9)
        sample_rate:  частота дискретизації, Гц

    Returns:
        np.ndarray dtype=float32, форма (N,)

    Raises:
        ValueError: якщо duration_sec поза діапазоном 0.1–9.9
    """
    if not (0.1 <= duration_sec <= 9.9):
        raise ValueError(
            f"Тривалість паузи {duration_sec!r} поза допустимим діапазоном 0.1–9.9 с"
        )
    n_samples = int(round(duration_sec * sample_rate))
    return np.zeros(n_samples, dtype=np.float32)


# ---------------------------------------------------------------------------
# SFX конфіг і завантаження
# ---------------------------------------------------------------------------

def _load_sfx_config(path: str = "sfx.yaml") -> dict:
    """
    Завантажує конфіг SFX із YAML.
    Пошук у порядку: ./sfx.yaml, ./sound/sfx.yaml
    """
    cfg = {"normalize_dbfs": -16, "sounds": {}}
    candidates = [
        os.path.join(os.getcwd(), "sfx.yaml"),
        os.path.join(os.getcwd(), "sound", "sfx.yaml"),
    ]
    found = None
    for p in candidates:
        if os.path.exists(p):
            found = p
            break

    if not found:
        return cfg

    try:
        with open(found, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                cfg.update(data)
        cfg["_cfg_dir"] = os.path.dirname(found)
    except Exception:
        pass

    return cfg


def get_sfx_config() -> dict:
    """Динамічне читання sfx.yaml на вимогу."""
    return _load_sfx_config()


def _load_and_process_sfx(sfx_id: str, target_sr: int) -> Tuple[int, np.ndarray]:
    """
    Завантажує і обробляє SFX:
    - Читає файл
    - Ресемплює до target_sr
    - Нормалізує за normalize_dbfs
    - Застосовує gain_db
    - Додає fade-in/fade-out (30 мс)

    Returns: (sample_rate, np.array)
    """
    cfg_all = get_sfx_config()
    cfg = cfg_all.get('sounds', {}).get(sfx_id)
    if not cfg:
        raise RuntimeError(f"SFX конфігурація відсутня для id '{sfx_id}'")

    src_file = cfg.get('file')
    if not src_file:
        raise RuntimeError(f"Файл для SFX '{sfx_id}' не вказаний у конфігурації")

    # Пошук файлу: декілька варіантів шляхів
    possible_paths = [src_file]
    possible_paths.append(os.path.join(os.getcwd(), src_file))

    cfg_dir = cfg_all.get("_cfg_dir")
    if cfg_dir:
        possible_paths.append(os.path.join(cfg_dir, src_file))
        possible_paths.append(os.path.join(cfg_dir, "sound", src_file))

    script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else None
    if script_dir:
        possible_paths.append(os.path.join(script_dir, src_file))
        possible_paths.append(os.path.join(script_dir, "sound", src_file))

    audio_path = None
    for p in possible_paths:
        if p and os.path.exists(p):
            audio_path = p
            break

    if not audio_path:
        tried = ", ".join([p for p in possible_paths if p])
        raise RuntimeError(
            f"Файл SFX '{src_file}' не знайдено (id: '{sfx_id}'). Шляхи: {tried}"
        )

    # Читання аудіо
    data, sr = sf.read(audio_path)
    data = np.asarray(data, dtype=np.float32)

    # Моно
    if data.ndim > 1:
        data = data.mean(axis=1)

    # Ресемпл
    if sr != target_sr:
        duration = data.shape[0] / sr
        target_len = int(round(duration * target_sr))
        if target_len <= 0:
            target_len = 1
        data = signal.resample(data, target_len)
        sr = target_sr

    # Нормалізація гучності
    normalize_dbfs = cfg_all.get('normalize_dbfs')
    if cfg.get('normalize') is False:
        normalize_dbfs = None

    rms = math.sqrt(np.mean(data ** 2)) if data.size else 0.0
    if rms > 0:
        current_dbfs = 20 * math.log10(rms)
    else:
        current_dbfs = -float('inf')

    total_gain_db = float(cfg.get('gain_db', 0.0))
    if normalize_dbfs is not None and current_dbfs > -float('inf'):
        total_gain_db += (float(normalize_dbfs) - current_dbfs)

    gain_factor = 10.0 ** (total_gain_db / 20.0)
    data = data * gain_factor

    # Fade-in/fade-out (30 мс)
    fade_ms = 30
    fade_len = int(sr * fade_ms / 1000.0)
    fade_len = max(fade_len, 1)

    if data.size >= fade_len:
        ramp_in = np.linspace(0.0, 1.0, fade_len, dtype=data.dtype)
        data[:fade_len] *= ramp_in
        ramp_out = np.linspace(1.0, 0.0, fade_len, dtype=data.dtype)
        data[-fade_len:] *= ramp_out

    return sr, data
