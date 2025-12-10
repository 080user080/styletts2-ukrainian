"""
p_304_tts_verbalizer_wrapper.py - Обгортка для вербалізації тексту
(Виділено з app.py)
"""

import re
from typing import Dict, Any, List  # ДОДАТИ ЦЕЙ РЯДОК
from typing import List
import logging

def split_to_parts(text: str, max_length: int = 150) -> List[str]:
    """
    Розбити текст на частини.
    Видобуто з app.py
    """
    split_symbols = '.?!:'
    parts = ['']
    index = 0
    
    for s in text:
        parts[index] += s
        if s in split_symbols and len(parts[index]) > max_length:
            index += 1
            parts.append('')
    
    # Видалити порожні частини
    parts = [p.strip() for p in parts if p.strip()]
    return parts

def verbalize_text(text: str, verbalizer) -> str:
    """
    Вербалізувати текст через Verbalizer.
    Видобуто з app.py
    """
    if not verbalizer:
        return text
    
    parts = split_to_parts(text)
    verbalized = ''
    for part in parts:
        verbalized += verbalizer.generate_text(part)
    return verbalized.strip()

def prepare_config_models():
    """Повертає модель конфігурації (опційно)."""
    return {}

def initialize(app_context: Dict[str, Any]):
    """
    Ініціалізація обгортки для вербалізації.
    Додає утилітні функції в контекст.
    """
    logger = app_context.get('logger', logging.getLogger("TTSVerbalizerWrapper"))
    
    # Додати функції в контекст
    app_context['tts_utils'] = {
        'split_to_parts': split_to_parts,
        'verbalize_text': lambda text: verbalize_text(text, app_context.get('verbalizer'))
    }
    
    logger.info("Обгортка вербалізації ініціалізована")
    return app_context['tts_utils']

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка обгортки."""
    if 'tts_utils' in app_context:
        del app_context['tts_utils']