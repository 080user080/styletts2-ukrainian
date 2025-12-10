# p_005_universal_deps_checker.py
"""
Універсальний модуль перевірки залежностей.
Сканує всі модулі проекту, виявляє імпорти та автоматично встановлює відсутні бібліотеки.
"""

import ast
import importlib
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
import logging
from pydantic import BaseModel, Field
import traceback

class DependencyConfig(BaseModel):
    """Конфігурація перевірки залежностей."""
    enabled: bool = True
    auto_install: bool = False
    check_on_start: bool = True
    log_level: str = "INFO"
    skip_packages: List[str] = Field(default_factory=lambda: [
        "typing", "collections", "dataclasses", "pathlib", "os", "sys",
        "logging", "json", "yaml", "time", "datetime", "re", "math", "random"
    ])
    required_packages: Dict[str, str] = Field(default_factory=dict)  # package: min_version

def prepare_config_models():
    """Повертає модель конфігурації для універсального перевірника залежностей."""
    return {'universal_deps_checker': DependencyConfig}

DEFAULT_CONFIG = {
    'universal_deps_checker': {
        'enabled': True,
        'auto_install': False,
        'check_on_start': True,
        'log_level': 'INFO',
        'skip_packages': [
            "typing", "collections", "dataclasses", "pathlib", "os", "sys",
            "logging", "json", "yaml", "time", "datetime", "re", "math", "random"
        ],
        'required_packages': {}
    }
}

class ImportAnalyzer(ast.NodeVisitor):
    """Аналізатор AST для виявлення імпортів."""
    
    def __init__(self):
        self.imports: Set[str] = set()
        self.from_imports: Dict[str, Set[str]] = {}
    
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name.split('.')[0])
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            module = node.module.split('.')[0]
            if module not in self.from_imports:
                self.from_imports[module] = set()
            for alias in node.names:
                self.from_imports[module].add(alias.name)

