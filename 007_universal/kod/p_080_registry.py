# p_020_registry.py (ВИПРАВЛЕНА ВЕРСІЯ)
"""
Реєстр дій для модулів.
Модулі реєструють свої функції, які потім відображаються в GUI.
"""

from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
from pydantic import BaseModel

@dataclass
class Action:
    """Опис дії, яку може виконати модуль."""
    id: str
    name: str
    description: str
    callback: Callable
    module: str
    category: str = "General"
    icon: Optional[str] = None
    requires_confirmation: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

# Локальні константи для подій (щоб уникнути імпорту з p_015_events)
class EventType(Enum):
    ACTION_REGISTERED = "action_registered"
    MODULE_LOADED = "module_loaded"

class ActionRegistry:
    """Центральний реєстр дій для GUI."""
    
    def __init__(self, event_bus=None):
        self.actions: Dict[str, Action] = {}
        self.categories: Dict[str, List[str]] = {}
        self.event_bus = event_bus
        self._logger = logging.getLogger("ActionRegistry")
    
    # ДОДАЙТЕ ЦЕЙ МЕТОД:
    def register_action(self, action_id: str, name: str, callback, 
                       description: str = "", module: str = "unknown", 
                       category: str = "General", icon: str = None, **kwargs) -> bool:
        """
        Альтернативний метод для сумісності з існуючим кодом.
        """
        action = Action(
            id=action_id,
            name=name,
            description=description,
            callback=callback,
            module=module,
            category=category,
            icon=icon,
            **kwargs
        )
        self.register(action)
        return True

    def register(self, action: Action) -> None:
        """Зареєструвати нову дію."""
        if action.id in self.actions:
            self._logger.warning(f"Дія з ID '{action.id}' вже зареєстрована. Перезапис.")
        
        self.actions[action.id] = action
        
        # Додаємо в категорію
        if action.category not in self.categories:
            self.categories[action.category] = []
        
        if action.id not in self.categories[action.category]:
            self.categories[action.category].append(action.id)
        
        self._logger.info(f"Зареєстровано дію: {action.name} ({action.id})")
        
        # Публікуємо подію про реєстрацію дії
        if self.event_bus:
            # Створюємо просту подію без імпорту з p_015_events
            import time
            event_data = {
                'type': EventType.ACTION_REGISTERED,
                'source': 'ActionRegistry',
                'data': {
                    'action_id': action.id,
                    'action_name': action.name,
                    'module': action.module,
                    'category': action.category
                },
                'timestamp': time.time()
            }
            try:
                self.event_bus.publish(event_data)
            except Exception as e:
                self._logger.debug(f"Не вдалося опублікувати подію: {e}")
    
    def unregister(self, action_id: str) -> bool:
        """Видалити дію з реєстру."""
        if action_id in self.actions:
            action = self.actions[action_id]
            
            # Видаляємо з категорії
            if action.category in self.categories:
                if action_id in self.categories[action.category]:
                    self.categories[action.category].remove(action_id)
            
            del self.actions[action_id]
            self._logger.info(f"Видалено дію: {action_id}")
            return True
        return False
    
    def get_action(self, action_id: str) -> Optional[Action]:
        """Отримати дію за ID."""
        return self.actions.get(action_id)
    
    def get_actions_by_category(self, category: str) -> List[Action]:
        """Отримати всі дії з категорії."""
        if category not in self.categories:
            return []
        
        return [self.actions[action_id] for action_id in self.categories[category] 
                if action_id in self.actions]
    
    def get_all_actions(self) -> List[Action]:
        """Отримати всі зареєстровані дії."""
        return list(self.actions.values())
    
    def get_categories(self) -> List[str]:
        """Отримати список всіх категорій."""
        return list(self.categories.keys())
    
    def execute(self, action_id: str, *args, **kwargs) -> Any:
        """Виконати дію."""
        action = self.get_action(action_id)
        if not action:
            raise ValueError(f"Дія з ID '{action_id}' не знайдена")
        
        if not action.enabled:
            raise ValueError(f"Дія '{action_id}' вимкнена")
        
        self._logger.info(f"Виконується дія: {action.name}")
        return action.callback(*args, **kwargs)

# --- Конфігурація ---
class RegistryConfig(BaseModel):
    """Конфігурація реєстру дій."""
    enabled: bool = True
    allow_overwrite: bool = False
    validate_callbacks: bool = True

def prepare_config_models():
    """Повертає модель конфігурації для реєстру дій."""
    return {'registry': RegistryConfig}

DEFAULT_CONFIG = {
    'registry': {
        'enabled': True,
        'allow_overwrite': False,
        'validate_callbacks': True
    }
}

# --- Основна логіка ---
_registry_instance = None

def initialize(app_context: Dict[str, Any]) -> ActionRegistry:
    """Ініціалізація реєстру дій."""
    global _registry_instance
    
    config = app_context.get('config')
    if config and hasattr(config, 'registry'):
        registry_config = config.registry
        if not registry_config.enabled:
            print("[Registry] Реєстр дій вимкнено в конфігурації")
            return None
    
    # Отримуємо шину подій з контексту
    event_bus = app_context.get('event_bus')
    
    # Створюємо реєстр
    _registry_instance = ActionRegistry(event_bus=event_bus)
    
    # Додаємо реєстр в контекст додатку
    app_context['action_registry'] = _registry_instance
    
    # Публікуємо подію про створення реєстру (якщо event_bus підтримує це)
    if event_bus:
        import time
        event_data = {
            'type': EventType.MODULE_LOADED,
            'source': 'p_020_registry',
            'data': {'module': 'registry', 'status': 'ready'},
            'timestamp': time.time()
        }
        try:
            event_bus.publish(event_data)
        except AttributeError:
            # Якщо event_bus не має методу publish або очікує інший формат
            pass
    
    print(f"[Registry] Реєстр дій ініціалізовано")
    return _registry_instance

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка реєстру дій."""
    global _registry_instance
    
    if _registry_instance:
        _registry_instance.actions.clear()
        _registry_instance.categories.clear()
        _registry_instance = None
    
    print("[Registry] Реєстр дій зупинено")

# --- Допоміжні функції для модулів ---
def register_action(
    app_context: Dict[str, Any],
    action_id: str,
    name: str,
    callback: Callable,
    description: str = "",
    module: str = "unknown",
    category: str = "General",
    icon: str = None,
    **kwargs
) -> bool:
    """
    Допоміжна функція для реєстрації дії з будь-якого модуля.
    """
    registry = app_context.get('action_registry')
    if not registry:
        print(f"[Registry] Помилка: реєстр дій не знайдено в app_context")
        return False
    
    action = Action(
        id=action_id,
        name=name,
        description=description,
        callback=callback,
        module=module,
        category=category,
        icon=icon,
        **kwargs
    )
    
    try:
        registry.register(action)
        return True
    except Exception as e:
        print(f"[Registry] Помилка реєстрації дії {action_id}: {e}")
        return False