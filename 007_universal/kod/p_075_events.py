# p_015_events.py
"""
Система подій для комунікації між модулями.
Дозволяє модулям публікувати та підписуватися на події.
"""

from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from enum import Enum
import logging
from pydantic import BaseModel

class EventType(Enum):
    """Типи системних подій."""
    MODULE_LOADED = "module_loaded"
    MODULE_STOPPED = "module_stopped"
    ACTION_REGISTERED = "action_registered"
    GUI_READY = "gui_ready"
    CONFIG_VALIDATED = "config_validated"
    APP_STARTING = "app_starting"
    APP_STOPPING = "app_stopping"

@dataclass
class Event:
    """Представлення події."""
    type: EventType
    source: str
    data: Dict[str, Any] = None
    timestamp: float = None
    
    def __post_init__(self):
        import time
        if self.timestamp is None:
            self.timestamp = time.time()

class EventBus:
    """Центральна шина подій."""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._logger = logging.getLogger("EventBus")
    
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Підписатися на подію певного типу."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            self._logger.debug(f"Додано підписника для {event_type}: {callback.__name__}")
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Відписатися від події."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                self._logger.debug(f"Видалено підписника для {event_type}: {callback.__name__}")
            except ValueError:
                pass
    
    def publish(self, event: Any) -> None:
        """Опублікувати подію."""
        # Підтримка як об'єкта Event, так і словника
        if isinstance(event, dict):
            event_type_str = event.get('type')
            if isinstance(event_type_str, str):
                event_type = event_type_str
            elif hasattr(event_type_str, 'value'):
                event_type = event_type_str.value
            else:
                event_type = str(event_type_str)
            
            source = event.get('source', 'unknown')
            self._logger.debug(f"Подія (dict): {event_type} від {source}")
        else:
            # Якщо це об'єкт Event
            event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
            source = event.source
            self._logger.debug(f"Подія (obj): {event_type} від {source}")
        
        # Викликаємо всіх підписників
        # Потрібно знайти правильний ключ
        for ev_type, callbacks in self._subscribers.items():
            if str(ev_type.value) == str(event_type):
                for callback in callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        self._logger.error(f"Помилка в обробнику події {event_type}: {e}")

# --- Конфігурація ---
class EventBusConfig(BaseModel):
    """Конфігурація системи подій."""
    enabled: bool = True
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR

def prepare_config_models():
    """Повертає модель конфігурації для системи подій."""
    return {'events': EventBusConfig}

DEFAULT_CONFIG = {
    'events': {
        'enabled': True,
        'log_level': 'INFO'
    }
}

# --- Основна логіка ---
_event_bus_instance = None

def initialize(app_context: Dict[str, Any]) -> EventBus:
    """Ініціалізація системи подій."""
    global _event_bus_instance
    
    config = app_context.get('config')
    events_config = None
    
    if config and hasattr(config, 'events'):
        events_config = config.events
        if not events_config.enabled:
            print("[Events] Система подій вимкнена в конфігурації")
            return None
    
    # Створюємо шину подій
    _event_bus_instance = EventBus()
    
    # Налаштовуємо логування
    logger = logging.getLogger("EventBus")
    
    if events_config:
        # Використовуємо налаштування з конфігурації
        log_level_str = events_config.log_level.upper()
        try:
            log_level = getattr(logging, log_level_str, logging.INFO)
        except AttributeError:
            log_level = logging.INFO
            logger.warning(f"Невірний рівень логування: {log_level_str}, використовую INFO")
    else:
        # Значення за замовчуванням
        log_level = logging.INFO
    
    logger.setLevel(log_level)
    
    # Додаємо шину в контекст додатку
    app_context['event_bus'] = _event_bus_instance
    
    # Публікуємо подію про створення шини
    _event_bus_instance.publish(Event(
        type=EventType.MODULE_LOADED,
        source="p_015_events",
        data={'module': 'events', 'status': 'ready'}
    ))
    
    print(f"[Events] Система подій ініціалізована (рівень логування: {events_config.log_level if events_config else 'INFO'})")
    return _event_bus_instance

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка системи подій."""
    global _event_bus_instance
    
    if _event_bus_instance:
        _event_bus_instance.publish(Event(
            type=EventType.APP_STOPPING,
            source="p_015_events",
            data={'message': 'Система зупиняється'}
        ))
        
        # Очищаємо всіх підписників
        _event_bus_instance._subscribers.clear()
        _event_bus_instance = None
    
    print("[Events] Система подій зупинена")