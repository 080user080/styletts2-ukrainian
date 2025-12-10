# p_006_error_handler.py
"""
Модуль для обробки помилок завантаження модулів.
Дозволяє безпечно пропускати модулі з помилками.
"""

import traceback
import sys
from typing import Dict, Any, Optional, Callable
import logging
from pydantic import BaseModel

class ErrorHandlerConfig(BaseModel):
    """Конфігурація обробника помилок."""
    enabled: bool = True
    skip_failed_modules: bool = True
    log_errors: bool = True
    max_error_length: int = 1000
    retry_count: int = 0

def prepare_config_models():
    """Повертає модель конфігурації для обробки помилок."""
    return {'error_handler': ErrorHandlerConfig}

DEFAULT_CONFIG = {
    'error_handler': {
        'enabled': True,
        'skip_failed_modules': True,
        'log_errors': True,
        'max_error_length': 1000,
        'retry_count': 0
    }
}

class ModuleError:
    """Інформація про помилку модуля."""
    
    def __init__(self, module_name: str, error_type: str, message: str, traceback_str: str):
        self.module_name = module_name
        self.error_type = error_type
        self.message = message
        self.traceback_str = traceback_str
        self.retry_count = 0

class ErrorHandler:
    """Централізований обробник помилок."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("ErrorHandler")
        self.errors: Dict[str, ModuleError] = {}
        self.config = None
        
        # Отримуємо конфігурацію
        if 'config' in app_context and hasattr(app_context['config'], 'error_handler'):
            self.config = app_context['config'].error_handler
    
    def safe_import(self, import_func: Callable, module_name: str) -> Any:
        """Безпечний імпорт модуля з обробкою помилок."""
        try:
            return import_func()
        except ImportError as e:
            error_msg = str(e)
            
            # Аналізуємо помилку імпорту
            if "No module named" in error_msg:
                # Виділяємо назву модуля
                module_match = error_msg.split("'")
                missing_module = module_match[1] if len(module_match) > 1 else "unknown"
                
                self.logger.warning(f"Модуль {module_name}: відсутня залежність '{missing_module}'")
                
                # Записуємо помилку
                self.errors[module_name] = ModuleError(
                    module_name=module_name,
                    error_type="MissingDependency",
                    message=f"Відсутня залежність: {missing_module}",
                    traceback_str=traceback.format_exc()
                )
                
                # Повертаємо спеціальний маркер для пропуску модуля
                return None
            else:
                # Інша помилка імпорту
                self.logger.error(f"Помилка імпорту модуля {module_name}: {error_msg}")
                self.errors[module_name] = ModuleError(
                    module_name=module_name,
                    error_type="ImportError",
                    message=error_msg,
                    traceback_str=traceback.format_exc()
                )
                return None
                
        except Exception as e:
            # Будь-яка інша помилка
            error_type = type(e).__name__
            self.logger.error(f"Критична помилка в модулі {module_name}: {error_type}: {e}")
            
            self.errors[module_name] = ModuleError(
                module_name=module_name,
                error_type=error_type,
                message=str(e),
                traceback_str=traceback.format_exc()[:self.config.max_error_length if self.config else 1000]
            )
            
            if self.config and not self.config.skip_failed_modules:
                raise  # Піднімаємо помилку далі, якщо не дозволено пропускати
                
            return None
    
    def safe_call(self, func: Callable, module_name: str, func_name: str, *args, **kwargs) -> Any:
        """Безпечний виклик функції модуля."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_type = type(e).__name__
            error_key = f"{module_name}.{func_name}"
            
            self.logger.error(f"Помилка у {error_key}: {error_type}: {e}")
            
            self.errors[error_key] = ModuleError(
                module_name=module_name,
                error_type=error_type,
                message=f"Помилка в {func_name}: {e}",
                traceback_str=traceback.format_exc()[:self.config.max_error_length if self.config else 1000]
            )
            
            return None
    
    def has_errors(self) -> bool:
        """Перевіряє, чи є помилки."""
        return len(self.errors) > 0
    
    def get_errors_summary(self) -> str:
        """Повертає зведення помилок."""
        if not self.errors:
            return "✅ Помилок немає"
        
        summary = f"⛔ Знайдено помилок: {len(self.errors)}\n\n"
        
        for module_name, error in self.errors.items():
            summary += f"📦 {module_name}:\n"
            summary += f"   Тип: {error.error_type}\n"
            summary += f"   Повідомлення: {error.message[:200]}...\n\n"
        
        return summary
    
    def clear_errors(self):
        """Очищає всі помилки."""
        self.errors.clear()

def initialize(app_context: Dict[str, Any]):
    """Ініціалізація обробника помилок."""
    config = app_context.get('config')
    
    # Перевіряємо, чи увімкнено модуль
    if config and hasattr(config, 'error_handler'):
        error_config = config.error_handler
        if not error_config.enabled:
            print("[ErrorHandler] Модуль вимкнено в конфігурації")
            return None
    
    handler = ErrorHandler(app_context)
    app_context['error_handler'] = handler
    
    print("[ErrorHandler] Ініціалізовано")
    return handler

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка обробника помилок."""
    if 'error_handler' in app_context:
        # Виводимо зведення помилок при завершенні
        handler = app_context['error_handler']
        if handler.has_errors():
            print("\n" + "="*60)
            print("ЗВЕДЕННЯ ПОМИЛОК ПРИ ЗАВАНТАЖЕННІ:")
            print("="*60)
            print(handler.get_errors_summary())
        
        del app_context['error_handler']
    
    print("[ErrorHandler] Модуль зупинено")