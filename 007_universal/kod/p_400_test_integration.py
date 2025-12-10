# p_400_test_integration.py
"""
Тестовий модуль для перевірки інтеграції TTS у фреймворк.
"""

from typing import Dict, Any
from pydantic import BaseModel

class TestConfig(BaseModel):
    enabled: bool = True
    test_message: str = "Тест інтеграції"

def prepare_config_models():
    return {'test_integration': TestConfig}

def initialize(app_context: Dict[str, Any]):
    """Простий тест, що все працює."""
    print("[Test] Перевірка інтеграції TTS...")
    
    # Перевіряємо наявність компонентів
    components = [
        'config',
        'logger',
        'event_bus',
        'action_registry',
        'gui_manager'
    ]
    
    for comp in components:
        if comp in app_context:
            print(f"[Test] ✅ {comp} присутній")
        else:
            print(f"[Test] ❌ {comp} відсутній")
    
    # Тестуємо реєстрацію дії
    from kod.p_080_registry import register_action
    
    def test_function():
        return "Тестова дія виконана!"
    
    register_action(
        app_context,
        action_id="test.demo_action",
        name="Тестова дія",
        callback=test_function,
        description="Демонстраційна дія для тестування",
        module="p_400_test_integration",
        category="Тест"
    )
    
    print("[Test] Інтеграція перевірена!")
    return {"status": "tested"}