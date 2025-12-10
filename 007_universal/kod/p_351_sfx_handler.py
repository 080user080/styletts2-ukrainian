"""
p_351_tts_sfx_handler.py - Обробник звукових ефектів (SFX) для TTS системи.
Завантажує, обробляє, нормалізує та змішує SFX файли.
"""

import os
import math
import yaml
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import logging

import numpy as np
import soundfile as sf
from scipy import signal


class SFXHandler:
    """Обробник звукових ефектів для TTS."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("SFXHandler")
        self.sfx_config = self._load_sfx_config()
        self.project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).parent
        self.logger.info(f"✅ SFX Handler ініціалізовано з конфігом: {len(self.sfx_config.get('sounds', {}))} ефектів")
    
    def _load_sfx_config(self, path: str = "sfx.yaml") -> dict:
        """
        Завантажує SFX конфігурацію з YAML.
        Пошуковий порядок:
          1) ./sfx.yaml
          2) ./sound/sfx.yaml
          3) config/sfx.yaml
        """
        candidates = [
            os.path.join(os.getcwd(), "sfx.yaml"),
            os.path.join(os.getcwd(), "sound", "sfx.yaml"),
            os.path.join(os.getcwd(), "config", "sfx.yaml"),
        ]
        
        default_config = {
            "normalize_dbfs": -16,
            "default_sr": 24000,
            "default_speed": 0.88,
            "sounds": {}
        }
        
        for candidate in candidates:
            if os.path.exists(candidate):
                try:
                    with open(candidate, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if isinstance(data, dict):
                            default_config.update(data)
                            default_config["_cfg_dir"] = os.path.dirname(candidate)
                            self.logger.info(f"Завантажено SFX конфіг: {candidate}")
                            return default_config
                except Exception as e:
                    self.logger.warning(f"Помилка читання {candidate}: {e}")
        
        self.logger.warning("⚠️ SFX конфіг не знайдено, використовуються дефолти")
        return default_config
    
    def get_config(self) -> dict:
        """Повертає поточну SFX конфігурацію (переськуває змін)."""
        return self._load_sfx_config()
    
    def load_and_process_sfx(self, sfx_id: str, target_sr: int = 24000) -> Tuple[int, np.ndarray]:
        """
        Завантажує та обробляє SFX файл:
          ✓ Читання з файлу
          ✓ Ресемплінг до target_sr
          ✓ Нормалізація гучності
          ✓ Застосування gain_db
          ✓ Fade-in/fade-out
        
        Args:
            sfx_id: ID ефекту з sfx.yaml
            target_sr: Цільова частота дискретизації
        
        Returns:
            (sample_rate, audio_array)
        """
        cfg_all = self.get_config()
        cfg = cfg_all.get('sounds', {}).get(sfx_id)
        
        if not cfg:
            raise RuntimeError(f"SFX конфігурація відсутня для id '{sfx_id}'")
        
        src_file = cfg.get('file')
        if not src_file:
            raise RuntimeError(f"Файл для SFX '{sfx_id}' не вказаний у конфігурації")
        
        # === ПОШУК ФАЙЛУ ===
        possible_paths = [
            src_file,
            os.path.join(os.getcwd(), src_file),
            os.path.join(os.getcwd(), "sound", src_file),
        ]
        
        cfg_dir = cfg_all.get("_cfg_dir")
        if cfg_dir:
            possible_paths.extend([
                os.path.join(cfg_dir, src_file),
                os.path.join(cfg_dir, "sound", src_file),
            ])
        
        audio_path = None
        for p in possible_paths:
            if p and os.path.exists(p):
                audio_path = p
                break
        
        if not audio_path:
            raise RuntimeError(f"Файл SFX '{src_file}' для id '{sfx_id}' не знайдено. "
                             f"Перевірені шляхи: {possible_paths}")
        
        # === ЧИТАННЯ АУДІО ===
        try:
            data, sr = sf.read(audio_path)
        except Exception as e:
            raise RuntimeError(f"Помилка читання SFX файлу {audio_path}: {e}")
        
        # === ОБРОБКА АУДІО ===
        # Конвертація у float32, моно
        data = np.asarray(data, dtype=np.float32)
        if data.ndim > 1:
            data = data.mean(axis=1)
        
        # Ресемплінг
        if sr != target_sr:
            duration = data.shape[0] / sr
            target_len = int(round(duration * target_sr))
            if target_len <= 0:
                target_len = 1
            data = signal.resample(data, target_len)
            sr = target_sr
        
        # === НОРМАЛІЗАЦІЯ ГУЧНОСТІ ===
        normalize_dbfs = cfg_all.get('normalize_dbfs', -16)
        # Якщо у конфігу SFX явно вказано normalize: false - відключаємо
        if cfg.get('normalize') is False:
            normalize_dbfs = None
        
        # Обчислення RMS та dBFS
        rms = math.sqrt(np.mean(data ** 2)) if data.size else 0.0
        if rms > 0:
            current_dbfs = 20 * math.log10(rms)
        else:
            current_dbfs = -float('inf')
        
        # Застосування gain_db та нормалізація
        total_gain_db = float(cfg.get('gain_db', 0.0))
        if normalize_dbfs is not None and current_dbfs > -float('inf'):
            total_gain_db += (float(normalize_dbfs) - current_dbfs)
        
        gain_factor = 10.0 ** (total_gain_db / 20.0)
        data = data * gain_factor
        
        # === FADE IN/OUT ===
        fade_ms = 30
        fade_len = int(sr * fade_ms / 1000.0)
        fade_len = max(fade_len, 1)
        
        if data.size >= fade_len:
            ramp_in = np.linspace(0.0, 1.0, fade_len, dtype=data.dtype)
            data[:fade_len] *= ramp_in
            ramp_out = np.linspace(1.0, 0.0, fade_len, dtype=data.dtype)
            data[-fade_len:] *= ramp_out
        
        self.logger.debug(f"✅ SFX '{sfx_id}' обрано: {audio_path} → {sr} Hz")
        return sr, data
    
    def get_available_sfx_ids(self) -> list:
        """Повертає список доступних ID ефектів."""
        cfg = self.get_config()
        return list(cfg.get('sounds', {}).keys())
    
    def validate_sfx_id(self, sfx_id: str) -> bool:
        """Перевіряє, чи існує SFX з таким ID."""
        cfg = self.get_config()
        return sfx_id in cfg.get('sounds', {})
    
    def get_sfx_info(self, sfx_id: str) -> Optional[Dict[str, Any]]:
        """Повертає інформацію про SFX."""
        cfg = self.get_config()
        return cfg.get('sounds', {}).get(sfx_id)


def prepare_config_models():
    """Повертає моделі конфігурації."""
    return {}


def initialize(app_context: Dict[str, Any]) -> SFXHandler:
    """Ініціалізація SFX Handler."""
    logger = app_context.get('logger', logging.getLogger("SFXHandler"))
    logger.info("🔊 Ініціалізація обробника SFX...")
    
    handler = SFXHandler(app_context)
    app_context['sfx_handler'] = handler
    
    logger.info(f"✅ SFX Handler готовий. Доступно ефектів: {len(handler.get_available_sfx_ids())}")
    return handler


def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка обробника SFX."""
    if 'sfx_handler' in app_context:
        del app_context['sfx_handler']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("SFX Handler зупинено")