class UniversalDependencyChecker:
    """Універсальний перевірник залежностей для всіх модулів."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("UniversalDepsChecker")
        self.config = None
        
        # Результати аналізу
        self.all_dependencies: Dict[str, Set[str]] = {}  # module -> set of packages
        self.found_packages: Set[str] = set()
        self.missing_packages: Dict[str, List[str]] = {}  # package -> [modules]
        self.install_results: Dict[str, bool] = {}
        
        # Отримуємо конфігурацію
        if 'config' in app_context and hasattr(app_context['config'], 'universal_deps_checker'):
            self.config = app_context['config'].universal_deps_checker
    
    def extract_imports_from_file(self, filepath: Path) -> Set[str]:
        """Витягує всі імпорти з файлу Python."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            analyzer = ImportAnalyzer()
            analyzer.visit(tree)
            
            # Об'єднуємо всі імпорти
            all_imports = set(analyzer.imports)
            for module in analyzer.from_imports:
                all_imports.add(module)
            
            return all_imports
        except Exception as e:
            self.logger.warning(f"Не вдалося проаналізувати {filepath}: {e}")
            return set()
    
    # p_005_universal_deps_checker.py (оновлена функція scan_module)
    def scan_module(self, module_path: Path) -> Set[str]:
        """Сканує один модуль на предмет залежностей."""
        imports = self.extract_imports_from_file(module_path)
        
        # Фільтруємо стандартні бібліотеки та вбудовані модулі
        filtered_imports = set()
        
        for imp in imports:
            # Ігноруємо стандартні модулі з конфігурації
            if self.config and imp in self.config.skip_packages:
                continue
            
            # АВТОМАТИЧНЕ виявлення внутрішніх модулів проєкту
            # Внутрішні модулі: починаються з p_, kod.p_, або містять шляхи проєкту
            is_internal_module = (
                imp.startswith('p_') or 
                imp.startswith('kod.p_') or
                imp.startswith('kod.') and any(part.startswith('p_') for part in imp.split('.'))
            )
            
            if is_internal_module:
                continue  # Це внутрішній модуль проєкту
            
            # Ігноруємо вбудовані модулі
            if imp.startswith('_'):
                continue
            
            filtered_imports.add(imp)
    
        return filtered_imports
    
    def scan_all_modules(self, kod_path: Path) -> Dict[str, Set[str]]:
        """Сканує всі модулі в папці kod/."""
        self.logger.info(f"Сканування модулів у {kod_path}")
        
        dependencies = {}
        
        # Знаходимо всі Python файли
        for py_file in kod_path.glob("**/*.py"):
            # Ігноруємо файли, що починаються з _
            if py_file.name.startswith('_'):
                continue
            
            # Отримуємо відносний шлях для імені модуля
            rel_path = py_file.relative_to(kod_path.parent)
            module_name = str(rel_path).replace(os.sep, '.').replace('.py', '')
            
            # Скануємо імпорти
            imports = self.scan_module(py_file)
            if imports:
                dependencies[module_name] = imports
                self.found_packages.update(imports)
                
                self.logger.debug(f"  {module_name}: {len(imports)} залежностей")
        
        self.all_dependencies = dependencies
        self.logger.info(f"Знайдено {len(dependencies)} модулів з {len(self.found_packages)} унікальних пакетів")
        return dependencies
    
    def check_package_available(self, package_name: str) -> Tuple[bool, Optional[str]]:
        """Перевіряє, чи доступний пакет та його версію."""
        # АВТОМАТИЧНЕ виявлення внутрішніх модулів проєкту
        if package_name.startswith('p_') or package_name.startswith('kod.p_'):
            return True, None  # Внутрішній модуль - вважаємо доступним
        """Перевіряє, чи доступний пакет та його версію."""
        # Спеціальні випадки
        if package_name in ['yaml']:
            package_name = 'PyYAML'
        elif package_name in ['PIL']:
            package_name = 'Pillow'
        
        try:
            # Спроба імпорту
            module = importlib.import_module(package_name)
            
            # Отримання версії, якщо можливо
            version = None
            if hasattr(module, '__version__'):
                version = module.__version__
            elif hasattr(module, 'version'):
                version = module.version
            
            return True, version
        except ImportError:
            # Спроба альтернативних назв
            alt_names = {
                'sklearn': 'scikit-learn',
                'cv2': 'opencv-python',
                'bs4': 'beautifulsoup4',
                'dateutil': 'python-dateutil',
            }
            
            if package_name in alt_names:
                return self.check_package_available(alt_names[package_name])
            
            return False, None
        except Exception as e:
            self.logger.debug(f"Помилка перевірки {package_name}: {e}")
            return False, None
    
    def check_all_dependencies(self) -> Dict[str, List[str]]:
        """Перевіряє наявність всіх знайдених залежностей."""
        self.logger.info("Перевірка наявності всіх залежностей...")
        
        missing = {}
        
        for package in sorted(self.found_packages):
            # Пропускаємо стандартні модулі
            if self.config and package in self.config.skip_packages:
                continue
            
            # Перевіряємо наявність
            available, version = self.check_package_available(package)
            
            if available:
                self.logger.debug(f"  ✅ {package} {version or ''}")
            else:
                # Знаходимо, які модулі потребують цей пакет
                requiring_modules = []
                for module, imports in self.all_dependencies.items():
                    if package in imports:
                        requiring_modules.append(module)
                
                missing[package] = requiring_modules
                self.logger.warning(f"  ❌ {package} (потрібен для: {len(requiring_modules)} модулів)")
        
        self.missing_packages = missing
        return missing
    
    def install_package(self, package_name: str) -> bool:
        """Встановлює пакет через pip."""
        # Мапа альтернативних назв для pip
        pip_names = {
            'yaml': 'PyYAML',
            'PIL': 'Pillow',
            'sklearn': 'scikit-learn',
            'cv2': 'opencv-python',
            'bs4': 'beautifulsoup4',
            'dateutil': 'python-dateutil',
            'dotenv': 'python-dotenv',
        }
        
        pip_package = pip_names.get(package_name, package_name)
        
        try:
            self.logger.info(f"Встановлення {pip_package}...")
            
            # Використовуємо pip з поточного середовища
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pip_package],
                capture_output=True,
                text=True,
                check=False,
                timeout=60
            )
            
            if result.returncode == 0:
                self.logger.info(f"✅ {pip_package} успішно встановлено")
                self.install_results[pip_package] = True
                
                # Перевіряємо, чи тепер пакет доступний
                available, version = self.check_package_available(package_name)
                if available:
                    self.logger.info(f"   Версія: {version or 'невідома'}")
                return True
            else:
                self.logger.error(f"❌ Помилка встановлення {pip_package}: {result.stderr[:200]}")
                self.install_results[pip_package] = False
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ Таймаут при встановленні {pip_package}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Виняток при встановленні {pip_package}: {e}")
            return False
    
    def auto_install_missing(self) -> Dict[str, bool]:
        """Автоматично встановлює всі відсутні залежності."""
        if not self.missing_packages:
            self.logger.info("Немає відсутніх залежностей для встановлення")
            return {}
        
        self.logger.info(f"Автоматичне встановлення {len(self.missing_packages)} відсутніх пакетів...")
        
        results = {}
        for package in sorted(self.missing_packages.keys()):
            results[package] = self.install_package(package)
        
        return results
    
    def generate_requirements_file(self, output_path: Optional[Path] = None) -> str:
        """Генерує файл requirements.txt з усіма залежностями."""
        if not output_path:
            output_path = Path.cwd() / "requirements_auto.txt"
        
        requirements = []
        
        for package in sorted(self.found_packages):
            # Пропускаємо стандартні модулі
            if self.config and package in self.config.skip_packages:
                continue
            
            # Перевіряємо наявність та версію
            available, version = self.check_package_available(package)
            
            if available and version:
                # Спрощуємо версію
                version_simple = version.split('+')[0].split('-')[0]
                requirements.append(f"{package}>={version_simple}")
            elif available:
                requirements.append(package)
            else:
                requirements.append(f"# {package} - відсутній")
        
        # Додаємо коментарі про відсутні пакети
        if self.missing_packages:
            requirements.append("\n# ВІДСУТНІ ПАКЕТИ (потрібно встановити):")
            for package, modules in self.missing_packages.items():
                module_list = ", ".join(modules[:3])
                if len(modules) > 3:
                    module_list += f" та ще {len(modules) - 3}"
                requirements.append(f"# {package}  # потрібен для: {module_list}")
        
        content = "\n".join(sorted(set(requirements)))
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# Автоматично згенеровано UniversalDepsChecker\n")
                f.write(f"# Загалом пакетів: {len(self.found_packages)}\n\n")
                f.write(content)
            
            self.logger.info(f"Файл вимог збережено: {output_path}")
            return str(output_path)
        except Exception as e:
            self.logger.error(f"Помилка збереження requirements: {e}")
            return ""
    
    def get_summary(self) -> Dict[str, Any]:
        """Повертає зведення про залежності."""
        return {
            'total_modules': len(self.all_dependencies),
            'total_packages_found': len(self.found_packages),
            'missing_packages_count': len(self.missing_packages),
            'missing_packages': self.missing_packages,
            'install_results': self.install_results,
            'config': self.config.dict() if self.config else None
        }
    
    def run_full_check(self, kod_path: Path) -> bool:
        """Виконує повну перевірку залежностей."""
        try:
            # 1. Сканування всіх модулів
            self.scan_all_modules(kod_path)
            
            # 2. Перевірка наявності
            missing = self.check_all_dependencies()
            
            # 3. Автоматичне встановлення (якщо налаштовано)
            if missing and self.config and self.config.auto_install:
                self.auto_install_missing()
            
            # 4. Генерація requirements.txt
            self.generate_requirements_file()
            
            # 5. Зведення
            summary = self.get_summary()
            
            if missing:
                self.logger.warning(f"Знайдено {len(missing)} відсутніх пакетів")
                return False
            else:
                self.logger.info("✅ Всі залежності доступні")
                return True
                
        except Exception as e:
            self.logger.error(f"Помилка під час перевірки залежностей: {e}")
            traceback.print_exc()
            return False

