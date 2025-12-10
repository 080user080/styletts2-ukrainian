# p_300_test_actions.py
from typing import Dict, Any
from pydantic import BaseModel

class TestConfig(BaseModel):
    enabled: bool = True
    message: str = "Тестове повідомлення"

def prepare_config_models():
    return {'test_actions': TestConfig}

def initialize(app_context: Dict[str, Any]):
    print("[TestActions] Ініціалізація тестового модуля")
    
    # Реєструємо тестову дію
    from kod.p_080_registry import register_action
    
    def test_action():
        print("✅ Тестова дія виконана!")
        return "Успіх!"
    
    register_action(
        app_context,
        action_id="test.say_hello",
        name="Сказати привіт",
        callback=test_action,
        description="Проста тестова дія для перевірки реєстру",
        module="p_300_test_actions",
        category="Тест"
    )
    
    return {"status": "ready"}