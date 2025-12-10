"""
p_302_verbalizer.py - Вербалізація тексту (цифри в слова)
"""
"""
p_304_tts_verbalizer_wrapper.py - Обгортка для вербалізації тексту
"""

from typing import Dict, Any, Optional  # ДОДАТИ ЦЕЙ РЯДОК
from typing import Dict, Any, List  # Додайте цей імпорт!
import torch
import logging


# Конфігурація
from pydantic import BaseModel

class VerbalizerConfig(BaseModel):
    enabled: bool = True
    device: str = "auto"  # auto, cuda, cpu
    model_name: str = "skypro1111/mbart-large-50-verbalization"

def prepare_config_models():
    return {'verbalizer': VerbalizerConfig}

DEFAULT_CONFIG = {
    'verbalizer': {
        'enabled': True,
        'device': 'auto',
        'model_name': 'skypro1111/mbart-large-50-verbalization'
    }
}

def check_dependencies():
    """Перевірка залежностей."""
    try:
        import transformers
        return True
    except ImportError:
        return False

# Клас Verbalizer з оригінального файлу
class Verbalizer:
    def __init__(self, device, model_name):
        from transformers import MBartForConditionalGeneration, AutoTokenizer
        
        self.device = device
        self.model = MBartForConditionalGeneration.from_pretrained(
            model_name,
            low_cpu_mem_usage=True,
            device_map=device,
        )
        self.model.eval()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.tokenizer.src_lang = "uk_XX"
        self.tokenizer.tgt_lang = "uk_XX"

    def generate_text(self, text: str) -> str:
        """Generate text for a single input."""
        input_text = "<verbalization>:" + text
        encoded_input = self.tokenizer(
            input_text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=1024,
        ).to(self.device)
        output_ids = self.model.generate(
            **encoded_input, max_length=1024, num_beams=5, early_stopping=True
        )
        normalized_text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        return normalized_text.strip()

def initialize(app_context: Dict[str, Any]) -> Optional[Verbalizer]:
    """Ініціалізація вербалізатора."""
    logger = app_context.get('logger', logging.getLogger("Verbalizer"))
    
    # Отримати конфігурацію
    config = app_context.get('config')
    if not config or not hasattr(config, 'verbalizer'):
        logger.warning("Конфігурація verbalizer не знайдена")
        return None
    
    verbalizer_config = config.verbalizer
    if not verbalizer_config.enabled:
        logger.info("Verbalizer вимкнено в конфігурації")
        return None
    
    # Перевірка залежностей
    if not check_dependencies():
        logger.error("Потрібні бібліотеки: transformers, torch")
        return None
    
    # Визначити пристрій
    device = verbalizer_config.device
    if device == "auto":
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    logger.info(f"Ініціалізація Verbalizer на пристрої: {device}")
    
    try:
        # Створити вербалізатор
        verbalizer = Verbalizer(device, verbalizer_config.model_name)
        
        # Додати в контекст
        app_context['verbalizer'] = verbalizer
        
        logger.info("✅ Verbalizer успішно ініціалізовано")
        return verbalizer
        
    except Exception as e:
        logger.error(f"Помилка ініціалізації Verbalizer: {e}")
        return None

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка вербалізатора."""
    if 'verbalizer' in app_context:
        del app_context['verbalizer']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("Verbalizer зупинено")