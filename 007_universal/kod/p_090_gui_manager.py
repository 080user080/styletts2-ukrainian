# p_030_gui_manager.py
"""
Менеджер графічних інтерфейсів.
"""

from typing import Dict, List, Any, Optional
import logging
from enum import Enum
from pydantic import BaseModel, Field

class GUIType(Enum):
    """Типи підтримуваних GUI."""
    GRADIO = "gradio"
    TKINTER = "tkinter"
    WEB = "web"
    CUSTOM = "custom"

# ⚠️ ДОДАЄМО ВІДСУТНІЙ КЛАС КОНФІГУРАЦІЇ
class GUIManagerConfig(BaseModel):
    """Конфігурація GUI менеджера."""
    enabled: bool = True
    autostart: bool = True
    default_gui: str = "gradio"  # Зберігаємо як строку для простоти
    available_guis: List[str] = Field(default_factory=lambda: ["gradio"])
    port_range_start: int = 7860
    port_range_end: int = 7890

def prepare_config_models():
    """Повертає модель конфігурації для GUI менеджера."""
    return {'gui_manager': GUIManagerConfig}

# ⚠️ ОНОВЛЮЄМО DEFAULT_CONFIG
DEFAULT_CONFIG = {
    'gui_manager': {
        'enabled': True,
        'autostart': True,
        'default_gui': 'gradio',
        'available_guis': ['gradio'],
        'port_range_start': 7860,
        'port_range_end': 7890
    }
}

class GUIInfo:
    """Інформація про GUI модуль."""
    
    def __init__(self, module_name: str, gui_type: GUIType, display_name: str,
                 description: str = "", priority: int = 100):
        self.module_name = module_name
        self.gui_type = gui_type
        self.display_name = display_name
        self.description = description
        self.priority = priority
        self.enabled: bool = True
        self.instance: Any = None
        self.port: Optional[int] = None

class GUIManager:
    """Менеджер графічних інтерфейсів."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("GUIManager")
        self.guis: Dict[str, GUIInfo] = {}
        self.active_guis: Dict[str, GUIInfo] = {}
        self.config = None
        
        # Отримуємо конфігурацію
        if 'config' in app_context and hasattr(app_context['config'], 'gui_manager'):
            self.config = app_context['config'].gui_manager
    
    def register_gui(self, gui_info: GUIInfo) -> bool:
        """Реєструє новий GUI модуль."""
        if gui_info.module_name in self.guis:
            self.logger.warning(f"GUI {gui_info.module_name} вже зареєстровано")
            return False
        
        self.guis[gui_info.module_name] = gui_info
        self.logger.info(f"Зареєстровано GUI: {gui_info.display_name} ({gui_info.gui_type.value})")
        return True
    
    def get_available_guis(self) -> List[GUIInfo]:
        """Повертає список доступних GUI."""
        return [gui for gui in self.guis.values() if gui.enabled]
    
    def get_gui_by_type(self, gui_type: GUIType) -> Optional[GUIInfo]:
        """Знаходить GUI за типом."""
        for gui in self.guis.values():
            if gui.gui_type == gui_type and gui.enabled:
                return gui
        return None
    
    def start_gui(self, gui_name: str, **kwargs) -> bool:
        """Запускає вказаний GUI."""
        if gui_name not in self.guis:
            self.logger.error(f"GUI {gui_name} не знайдено")
            return False
        
        gui_info = self.guis[gui_name]
        if not gui_info.enabled:
            self.logger.error(f"GUI {gui_name} вимкнено")
            return False
        
        # Тут логіка запуску GUI
        # ...
        return True

def initialize(app_context: Dict[str, Any]):
    """Ініціалізація менеджера GUI."""
    manager = GUIManager(app_context)
    app_context['gui_manager'] = manager
    return manager

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка менеджера GUI."""
    if 'gui_manager' in app_context:
        del app_context['gui_manager']