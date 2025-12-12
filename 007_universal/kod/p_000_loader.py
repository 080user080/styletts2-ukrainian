# p_000_loader.py
"""
Модуль P_000: ModuleLoader
Сканування, імпорт та ініціалізація модулів.
ВИПРАВЛЕНА ВЕРСІЯ: правильна обробка gr.Blocks об'єктів
"""

import os
import importlib
import inspect
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path
import logging
import traceback

ROOT_LOGGER_NAME = "modular_project"
INTERNAL_LOGGER = logging.getLogger("Loader")

@dataclass
class ModuleInfo:
    prefix: int
    name: str
    filepath: Path
    import_name: str
    module_object: Optional[Any] = None

class ModuleLoader:
    def __init__(self):
        self.app_context: Dict[str, Any] = {
            'config_models': {},
            'modules': []
        }
        self.project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.kod_path = self.project_root / "kod"
        
        self.modules: List[ModuleInfo] = []
        self.initialized_modules: List[str] = []
    
    def _scan_modules(self) -> List[ModuleInfo]:
        """Сканує директорію kod/."""
        found_modules = []
        for fpath in self.kod_path.glob("**/p_[0-9][0-9][0-9]_*.py"):
            if fpath.name == Path(__file__).name: 
                continue
            
            try:
                prefix = int(fpath.name[2:5])
            except ValueError:
                continue

            relative_path = fpath.relative_to(self.project_root)
            import_name = ".".join(relative_path.parts).replace(".py", "")

            found_modules.append(ModuleInfo(
                prefix=prefix,
                name=fpath.name.replace(".py", ""),
                filepath=fpath,
                import_name=import_name
            ))
        
        found_modules.sort(key=lambda m: m.prefix)
        return found_modules
    
    def _import_module(self, module_info: ModuleInfo) -> Any:
        """Імпортує модуль."""
        try:
            mod = importlib.import_module(module_info.import_name)
            module_info.module_object = mod
            return mod
        except ImportError as e:
            INTERNAL_LOGGER.warning(f"Модуль {module_info.name} не може бути імпортований: {e}")
            return None
        except Exception as e:
            INTERNAL_LOGGER.error(f"Помилка імпорту {module_info.name}: {e}")
            return None
    
    def _call_func(self, module: Any, func_name: str, **kwargs) -> Any:
        """Безпечний виклик функції модуля."""
        if module is None:
            return None
            
        if hasattr(module, func_name) and callable(getattr(module, func_name)):
            func = getattr(module, func_name)
            
            try:
                sig = inspect.signature(func)
                if 'app_context' in sig.parameters:
                    return func(self.app_context)
                return func()
            except Exception as e:
                INTERNAL_LOGGER.error(f"Помилка у {func_name}: {e}")
                import traceback
                traceback.print_exc()
                return None
        return None
    
    def _process_initialize_result(self, result: Any, module_name: str) -> Dict[str, Any]:
        """
        Обробляє результат функції initialize().
        
        Може повертати:
        1. gr.Blocks об'єкт (напряму) → зберігаємо як 'демо'
        2. Dict з 'demo' всередині → витягаємо demo
        3. Dict з іншими даними → зберігаємо як є
        4. None → ігноруємо
        """
        if result is None:
            return {}
        
        # Перевірка чи це gr.Blocks об'єкт
        if hasattr(result, 'launch'):
            # Це Gradio демо!
            return {f"{module_name}_demo": result}
        
        # Якщо це dict
        if isinstance(result, dict):
            # Якщо всередині є 'demo' ключ
            if 'demo' in result:
                demo = result['demo']
                
                # Перевірка чи це gr.Blocks
                if hasattr(demo, 'launch'):
                    # Зберігаємо демо окремо
                    result_copy = result.copy()
                    result_copy[f"{module_name}_demo"] = demo
                    return result_copy
            
            # Інші дані в dict - зберігаємо як є
            return result
        
        # Для всіх інших типів даних
        return {module_name: result}
    
    def run(self) -> Dict[str, Any]:
        """Головний цикл запуску."""
        logging.basicConfig(level=logging.INFO, format='[Loader] %(message)s')
        INTERNAL_LOGGER.info("--- ПОЧАТОК ЗАВАНТАЖЕННЯ ---")
        
        try:
            # 1. Сканування модулів
            self.modules = self._scan_modules()
            INTERNAL_LOGGER.info(f"Знайдено модулів: {len(self.modules)}")
            
            # 2. Імпорт модулів
            imported_modules = []
            for m in self.modules:
                mod = self._import_module(m)
                if mod:
                    imported_modules.append(m)
            
            # 3. Збір метаданих (Config Models)
            for m in imported_modules:
                if m.module_object:
                    models = self._call_func(m.module_object, "prepare_config_models")
                    if models and isinstance(models, dict):
                        self.app_context['config_models'].update(models)
            
            # Зберігаємо інформацію про модулі в контексті
            self.app_context['modules'] = [
                {
                    'name': m.name,
                    'prefix': m.prefix,
                    'module_object': m.module_object
                }
                for m in imported_modules
            ]
            
            # 4. Ініціалізація модулів у порядку префіксів
            for m in imported_modules:
                if m.module_object:
                    INTERNAL_LOGGER.info(f"Start: {m.name}")
                    
                    # Виклик ініціалізації
                    result = self._call_func(m.module_object, "initialize")
                    
                    # Зберігаємо в ініціалізованих
                    self.initialized_modules.append(m.name)
                    
                    # Обробляємо результат та зберігаємо в контекст
                    if result is not None:
                        processed = self._process_initialize_result(result, m.name)
                        
                        if processed:
                            self.app_context.update(processed)
                            
                            # Логування того, що було додано
                            for key in processed.keys():
                                if 'demo' in key.lower():
                                    INTERNAL_LOGGER.info(f"  ✅ Демо зареєстровано: {key}")
            
            INTERNAL_LOGGER.info("--- СИСТЕМА ЗАПУЩЕНА ---")
            
            # Показуємо статус всіх демо
            INTERNAL_LOGGER.info("Доступні демо:")
            for key in sorted(self.app_context.keys()):
                if 'demo' in key.lower() and hasattr(self.app_context[key], 'launch'):
                    INTERNAL_LOGGER.info(f"  ✓ {key}")
            
            return self.app_context
            
        except Exception as e:
            INTERNAL_LOGGER.critical("АВАРІЙНА ЗУПИНКА ЗАВАНТАЖЕННЯ")
            traceback.print_exc()
            sys.exit(1)

def initialize(app_context: Dict[str, Any]):
    """Ініціалізація завантажувача."""
    loader = ModuleLoader()
    context = loader.run()
    app_context.update(context)
    return loader