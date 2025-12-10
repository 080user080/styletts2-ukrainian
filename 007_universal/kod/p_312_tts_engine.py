# p_312_tts_engine.py
"""
TTS двигун - ядро синтезу мови.
Адаптована версія ключових функцій з оригінального коду.
"""

import os
import time
import re
import unicodedata
import traceback
from typing import Dict, List, Tuple, Optional, Any, Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
from pathlib import Path  # ДОДАТИ ЦЕЙ РЯДОК
import numpy as np
import yaml
from scipy import signal
import math

# Типові імпорти для TTS
try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False
    print("WARNING: soundfile не встановлено, збереження аудіо недоступне")

# Імпорт для токенізації (опційно)
try:
    from transformers import AutoTokenizer
    TOKENIZER_AVAILABLE = True
except ImportError:
    AutoTokenizer = None
    TOKENIZER_AVAILABLE = False

@dataclass
class TTSPart:
    """Представляє частину тексту для синтезу."""
    text: str
    speaker_id: int
    speed: float
    index: int
    metadata: Dict[str, Any] = None

@dataclass
class SynthesisResult:
    """Результат синтезу."""
    audio: np.ndarray
    sample_rate: int
    duration: float
    part: TTSPart
    output_path: Optional[str] = None

class TTSEngine:
    """
    Основний двигун TTS синтезу.
    Інтегрує логіку з оригінального коду в модульну систему.
    """
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("TTSEngine")
        
        # Конфігурація
        self.config = self._get_config()
        self.sfx_config = self._load_sfx_config()
        
        # Кеш токенізатора
        self._tokenizer = None
        self._init_tokenizer()
        
        # Стан двигуна
        self.is_initialized = False
        self.current_session_id = None
        self.output_dir = None
        self.speaker_configs = {}
        
        # ====== ДОДАНО: Список доступних голосів ======
        self.available_voices = []
        
        self.logger.info("TTSEngine створено")
    
    def _get_config(self) -> Dict[str, Any]:
        """Отримати конфігурацію TTS з app_context."""
        config = self.app_context.get('config', {})
        
        # Якщо конфіг вже валідований Pydantic
        if hasattr(config, 'tts'):
            return {
                'tts': config.tts.dict(),
                'sfx': config.sfx.dict() if hasattr(config, 'sfx') else {},
                'processing': config.processing.dict() if hasattr(config, 'processing') else {}
            }
        
        # Fallback до дефолтних значень
        from .p_310_tts_config import DEFAULT_CONFIG
        return DEFAULT_CONFIG
    
    def _load_sfx_config(self) -> Dict[str, Any]:
        """
        Завантажити конфігурацію SFX.
        ====== ЗМІНЕНО: Пріоритет sound/sfx.yaml ======
        """
        default_config = {"normalize_dbfs": -16, "sounds": {}, "default_speed": 0.88}
        
        candidates = [
            # ПРІОРИТЕТ 1: sound/sfx.yaml у поточній директорії
            os.path.join(os.getcwd(), "sound", "sfx.yaml"),
            # ПРІОРИТЕТ 2: sfx.yaml у поточній директорії
            os.path.join(os.getcwd(), "sfx.yaml"),
            # ПРІОРИТЕТ 3: sound/sfx.yaml відносно модуля
            os.path.join(os.path.dirname(__file__), "..", "sound", "sfx.yaml"),
            # ПРІОРИТЕТ 4: з конфігу (якщо вказано)
            self.config.get('tts', {}).get('sfx_config_path', ''),
        ]
        
        # Видалити порожні шляхи
        candidates = [c for c in candidates if c]
        
        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if isinstance(data, dict):
                            data['_cfg_dir'] = os.path.dirname(path)
                            self.logger.info(f"✅ SFX конфіг завантажено: {path}")
                            return data
                except Exception as e:
                    self.logger.warning(f"Не вдалося завантажити {path}: {e}")
        
        self.logger.warning("⚠️ SFX конфіг не знайдено, використовуються дефолтні значення")
        return default_config
    
    def _init_tokenizer(self):
        """Ініціалізація токенізатора (якщо доступно)."""
        if not TOKENIZER_AVAILABLE:
            self._tokenizer = None
            return
        
        try:
            self._tokenizer = AutoTokenizer.from_pretrained("albert-base-v2")
            self.logger.debug("Токенізатор ініціалізовано")
        except Exception as e:
            self.logger.warning(f"Не вдалося завантажити токенізатор: {e}")
            self._tokenizer = None
    
    def _token_length(self, text: str) -> int:
        """Оцінити довжину в токенах."""
        if self._tokenizer:
            return len(self._tokenizer.encode(text, add_special_tokens=True))
        
        # Консервативний fallback
        return len(text) + 32
    
    def initialize(self) -> bool:
        """Ініціалізація двигуна."""
        try:
            # Перевірка залежностей
            deps = self.app_context.get('tts_dependencies', {})
            if not deps.get('soundfile_available', SOUNDFILE_AVAILABLE):
                self.logger.error("soundfile не доступний")
                return False
            
            # Створення вихідної директорії
            output_dir = self.config['tts'].get('output_dir', 'output_audio')
            os.makedirs(output_dir, exist_ok=True)
            self.output_dir = output_dir
            
            # Генерація ID сесії
            self.current_session_id = f"tts_{int(time.time())}"
            
            # ====== ДОДАНО: Завантаження списку голосів ======
            self.available_voices = self._discover_voices()
            
            self.is_initialized = True
            self.logger.info(f"TTSEngine ініціалізовано, сесія: {self.current_session_id}")
            self.logger.info(f"Доступно голосів: {len(self.available_voices)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Помилка ініціалізації TTSEngine: {e}")
            return False
    
    # ====== ДОДАНО: Нові методи для Gradio UI ======
    
    def _discover_voices(self) -> List[str]:
        """
        Автоматичне виявлення доступних голосів.
        ВИПРАВЛЕНО: Без імпорту app.py
        """
        # Спроба отримати з app_context
        voices = self.app_context.get('available_voices', [])
        if voices:
            self.logger.info(f"Використано голоси з app_context: {len(voices)}")
            return voices
        
        # Спроба отримати з tts_models (якщо модуль завантажений)
        tts_models = self.app_context.get('tts_models')
        if tts_models and hasattr(tts_models, 'get_available_voices'):
            try:
                model_voices = tts_models.get_available_voices()
                if model_voices:
                    self.logger.info(f"✅ Отримано голоси з TTS моделей: {len(model_voices)}")
                    return model_voices
            except Exception as e:
                self.logger.debug(f"Не вдалося отримати голоси з TTS моделей: {e}")
        
        # Fallback: спроба прочитати з папки voices
        voices_dir = Path("voices")
        if voices_dir.exists():
            try:
                pt_files = list(voices_dir.glob("*.pt"))
                pt_files.extend(voices_dir.glob("*.wav"))
                pt_files.extend(voices_dir.glob("*.mp3"))
                
                if pt_files:
                    voices = [f.stem for f in pt_files]
                    self.logger.info(f"✅ Знайдено голосів у папці voices: {len(voices)}")
                    return voices
            except Exception as e:
                self.logger.debug(f"Не вдалося прочитати папку voices: {e}")
        
        # Fallback: базові голоси для тестування
        fallback_voices = [
            "default",
            "Філатов Дмитро",
            "Narrator Male",
            "Narrator Female",
        ]
        self.logger.warning(f"⚠️ Використовуються тестові голоси: {fallback_voices}")
        return fallback_voices
    
    def get_available_voices(self) -> List[str]:
        """
        Повертає список доступних голосів для UI.
        
        Returns:
            List[str]: Список назв голосів
        """
        if not self.available_voices:
            self.available_voices = self._discover_voices()
        return self.available_voices.copy()
    
    # --- Основні функції з оригінального коду (адаптовані) ---
    
    def normalize_text(self, text: str) -> str:
        """Нормалізація тексту (збереження '+')."""
        if not isinstance(text, str):
            return str(text) if text else ""
        
        # NFKC нормалізація
        text = unicodedata.normalize("NFKC", text).replace("\ufeff", "")
        
        # Уніфікація апострофів і тире
        text = (text.replace("'", "'").replace("'", "'").replace("ʼ", "'")
                   .replace("—", "-").replace("–", "-").replace("−", "-"))
        
        # Видалення невидимих символів (збереження \n, \r, \t, +)
        result = []
        for char in text:
            if char == '+':
                result.append(char)
                continue
            
            category = unicodedata.category(char)
            if category in ("Cf", "Cc") and char not in ("\n", "\r", "\t"):
                continue
            
            result.append(char)
        
        text = "".join(result)
        
        # Заміна NBSP на звичайний пробіл
        text = text.replace("\u00A0", " ")
        
        # Очищення пробілів навколо переносів
        text = re.sub(r"\s*\n\s*", "\n", text)
        
        return text.strip()
    
    def split_to_parts(self, text: str, max_tokens: Optional[int] = None) -> List[str]:
        """
        Розбиття тексту на частини з урахуванням обмежень токенів.
        Адаптована версія з оригінального коду.
        """
        if max_tokens is None:
            max_tokens = self.config['tts'].get('max_tokens', 280)
        
        char_cap = self.config['tts'].get('char_cap', 1200)
        text = self.normalize_text(text)
        
        # Проста реалізація для початку
        parts = []
        current_part = ""
        current_token_count = 0
        
        # Розбиття на речення
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            
            sentence_tokens = self._token_length(sentence)
            
            # Якщо речення дуже довге, розбиваємо його
            if sentence_tokens > max_tokens or len(sentence) > char_cap:
                # Додаємо те, що накопичили
                if current_part:
                    parts.append(current_part.strip())
                    current_part = ""
                    current_token_count = 0
                
                # Розбиваємо довге речення
                words = sentence.split()
                chunk = []
                chunk_tokens = 0
                
                for word in words:
                    word_tokens = self._token_length(word)
                    
                    if chunk_tokens + word_tokens > max_tokens:
                        if chunk:
                            parts.append(" ".join(chunk).strip())
                        chunk = [word]
                        chunk_tokens = word_tokens
                    else:
                        chunk.append(word)
                        chunk_tokens += word_tokens
                
                if chunk:
                    parts.append(" ".join(chunk).strip())
            
            # Якщо речення поміщається
            elif current_token_count + sentence_tokens <= max_tokens:
                if current_part:
                    current_part += " " + sentence
                else:
                    current_part = sentence
                current_token_count += sentence_tokens
            
            # Якщо не поміщається
            else:
                if current_part:
                    parts.append(current_part.strip())
                current_part = sentence
                current_token_count = sentence_tokens
        
        # Додаємо останню частину
        if current_part:
            parts.append(current_part.strip())
        
        return parts
    
    def parse_dialog_tags(self, text: str) -> List[Tuple[int, str]]:
        """Парсинг тегів діалогу (#gN)."""
        text = self.normalize_text(text)
        lines = text.splitlines()
        current_tag = None
        parsed = []
        
        tag_re = re.compile(r'^#g([1-9]|[12][0-9]|30)\s*:\s*(.*)$', re.I)
        
        for line in lines:
            line = line.rstrip()
            if not line:
                continue
            
            match = tag_re.match(line)
            if match:
                current_tag = int(match.group(1))
                tail = match.group(2).strip()
                if tail:
                    for part in self.split_to_parts(tail):
                        parsed.append((current_tag, part))
                continue
            
            speaker_id = current_tag if current_tag is not None else 1
            for part in self.split_to_parts(line):
                parsed.append((speaker_id, part))
        
        return parsed
    
    # --- Основні методи API ---
    
    def synthesize(self, text: str, speaker_id: int = 1, speed: float = None, voice: str = None) -> Dict[str, Any]:
        """
        Основний метод синтезу.
        ====== ЗМІНЕНО: Повертає dict замість SynthesisResult ======
        
        Args:
            text: Текст для синтезу
            speaker_id: ID спікера (1-30)
            speed: Швидкість синтезу (0.7-1.3)
            voice: Назва голосу (опційно, якщо None - використовується speaker_id)
        
        Returns:
            Dict з ключами: 'audio', 'sample_rate', 'duration'
        """
        if not self.is_initialized and not self.initialize():
            raise RuntimeError("TTSEngine не ініціалізовано")
        
        if speed is None:
            speed = self.config['tts'].get('default_speed', 0.88)
        
        # ====== ДОДАНО: Підтримка voice параметра ======
        if voice:
            self.logger.info(f"Використовується голос: {voice}")
            # ТУТ має бути логіка вибору голосу
            # Наприклад, маппінг voice -> speaker_id або параметри для TTS
            # speaker_id = self._voice_to_speaker_id(voice)
        
        # Нормалізація тексту
        text = self.normalize_text(text)
        
        # Логування
        self.logger.info(f"Синтез: {len(text)} символів, спікер: {speaker_id}, швидкість: {speed}")
        
        # ====== ВАЖЛИВО: ЗАМІНІТЬ НА СПРАВЖНІЙ TTS ======
        # Тут має бути виклик до справжнього синтезатора:
        # audio, sample_rate = your_real_tts_function(text, voice, speed)
        # ==============================================
        
        sample_rate = self.config['tts'].get('sample_rate', 24000)
        
        # Генерація тестового аудіо (синусоїда) - ТІЛЬКИ ДЛЯ ТЕСТУВАННЯ
        duration = max(1.0, len(text) / 20)  # Приблизна тривалість
        t = np.linspace(0, duration, int(sample_rate * duration))
        frequency = 440  # Нота Ля
        audio = 0.5 * np.sin(2 * np.pi * frequency * t)
        
        # Додаємо затухання
        fade_samples = int(0.1 * sample_rate)
        if len(audio) > fade_samples:
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            audio[:fade_samples] *= fade_in
            audio[-fade_samples:] *= fade_out
        
        # Збереження (якщо налаштовано)
        output_path = None
        if self.config['tts'].get('autosave', True):
            output_path = self._save_audio(audio, sample_rate, speaker_id)
        
        # ====== ЗМІНЕНО: Повертаємо dict замість SynthesisResult ======
        result = {
            'audio': audio,
            'sample_rate': sample_rate,
            'duration': duration,
            'speaker_id': speaker_id,
            'speed': speed,
            'voice': voice,
            'output_path': output_path
        }
        
        return result
    
    def synthesize_batch(self, parts: List[TTSPart]) -> Generator[Dict[str, Any], None, None]:
        """Пакетний синтез кількох частин."""
        total = len(parts)
        
        for i, part in enumerate(parts, 1):
            self.logger.info(f"Обробка частини {i}/{total}")
            
            yield self.synthesize(
                text=part.text,
                speaker_id=part.speaker_id,
                speed=part.speed
            )
    
    def _save_audio(self, audio: np.ndarray, sample_rate: int, speaker_id: int = 1) -> Optional[str]:
        """
        ====== ДОДАНО: Спрощений метод збереження ======
        Зберегти аудіо масив у файл.
        
        Args:
            audio: Numpy масив з аудіо
            sample_rate: Частота дискретизації
            speaker_id: ID спікера
        
        Returns:
            str: Шлях до збереженого файлу або None
        """
        if not SOUNDFILE_AVAILABLE:
            self.logger.warning("soundfile не доступний, збереження пропущено")
            return None
        
        if not self.output_dir:
            self.output_dir = self.config['tts'].get('output_dir', 'output_audio')
            os.makedirs(self.output_dir, exist_ok=True)
        
        # Генерація імені файлу
        timestamp = int(time.time())
        filename = f"tts_{timestamp}_{speaker_id}.wav"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            sf.write(filepath, audio, sample_rate)
            self.logger.info(f"Аудіо збережено: {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"Помилка збереження аудіо: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """Отримати статус двигуна."""
        return {
            'initialized': self.is_initialized,
            'session_id': self.current_session_id,
            'output_dir': self.output_dir,
            'available_voices': len(self.available_voices),
            'config': {
                'speaker_max': self.config['tts'].get('speaker_max', 30),
                'default_speed': self.config['tts'].get('default_speed', 0.88),
                'sample_rate': self.config['tts'].get('sample_rate', 24000)
            },
            'dependencies': {
                'soundfile': SOUNDFILE_AVAILABLE,
                'tokenizer': TOKENIZER_AVAILABLE
            }
        }
    
    def cleanup(self):
        """Очищення ресурсів."""
        self.logger.info("Очищення ресурсів TTSEngine")
        self.is_initialized = False
        self.current_session_id = None

# Функції для ініціалізації модуля
def prepare_config_models():
    """Підготовка моделей конфігурації для TTS двигуна."""
    # Ця функція вже визначена в p_310_tts_config.py
    # Повертаємо порожній словник, щоб уникнути конфліктів
    return {}

def initialize(app_context: Dict[str, Any]) -> TTSEngine:
    """Ініціалізація TTS двигуна в контексті додатку."""
    logger = app_context.get('logger')
    if logger:
        logger.info("Ініціалізація TTSEngine...")
    
    # Створення двигуна
    engine = TTSEngine(app_context)
    
    # Спроба ініціалізації
    if engine.initialize():
        app_context['tts_engine'] = engine
        
        # ====== ВИПРАВЛЕНО: Правильна реєстрація дій ======
        action_registry = app_context.get('action_registry')
        if action_registry:
            try:
                # Використовуємо правильний API з p_080_registry
                # Формат: register_action(action_id, name, callback, description)
                
                action_registry.register_action(
                    "tts.synthesize",
                    "🎤 Синтезувати текст",
                    lambda text, speaker=1: engine.synthesize(text, speaker),
                    "Швидкий синтез тексту в мову"
                )
                
                action_registry.register_action(
                    "tts.get_status",
                    "📊 Статус TTS",
                    engine.get_status,
                    "Отримати статус TTS двигуна"
                )
                
                action_registry.register_action(
                    "tts.get_voices",
                    "🎙️ Список голосів",
                    engine.get_available_voices,
                    "Отримати список доступних голосів"
                )
                
                if logger:
                    logger.info("✅ TTS дії успішно зареєстровано")
            except Exception as e:
                if logger:
                    logger.warning(f"Не вдалося зареєструвати TTS дії: {e}")
        
        if logger:
            logger.info("TTSEngine успішно ініціалізовано")
        
        return engine
    else:
        if logger:
            logger.error("Не вдалося ініціалізувати TTSEngine")
        return None

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка TTS двигуна."""
    if 'tts_engine' in app_context:
        app_context['tts_engine'].cleanup()
        del app_context['tts_engine']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("TTSEngine зупинено")
