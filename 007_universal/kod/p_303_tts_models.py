"""
p_303_tts_models.py - Завантаження та керування моделями TTS
(Виділено з app.py)
"""

import os
import glob
import torch
from typing import Dict, Any, Optional
import logging
from pathlib import Path

# Конфігурація
from pydantic import BaseModel

class TTSModelsConfig(BaseModel):
    enabled: bool = True
    device: str = "auto"
    prompts_dir: str = "voices"
    single_model_path: str = "patriotyk/styletts2_ukrainian_single"
    multi_model_path: str = "patriotyk/styletts2_ukrainian_multispeaker"
    single_style_path: str = "filatov.pt"

def prepare_config_models():
    return {'tts_models': TTSModelsConfig}

DEFAULT_CONFIG = {
    'tts_models': {
        'enabled': True,
        'device': 'auto',
        'prompts_dir': 'voices',
        'single_model_path': 'patriotyk/styletts2_ukrainian_single',
        'multi_model_path': 'patriotyk/styletts2_ukrainian_multispeaker',
        'single_style_path': 'filatov.pt'
    }
}

class TTSModels:
    """Клас для керування моделями TTS."""
    
    def __init__(self, config: TTSModelsConfig):
        self.config = config
        self.logger = logging.getLogger("TTSModels")
        
        # Визначити пристрій
        self.device = config.device
        if self.device == "auto":
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Моделі
        self.single_model = None
        self.multi_model = None
        self.single_style = None
        self.multi_styles = {}
        self.prompts_list = []
        
        # Завантажені прапори
        self.models_loaded = False
    
    def load_models(self) -> bool:
        """Завантажити всі моделі."""
        try:
            self.logger.info("Завантаження TTS моделей...")
            
            # Імпорт тут, щоб уникнути помилок при відсутності залежностей
            from styletts2_inference.models import StyleTTS2
            
            # 1. Завантажити single модель
            self.logger.info(f"Завантаження single моделі: {self.config.single_model_path}")
            self.single_model = StyleTTS2(
                hf_path=self.config.single_model_path, 
                device=self.device
            )
            
            # 2. Завантажити single стиль
            if os.path.exists(self.config.single_style_path):
                self.single_style = torch.load(self.config.single_style_path)
                self.logger.info(f"Завантажено single стиль: {self.config.single_style_path}")
            
            # 3. Завантажити multi модель
            self.logger.info(f"Завантаження multi моделі: {self.config.multi_model_path}")
            self.multi_model = StyleTTS2(
                hf_path=self.config.multi_model_path,
                device=self.device
            )
            
            # 4. Завантажити multi стилі
            prompts_dir = Path(self.config.prompts_dir)
            if prompts_dir.exists():
                prompt_files = sorted(glob.glob(str(prompts_dir / "*.pt")))
                self.prompts_list = [
                    os.path.splitext(os.path.basename(p))[0] 
                    for p in prompt_files
                ]
                
                for audio_prompt in self.prompts_list:
                    audio_path = prompts_dir / f"{audio_prompt}.pt"
                    if audio_path.exists():
                        self.multi_styles[audio_prompt] = torch.load(audio_path)
                        self.logger.debug(f"Завантажено стиль: {audio_prompt}")
            
            self.logger.info(f"Завантажено моделей: single=1, multi=1, стилів: {len(self.multi_styles)}")
            self.models_loaded = True
            return True
            
        except ImportError as e:
            self.logger.error(f"Не вдалося імпортувати styletts2_inference: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Помилка завантаження моделей: {e}")
            return False
    
    def get_single_model(self):
        """Отримати single модель."""
        if not self.models_loaded:
            self.load_models()
        return self.single_model, self.single_style
    
    def get_multi_model(self, voice_name: Optional[str] = None):
        """Отримати multi модель та стиль."""
        if not self.models_loaded:
            self.load_models()
        
        if voice_name and voice_name in self.multi_styles:
            return self.multi_model, self.multi_styles[voice_name]
        elif self.prompts_list:
            return self.multi_model, self.multi_styles.get(self.prompts_list[0], None)
        else:
            return self.multi_model, None
    
    def get_available_voices(self) -> list:
        """Отримати список доступних голосів."""
        if not self.models_loaded:
            self.load_models()
        return self.prompts_list.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Отримати статус моделей."""
        return {
            'device': self.device,
            'models_loaded': self.models_loaded,
            'single_model_loaded': self.single_model is not None,
            'multi_model_loaded': self.multi_model is not None,
            'single_style_loaded': self.single_style is not None,
            'multi_styles_count': len(self.multi_styles),
            'available_voices': len(self.prompts_list),
            'prompts_dir': self.config.prompts_dir
        }

def check_dependencies() -> bool:
    """Перевірити залежності."""
    try:
        import styletts2_inference
        import torch
        return True
    except ImportError:
        return False

def initialize(app_context: Dict[str, Any]) -> Optional[TTSModels]:
    """Ініціалізація моделей TTS."""
    logger = app_context.get('logger', logging.getLogger("TTSModels"))
    
    # Отримати конфігурацію
    config = app_context.get('config')
    if not config or not hasattr(config, 'tts_models'):
        logger.warning("Конфігурація tts_models не знайдена")
        return None
    
    tts_config = config.tts_models
    if not tts_config.enabled:
        logger.info("TTS моделі вимкнені в конфігурації")
        return None
    
    # Перевірка залежностей
    if not check_dependencies():
        logger.error("Потрібні бібліотеки: styletts2_inference, torch")
        return None
    
    try:
        # Створити менеджер моделей
        models_manager = TTSModels(tts_config)
        
        # Спроба завантажити моделі
        if models_manager.load_models():
            app_context['tts_models'] = models_manager
            
            # Додати доступні голоси в контекст
            app_context['available_voices'] = models_manager.get_available_voices()
            
            logger.info("✅ TTS моделі успішно завантажені")
            return models_manager
        else:
            logger.error("Не вдалося завантажити TTS моделі")
            return None
            
    except Exception as e:
        logger.error(f"Помилка ініціалізації TTS моделей: {e}")
        return None

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка моделей TTS."""
    if 'tts_models' in app_context:
        del app_context['tts_models']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("TTS моделі зупинені")