"""
a_2_synthesis.py
Синтез мовлення з fallback-стратегіями для PL-BERT.
"""

import traceback
import numpy as np
from typing import Tuple, Sequence, List

from a_6_text_processing import normalize_text, split_to_parts, PLBERT_SAFE, HARD_MAX_TOKENS, CHAR_CAP, _tok_len
from a_7_utils import NoProgress, _should_use_single_voice, _needs_plbert_fallback


def _synthesize_chunk(chunk: str, voice: str | None, speed: float) -> Tuple[int, np.ndarray]:
    """
    Синтезує один шматок тексту з fallback-стратегіями для PL-BERT.
    
    Returns: (sample_rate, audio_array)
    """
    # Імпорт тут щоб уникнути циклічних залежностей
    from app import synthesize
    
    use_single = _should_use_single_voice(voice)
    
    def run_for_parts(parts: Sequence[str]) -> Tuple[int, np.ndarray]:
        waves: List[np.ndarray] = []
        sr_local: int | None = None
        mode = "single" if use_single else "multi"
        voice_name = None if use_single else (voice or None)
        
        for part in parts:
            txt = normalize_text(part)
            sr_local, audio = synthesize(mode, txt, speed, voice_name=voice_name, progress=NoProgress())
            waves.append(audio)
        
        if sr_local is None:
            raise RuntimeError("Synthesis did not return sample rate")
        
        audio_np = waves[0] if len(waves) == 1 else np.concatenate(waves, axis=0)
        return sr_local, audio_np
    
    # Перевірити розмір, потім спробувати синтез
    parts: List[str] = [chunk]
    if _tok_len(chunk) > PLBERT_SAFE or len(chunk) > CHAR_CAP:
        parts = split_to_parts(chunk, max_tokens=min(HARD_MAX_TOKENS, PLBERT_SAFE // 2))
    
    try:
        return run_for_parts(parts)
    except Exception:
        first_err = traceback.format_exc()
        if _needs_plbert_fallback(first_err):
            try:
                # Агресивнішою розбиття
                fallback_parts = split_to_parts(chunk, max_tokens=PLBERT_SAFE // 3)
                return run_for_parts(fallback_parts)
            except Exception:
                raise RuntimeError(f"Synthesis error:\n{traceback.format_exc()}") from None
        raise RuntimeError(f"Synthesis error:\n{first_err}") from None
