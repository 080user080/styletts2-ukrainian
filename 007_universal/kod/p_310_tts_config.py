# p_310_tts_config.py
"""
Конфігурація TTS модуля.
Визначає всі моделі Pydantic для налаштування TTS системи.

🔄 ОНОВЛЕНО:
  - Додана SFXSoundConfig
  - Розширена документація
  - Інтеграція з dialog_parser
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum

class SpeedMode(Enum):
    """Режими швидкості озвучення."""
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"
    CUSTOM = "custom"

class SpeakerConfig(BaseModel):
    """Конфігурація одного спікера."""
    id: int = Field(ge=1, le=30)
    name: str = "Unnamed Speaker"
    voice: Optional[str] = None
    speed: float = Field(0.88, ge=0.5, le=2.0)
    enabled: bool = True

class TTSConfig(BaseModel):
    """Головна конфігурація TTS модуля."""
    enabled: bool = True
    default_speed: float = Field(0.88, ge=0.5, le=2.0)
    speaker_max: int = Field(30, ge=1, le=30)
    output_dir: str = "output_audio"
    autoplay: bool = False
    autosave: bool = True
    max_tokens: int = Field(280, ge=100, le=512)
    char_cap: int = Field(1200, ge=500, le=5000)
    progress_poll_interval: float = Field(1.0, ge=0.1, le=5.0)
    
    # SFX налаштування
    sfx_enabled: bool = True
    sfx_config_path: str = "sfx.yaml"
    
    # Параметри якості
    sample_rate: int = Field(24000, ge=8000, le=48000)
    normalize_volume: bool = True
    target_dbfs: int = -16

class SFXSoundConfig(BaseModel):
    """🆕 Конфігурація одного звукового ефекту."""
    file: str
    gain_db: float = 0.0
    normalize: bool = True
    enabled: bool = True

class SFXConfig(BaseModel):
    """🔄 ОНОВЛЕНО: Конфігурація звукових ефектів."""
    normalize_dbfs: int = -16
    default_sr: int = 24000
    default_speed: float = 0.88
    sounds: Dict[str, SFXSoundConfig] = Field(default_factory=dict)

class GradioUIConfig(BaseModel):
    """Конфігурація Gradio інтерфейсу."""
    port: int = Field(7860, ge=1000, le=65535)
    server_name: str = "0.0.0.0"
    share: bool = False
    theme: str = "default"
    width: str = "100%"
    height: int = 600
    show_error: bool = True
    analytics_enabled: bool = False

class ProcessingConfig(BaseModel):
    """🔄 ОНОВЛЕНО: Конфігурація обробки тексту (для dialog_parser)."""
    preserve_plus_symbols: bool = True  # Зберегати '+' для наголосу
    normalize_unicode: bool = True
    split_by_sentences: bool = True
    max_sentence_length: int = 200
    remove_control_chars: bool = True

class DialogParserConfig(BaseModel):
    """🆕 Конфігурація Dialog Parser."""
    enabled: bool = True
    max_tokens: int = Field(280, ge=100, le=512)
    char_cap: int = Field(1200, ge=500, le=5000)
    plbert_safe: int = Field(480, ge=100, le=512)
    speaker_max: int = Field(30, ge=1, le=30)

def prepare_config_models() -> Dict[str, Any]:
    """
    Повертає всі моделі конфігурації для TTS модуля.
    Кожна модель відповідає за свою секцію в конфігураційному файлі.
    """
    return {
        'tts': TTSConfig,
        'sfx': SFXConfig,
        'gradio_ui': GradioUIConfig,
        'processing': ProcessingConfig,
        'dialog_parser': DialogParserConfig,  # 🆕
    }

# Дефолтні значення для швидкого старту
DEFAULT_CONFIG = {
    'tts': {
        'enabled': True,
        'default_speed': 0.88,
        'speaker_max': 30,
        'output_dir': 'output_audio',
        'autoplay': False,
        'autosave': True,
        'max_tokens': 280,
        'char_cap': 1200,
        'progress_poll_interval': 1.0,
        'sfx_enabled': True,
        'sfx_config_path': 'sfx.yaml',
        'sample_rate': 24000,
        'normalize_volume': True,
        'target_dbfs': -16
    },
    'sfx': {
        'normalize_dbfs': -16,
        'default_sr': 24000,
        'default_speed': 0.88,
        'sounds': {}
    },
    'gradio_ui': {
        'port': 7860,
        'server_name': '0.0.0.0',
        'share': False,
        'theme': 'default',
        'width': '100%',
        'height': 600,
        'show_error': True,
        'analytics_enabled': False
    },
    'processing': {
        'preserve_plus_symbols': True,
        'normalize_unicode': True,
        'split_by_sentences': True,
        'max_sentence_length': 200,
        'remove_control_chars': True
    },
    'dialog_parser': {  # 🆕
        'enabled': True,
        'max_tokens': 280,
        'char_cap': 1200,
        'plbert_safe': 480,
        'speaker_max': 30
    }
}

def check_dependencies() -> Dict[str, Any]:
    """
    Перевірка залежностей TTS модуля.
    АЛЕ: цей модуль конфігурації не вимагає цих залежностей для роботи.
    Він тільки визначає моделі Pydantic.
    """
    return {
        'all_available': True,
        'missing_packages': [],
        'installed_packages': [],
        'details': {
            'note': 'This is configuration module only. Dependencies are checked in p_312_tts_engine'
        }
    }
