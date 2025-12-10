# p_010_event_types.py
"""
Загальні типи подій для всієї системи.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any

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
    
    def __post_init__(self):
        import time
        self.timestamp = time.time()