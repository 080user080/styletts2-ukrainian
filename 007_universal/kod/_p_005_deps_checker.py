# p_005_deps_checker.py
"""
Модуль для автоматичної перевірки та встановлення залежностей.
Сканує всі модулі, перевіряє їхні залежності та пропонує встановити відсутні.
"""

import importlib
import subprocess
import sys
from typing import Dict, List, Any, Optional, Tuple
import logging
from dataclasses import dataclass
from pydantic import BaseModel

@dataclass
class Dependency:
    """Інформація про залежність."""
    package: str
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    optional: bool = False
    pip_name: Optional[str] = None  # Якщо відрізняється від імпорту

class DependencyCheckerConfig(BaseModel):
    """Конфігурація перевірки залежностей."""
    enabled: bool = True
    auto_install: bool = False
    check_on_start: bool = True
    log_level: str = "INFO"

def prepare_config_models():
    """Повертає модель конфігурації для перевірки залежностей."""
    return {'deps_checker': DependencyCheckerConfig}

DEFAULT_CONFIG = {
    'deps_checker': {
        'enabled': True,
        'auto_install': False,
        'check_on_start': True,
        'log_level': 'INFO'
    }
}

class DependencyChecker:
    """Система перевірки залежностей."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("DependencyChecker")
        self.modules_deps: Dict[str, List[Dependency]] = {}
        self.missing_deps: Dict[str, List[str]] = {}
        self.install_queue: List[str] = []
        
    def register_module_deps(self, module_name: str, deps: List[Dependency]):
        """Реєструє залежності для модуля."""
        self.modules_deps[module_name] = deps
        self.logger.debug(f"Зареєстровано залежності для {module_name}: {len(deps)}")
    
    def check_package(self, package: str, min_version: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Перевіряє, чи встановлений пакет та його версію."""
        pip_package = package.replace('_', '-')
        
        try:
            # Спроба імпорту
            module = importlib.import_module(package)
            
            # Перевірка версії, якщо вказано
            if min_version and hasattr(module, '__version__'):
                from packaging import version
                if version.parse(module.__version__) < version.parse(min_version):
                    return False, f"версія {module.__version__} < {min_version}"
            
            return True, getattr(module, '__version__', None)
        except ImportError:
            return False, None
    
    def scan_all_modules(self):
        """Сканує всі модулі на предмет залежностей."""
        self.logger.info("Сканування залежностей модулів...")
        
        # Отримуємо всі завантажені модулі
        loader = self.app_context.get('module_loader')
        if not loader:
            self.logger.warning("ModuleLoader не знайдено в контексті")
            return
        
        for module_info in loader.modules:
            module = module_info.module_object
            if not module:
                continue
            
            # Шукаємо функцію check_dependencies в модулі
            if hasattr(module, 'check_dependencies'):
                try:
                    deps_result = module.check_dependencies()
                    
                    # Обробляємо різні формати результатів
                    if isinstance(deps_result, dict):
                        # Словник з інформацією
                        if not deps_result.get('all_available', True):
                            missing = deps_result.get('missing_packages', [])
                            self.missing_deps[module_info.name] = missing
                            self.logger.warning(f"Модуль {module_info.name} має відсутні залежності: {missing}")
                    
                    elif deps_result is False:
                        # Просто False
                        self.logger.warning(f"Модуль {module_info.name} має незадоволені залежності")
                
                except Exception as e:
                    self.logger.error(f"Помилка перевірки залежностей {module_info.name}: {e}")
    
    def install_package(self, package: str) -> bool:
        """Встановлює пакет через pip."""
        try:
            self.logger.info(f"Встановлення {package}...")
            
            # Використовуємо pip з поточного середовища
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                self.logger.info(f"✅ {package} успішно встановлено")
                return True
            else:
                self.logger.error(f"❌ Помилка встановлення {package}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Виняток при встановленні {package}: {e}")
            return False
    
    def auto_install_missing(self) -> Dict[str, bool]:
        """Автоматичне встановлення всіх відсутніх залежностей."""
        results = {}
        
        for module_name, packages in self.missing_deps.items():
            for package in packages:
                if package not in self.install_queue:
                    self.install_queue.append(package)
        
        for package in self.install_queue:
            results[package] = self.install_package(package)
        
        return results
    
    def generate_requirements(self) -> str:
        """Генерує requirements.txt на основі залежностей."""
        requirements = []
        
        for module_name, deps in self.modules_deps.items():
            for dep in deps:
                if dep.pip_name:
                    pkg = dep.pip_name
                else:
                    pkg = dep.package
                
                if dep.min_version:
                    requirements.append(f"{pkg}>={dep.min_version}")
                else:
                    requirements.append(pkg)
        
        # Видаляємо дублікати
        requirements = list(set(requirements))
        requirements.sort()
        
        return "\n".join(requirements)
    
    def get_status(self) -> Dict[str, Any]:
        """Повертає статус залежностей."""
        return {
            'modules_scanned': len(self.modules_deps),
            'missing_dependencies': self.missing_deps,
            'install_queue': self.install_queue,
            'requirements': self.generate_requirements()
        }

def initialize(app_context: Dict[str, Any]):
    """Ініціалізація перевірки залежностей."""
    config = app_context.get('config')
    
    # Перевіряємо, чи увімкнено модуль
    if config and hasattr(config, 'deps_checker'):
        deps_config = config.deps_checker
        if not deps_config.enabled:
            print("[DepsChecker] Модуль вимкнено в конфігурації")
            return None
    
    checker = DependencyChecker(app_context)
    app_context['deps_checker'] = checker
    
    # Якщо налаштовано, скануємо одразу
    if config and hasattr(config, 'deps_checker') and config.deps_checker.check_on_start:
        checker.scan_all_modules()
        
        # Автовстановлення, якщо налаштовано
        if config.deps_checker.auto_install and checker.missing_deps:
            print("[DepsChecker] Автоматичне встановлення відсутніх залежностей...")
            checker.auto_install_missing()
    
    print(f"[DepsChecker] Ініціалізовано. Відсутні залежності: {len(checker.missing_deps)} модулів")
    return checker

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка перевірки залежностей."""
    if 'deps_checker' in app_context:
        del app_context['deps_checker']
    print("[DepsChecker] Модуль зупинено")