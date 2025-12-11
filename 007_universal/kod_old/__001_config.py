# p_001_config.py (оновлена версія)
"""
Валідація конфігурації з відстеженням джерел.
"""

from pydantic import BaseModel, Field, create_model
from typing import Dict, Any, Literal

class AppConfig(BaseModel):
    """Конфігурація додатку."""
    name: str = "My Modular Project"
    version: str = "0.1.0"
    mode: Literal["DEBUG", "PRODUCTION"] = "DEBUG"
    config_mode: Literal["auto", "manual"] = "auto"

def initialize(app_context: Dict[str, Any]) -> BaseModel:
    """
    Динамічно створює модель Config з відстеженням джерел.
    """
    print("  [Config] Валідація конфігурації...")
    
    raw_config = app_context.get('raw_config', {})
    config_sources = app_context.get('config_sources', {})
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
        
        # Додаємо метадані про джерела в об'єкт конфігурації
        validated_config._config_sources = config_sources
        validated_config._raw_config = raw_config
        
        # Додаємо метод для отримання джерела конфігурації
        def get_config_source(path: str) -> str:
            """Отримати джерело конфігурації для шляху."""
            return config_sources.get(path, "unknown")
        
        validated_config.get_config_source = get_config_source
        
        # Інформація про секції
        sections = list(validated_config.dict().keys())
        print(f"  [Config] ✅ Успішно. Секції: {sections}")
        print(f"  [Config] 📊 Джерела: {len(config_sources)} конфігураційних шляхів")
        
        return validated_config

    except Exception as e:
        print(f"  [Config] ❌ КРИТИЧНА ПОМИЛКА КОНФІГУРАЦІЇ: {e}")
        # Детальна інформація про помилку
        import traceback
        traceback.print_exc()
        raise