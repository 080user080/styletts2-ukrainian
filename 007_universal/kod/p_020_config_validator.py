# p_002_config_validator.py
"""
Валідація конфігурації через Pydantic.
"""

from pydantic import BaseModel, Field, create_model
from typing import Dict, Any, Literal

class AppConfig(BaseModel):
    """Конфігурація додатку."""
    name: str = "My Modular Project"
    version: str = "0.1.0"
    mode: Literal["DEBUG", "PRODUCTION"] = "DEBUG"

def initialize(app_context: Dict[str, Any]) -> BaseModel:
    """
    Валідує raw_config через Pydantic моделі.
    """
    print("  [Config] Валідація конфігурації...")
    
    raw_config = app_context.get('raw_config', {})
    models_map = app_context.get('config_models', {})

    # Створюємо словник полів для головної моделі
    fields = {
        'app': (AppConfig, Field(default_factory=AppConfig))
    }
    
    # Додаємо моделі, отримані від інших модулів
    for section_name, model_cls in models_map.items():
        fields[section_name] = (model_cls, Field(default_factory=model_cls))

    # Створюємо супер-модель
    DynamicConfig = create_model('Config', **fields)

    try:
        # Валідуємо словник через Pydantic
        validated_config = DynamicConfig.parse_obj(raw_config)
        
        # ДОДАЄМО КОНФІГУРАЦІЮ В КОНТЕКСТ ДОДАТКУ
        app_context['config'] = validated_config
        
        print(f"  [Config] ✅ Успішно. Секції: {list(validated_config.dict().keys())}")
        return validated_config

    except Exception as e:
        print(f"  [Config] ❌ КРИТИЧНА ПОМИЛКА КОНФІГУРАЦІЇ: {e}")
        import traceback
        traceback.print_exc()
        raise