def initialize(app_context: Dict[str, Any]):
    """Ініціалізація універсального перевірника залежностей."""
    config = app_context.get('config')
    
    # Перевіряємо, чи увімкнено модуль
    if config and hasattr(config, 'universal_deps_checker'):
        deps_config = config.universal_deps_checker
        if not deps_config.enabled:
            print("[UniversalDepsChecker] Модуль вимкнено в конфігурації")
            return None
    else:
        print("[UniversalDepsChecker] Конфігурація не знайдена, використовуються значення за замовчуванням")
        deps_config = DependencyConfig()
    
    # Створюємо перевірника
    checker = UniversalDependencyChecker(app_context)
    app_context['universal_deps_checker'] = checker
    
    # Отримуємо шлях до папки kod
    project_root = Path(app_context.get('project_root', os.getcwd()))
    kod_path = project_root / "kod"
    
    if not kod_path.exists():
        print(f"[UniversalDepsChecker] Помилка: папка {kod_path} не знайдена")
        return checker
    
    # Запускаємо перевірку (якщо налаштовано)
    if deps_config.check_on_start:
        print("[UniversalDepsChecker] Запуск автоматичної перевірки залежностей...")
        success = checker.run_full_check(kod_path)
        
        if not success and checker.missing_packages:
            print("\n" + "="*60)
            print("ВІДСУТНІ ЗАЛЕЖНОСТІ:")
            print("="*60)
            for package, modules in checker.missing_packages.items():
                print(f"❌ {package} - потрібен для: {', '.join(modules[:3])}")
            
            if deps_config.auto_install:
                print("\nСпробуйте встановити вручну:")
                for package in checker.missing_packages:
                    print(f"pip install {package}")
            print("="*60 + "\n")
    
    print(f"[UniversalDepsChecker] Ініціалізовано. Знайдено пакетів: {len(checker.found_packages)}")
    return checker

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка перевірника залежностей."""
    if 'universal_deps_checker' in app_context:
        del app_context['universal_deps_checker']
    print("[UniversalDepsChecker] Модуль зупинено")

# Додаткові утиліти для використання в інших модулях
def check_and_install(package_name: str, app_context: Dict[str, Any]) -> bool:
    """Утиліта для перевірки та встановлення конкретного пакета."""
    checker = app_context.get('universal_deps_checker')
    if not checker:
        print(f"[UniversalDepsChecker] Перевірник не знайдено в контексті")
        return False
    
    available, version = checker.check_package_available(package_name)
    if available:
        print(f"✅ {package_name} вже встановлено (версія: {version or 'невідома'})")
        return True
    
    print(f"⚠️  {package_name} відсутній, спроба встановлення...")
    return checker.install_package(package_name)

def get_missing_dependencies(app_context: Dict[str, Any]) -> List[str]:
    """Отримати список відсутніх залежностей."""
    checker = app_context.get('universal_deps_checker')
    if not checker:
        return []
    
    return list(checker.missing_packages.keys())