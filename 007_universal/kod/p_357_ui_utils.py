import os
import time
import tempfile
import numpy as np
import soundfile as sf
from typing import Tuple, Optional, Dict, Any

def save_audio_part(audio: np.ndarray, sr: int, idx: int, output_dir: str) -> str:
    """Зберігає аудіо частину в файл."""
    # Конвертація до float32
    if isinstance(audio, np.ndarray):
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
    else:
        audio = np.array(audio, dtype=np.float32)
    
    # Збереження
    part_path = os.path.join(output_dir, f"part_{idx:03d}.wav")
    try:
        sf.write(part_path, audio, sr)
        return part_path
    except Exception:
        # Fallback до тимчасової папки
        with tempfile.TemporaryDirectory() as tmpdir:
            part_path = os.path.join(tmpdir, f"part_{idx:03d}.wav")
            sf.write(part_path, audio, sr)
            return part_path

def calculate_remaining_time(start_time: float, times_per_part: list, total_parts: int) -> str:
    """Розраховує залишений час."""
    if times_per_part:
        avg_time = sum(times_per_part) / len(times_per_part)
        est_total = avg_time * total_parts
        remaining_secs = int(start_time + est_total - time.time())
        rem_min, rem_sec = divmod(max(remaining_secs, 0), 60)
        return f"{rem_min} хв {rem_sec} сек"
    return "Розрахунок..."

def read_input_text(text_input: str, file_input: Optional[str]) -> str:
    """Читає текст з вводу або файлу."""
    if text_input and text_input.strip():
        return text_input
    elif file_input:
        with open(file_input, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError("Введіть текст або виберіть файл")

def create_output_directory() -> str:
    """Створює папку для виходу."""
    output_dir = os.path.join(os.getcwd(), "output_audio", f"session_{int(time.time())}")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def prepare_config_models():
    """Конфігурація не потрібна."""
    return {}