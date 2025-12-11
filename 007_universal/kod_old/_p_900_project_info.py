# p_900_project_info.py
"""
Модуль для документування проекту.
Збирає інформацію про всі модулі, конфігурації, залежності та взаємодії.
Створює повну документацію проекту для швидкого розуміння архітектури.
"""

import os
import ast
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import logging
import json
from datetime import datetime

class ProjectInfoCollector:
    """Збирач інформації про весь проект."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("ProjectInfo")
        
        # Шляхи
        self.project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.kod_path = self.project_root / "kod"
        self.output_dir = self.project_root / "project_info"
        
        # Створюємо папку для звітів
        self.output_dir.mkdir(exist_ok=True)
        
        # Зберігаємо інформацію
        self.modules_info: Dict[str, Dict] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        self.config_sections: Set[str] = set()
        self.components: Dict[str, str] = {}
        
    def analyze_module(self, filepath: Path) -> Dict[str, Any]:
        """Аналізує модуль та повертає детальну інформацію."""
        info = {
            'name': filepath.stem,
            'file': str(filepath.relative_to(self.project_root)),
            'size_bytes': filepath.stat().st_size,
            'last_modified': datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
            'functions': [],
            'classes': [],
            'imports': [],
            'config_sections': [],
            'dependencies': [],
            'description': '',
            'docstring': '',
            'api': []
        }
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
                info['line_count'] = len(lines)
                
                # Отримуємо префікс
                prefix = 0
                if info['name'].startswith('p_') and len(info['name']) > 3:
                    try:
                        prefix = int(info['name'][2:5])
                        info['prefix'] = prefix
                    except:
                        pass
                
                # Аналізуємо AST
                tree = ast.parse(content, filename=filepath.name)
                
                # Докстрінг модуля
                info['docstring'] = ast.get_docstring(tree) or ''
                if info['docstring']:
                    info['description'] = info['docstring'].split('\n')[0]
                
                # Збираємо всю інформацію про модуль
                self._extract_ast_info(tree, info, filepath)
                
                # Шукаємо конфігурації
                self._extract_config_info(content, info)
                
                # Шукаємо залежності
                self._extract_dependencies(content, info)
                
                # Визначаємо API модуля (функції, що експортуються)
                self._extract_api_info(content, info)
                
        except Exception as e:
            self.logger.warning(f"Помилка аналізу {filepath.name}: {e}")
            info['error'] = str(e)
        
        return info
    
    def _extract_ast_info(self, tree: ast.AST, info: Dict, filepath: Path):
        """Витягує інформацію з AST дерева."""
        # Знаходимо всі функції
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'docstring': ast.get_docstring(node) or '',
                    'lineno': node.lineno,
                    'args': [arg.arg for arg in node.args.args],
                    'returns': 'bool' if node.returns else 'None'
                }
                
                # Визначаємо тип функції
                if node.name == 'initialize':
                    func_info['type'] = 'init'
                elif node.name == 'prepare_config_models':
                    func_info['type'] = 'config'
                elif node.name == 'check_dependencies':
                    func_info['type'] = 'deps'
                elif node.name == 'stop':
                    func_info['type'] = 'cleanup'
                else:
                    func_info['type'] = 'custom'
                
                info['functions'].append(func_info)
                
                # Додаємо до API
                if node.name in ['initialize', 'prepare_config_models']:
                    info['api'].append({
                        'function': node.name,
                        'description': ast.get_docstring(node) or '',
                        'type': 'required' if node.name == 'initialize' else 'optional'
                    })
            
            # Знаходимо всі класи
            elif isinstance(node, ast.ClassDef):
                class_info = {
                    'name': node.name,
                    'docstring': ast.get_docstring(node) or '',
                    'lineno': node.lineno,
                    'bases': [base.id if isinstance(base, ast.Name) else str(base) 
                             for base in node.bases]
                }
                info['classes'].append(class_info)
            
            # Збираємо імпорти
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    info['imports'].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    info['imports'].append(f"{module}.{alias.name}" if module else alias.name)
    
    def _extract_config_info(self, content: str, info: Dict):
        """Витягує інформацію про конфігурацію."""
        # Шукаємо DEFAULT_CONFIG
        if 'DEFAULT_CONFIG' in content:
            info['has_default_config'] = True
        
        # Шукаємо prepare_config_models
        if 'prepare_config_models' in content:
            info['has_config_models'] = True
            
            # Спроба витягти назви секцій конфігурації
            import re
            pattern = r"return\s+{([^}]+)}"
            matches = re.search(pattern, content, re.DOTALL)
            if matches:
                # Спрощений парсинг
                sections = re.findall(r"'([^']+)'", matches.group(1))
                info['config_sections'] = sections
                self.config_sections.update(sections)
    
    def _extract_dependencies(self, content: str, info: Dict):
        """Витягує інформацію про залежності."""
        # Шукаємо специфічні імпорти
        external_deps = set()
        internal_deps = set()
        
        # Список стандартних модулів
        std_modules = {
            'os', 'sys', 'json', 'yaml', 'logging', 'pathlib', 'typing',
            'datetime', 'time', 're', 'inspect', 'ast', 'importlib',
            'dataclasses', 'enum', 'collections', 'itertools', 'functools'
        }
        
        # Простий парсинг імпортів
        for line in content.split('\n'):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                parts = line.split()
                if len(parts) >= 2:
                    module = parts[1].split('.')[0]
                    if module not in std_modules:
                        if module.startswith('p_'):
                            internal_deps.add(module)
                        else:
                            external_deps.add(module)
        
        info['external_dependencies'] = list(external_deps)
        info['internal_dependencies'] = list(internal_deps)
        info['dependencies'] = list(external_deps.union(internal_deps))
        
        # Додаємо до загальних залежностей
        self.dependencies[info['name']] = external_deps
    
    def _extract_api_info(self, content: str, info: Dict):
        """Визначає API модуля."""
        # Функції, які можуть використовуватися зовні
        api_functions = ['initialize', 'prepare_config_models', 'check_dependencies', 'stop']
        
        for func in api_functions:
            if f"def {func}(" in content:
                # Знаходимо опис функції
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if f"def {func}(" in line:
                        # Шукаємо докстрінг
                        docstring = ''
                        for j in range(i+1, min(i+10, len(lines))):
                            if '"""' in lines[j] or "'''" in lines[j]:
                                # Початок докстрінга
                                docstring = lines[j].strip(" \"'")
                                break
                        
                        info['api'].append({
                            'function': func,
                            'description': docstring[:100] + '...' if len(docstring) > 100 else docstring,
                            'required': func == 'initialize'
                        })
                        break
    
    def scan_all_modules(self):
        """Сканує всі модулі проекту."""
        self.logger.info("🔍 Сканування всіх модулів проекту...")
        
        for py_file in self.kod_path.glob("**/p_*.py"):
            if py_file.is_file():
                info = self.analyze_module(py_file)
                self.modules_info[info['name']] = info
        
        self.logger.info(f"✅ Проаналізовано {len(self.modules_info)} модулів")
    
    def collect_system_info(self):
        """Збирає інформацію про систему з app_context."""
        self.logger.info("📊 Збір інформації про систему...")
        
        # Компоненти системи
        for key, value in self.app_context.items():
            if not key.startswith('_'):
                self.components[key] = {
                    'type': type(value).__name__,
                    'module': getattr(value, '__module__', 'unknown')
                }
        
        # Конфігурація
        if 'config' in self.app_context:
            config = self.app_context['config']
            if hasattr(config, '__dict__'):
                self.config_sections = set(config.__dict__.keys())
    
    def generate_module_summary(self) -> str:
        """Генерує короткий звіт по модулях."""
        summary = []
        summary.append("=" * 100)
        summary.append("📦 МОДУЛЬНА СТРУКТУРА ПРОЄКТУ")
        summary.append("=" * 100)
        summary.append(f"Загальна кількість модулів: {len(self.modules_info)}")
        summary.append(f"Секції конфігурації: {len(self.config_sections)}")
        summary.append(f"Компонентів у системі: {len(self.components)}")
        summary.append("")
        
        # Групуємо модулі за категоріями
        categories = {
            'core': [],      # 000-099
            'config': [],    # 010-029
            'services': [],  # 050-099
            'utils': [],     # 100-199
            'features': [],  # 200-899
            'info': []       # 900+
        }
        
        for module_name, info in self.modules_info.items():
            prefix = info.get('prefix', 999)
            
            if prefix < 10:
                categories['core'].append(info)
            elif prefix < 30:
                categories['config'].append(info)
            elif prefix < 100:
                categories['services'].append(info)
            elif prefix < 200:
                categories['utils'].append(info)
            elif prefix < 900:
                categories['features'].append(info)
            else:
                categories['info'].append(info)
        
        # Виводимо категорії
        for category, modules in categories.items():
            if modules:
                summary.append(f"\n{'='*50}")
                summary.append(f"🏷️  КАТЕГОРІЯ: {category.upper()} ({len(modules)} модулів)")
                summary.append('='*50)
                
                for module in sorted(modules, key=lambda x: x.get('prefix', 999)):
                    name = module['name']
                    desc = module.get('description', '')
                    deps = len(module.get('external_dependencies', []))
                    
                    line = f"  [{module.get('prefix', '???')}] {name:30}"
                    if desc:
                        line += f" - {desc[:50]}..."
                    line += f" | deps: {deps}"
                    
                    summary.append(line)
        
        return "\n".join(summary)
    
    def generate_detailed_report(self) -> str:
        """Генерує детальний звіт по кожному модулю."""
        report = []
        
        report.append("=" * 120)
        report.append("🔍 ДЕТАЛЬНА ІНФОРМАЦІЯ ПО КОЖНОМУ МОДУЛЮ")
        report.append("=" * 120)
        report.append("")
        
        # Сортуємо модулі за префіксом
        sorted_modules = sorted(self.modules_info.values(), 
                              key=lambda x: x.get('prefix', 999))
        
        for module in sorted_modules:
            report.append(f"\n{'='*80}")
            report.append(f"📄 МОДУЛЬ: {module['name']}")
            report.append(f"📁 Файл: {module['file']}")
            if 'prefix' in module:
                report.append(f"🔢 Префікс: {module['prefix']}")
            report.append(f"📏 Розмір: {module.get('line_count', '?')} рядків")
            report.append(f"{'='*80}")
            
            # Опис
            if module.get('description'):
                report.append(f"\n📝 ОПИС:")
                report.append(f"  {module['description']}")
            
            # API
            if module.get('api'):
                report.append(f"\n🔌 API МОДУЛЯ:")
                for api in module['api']:
                    req = "🔵 Обов'язкова" if api.get('required') else "🟢 Опційна"
                    report.append(f"  • {api['function']}() - {req}")
                    if api.get('description'):
                        report.append(f"    {api['description'][:80]}...")
            
            # Функції
            if module.get('functions'):
                report.append(f"\n⚙️  ФУНКЦІЇ ({len(module['functions'])}):")
                for func in module['functions'][:10]:  # Обмежуємо для читабельності
                    if func['name'] not in ['initialize', 'prepare_config_models', 'check_dependencies', 'stop']:
                        report.append(f"  • {func['name']}()")
                        if func['docstring']:
                            report.append(f"    {func['docstring'][:60]}...")
            
            # Класи
            if module.get('classes'):
                report.append(f"\n🏛️  КЛАСИ ({len(module['classes'])}):")
                for cls in module['classes'][:5]:
                    report.append(f"  • {cls['name']}")
                    if cls['docstring']:
                        report.append(f"    {cls['docstring'][:60]}...")
            
            # Залежності
            if module.get('external_dependencies'):
                report.append(f"\n📦 ЗОВНІШНІ ЗАЛЕЖНОСТІ:")
                for dep in sorted(module['external_dependencies']):
                    report.append(f"  • {dep}")
            
            if module.get('internal_dependencies'):
                report.append(f"\n🔗 ВНУТРІШНІ ЗАЛЕЖНОСТІ:")
                for dep in sorted(module['internal_dependencies']):
                    report.append(f"  • {dep}")
            
            # Конфігурація
            if module.get('has_default_config'):
                report.append(f"\n⚙️  КОНФІГУРАЦІЯ: Має DEFAULT_CONFIG")
            
            if module.get('config_sections'):
                report.append(f"📋 СЕКЦІЇ КОНФІГУРАЦІЇ: {', '.join(module['config_sections'])}")
        
        return "\n".join(report)
    
    def generate_architecture_doc(self) -> str:
        """Генерує документ архітектури."""
        doc = []
        
        doc.append("# 🏗️ АРХІТЕКТУРА ПРОЄКТУ")
        doc.append(f"*Автоматично згенеровано: {datetime.now().isoformat()}*")
        doc.append("")
        
        # Загальна інформація
        doc.append("## 📊 ЗАГАЛЬНА ІНФОРМАЦІЯ")
        doc.append("")
        doc.append(f"- **Загальна кількість модулів**: {len(self.modules_info)}")
        doc.append(f"- **Секції конфігурації**: {len(self.config_sections)}")
        doc.append(f"- **Активних компонентів**: {len(self.components)}")
        doc.append(f"- **Коренева папка**: {self.project_root}")
        doc.append("")
        
        # Схема роботи
        doc.append("## 🔄 СХЕМА РОБОТИ СИСТЕМИ")
        doc.append("""
```mermaid
graph TD
    A[main.py] --> B[p_000_loader.py]
    B --> C[Сканування модулів]
    C --> D[Збір конфігурацій]
    D --> E[Валідація конфігурації]
    E --> F[Перевірка залежностей]
    F --> G[Ініціалізація модулів]
    G --> H[Запуск системи]
    H --> I[Робота з діями]
    I --> J[Обробка подій]
    J --> K[GUI інтерфейси]
""")
    # Ключові компоненти
    doc.append("## 🧩 КЛЮЧОВІ КОМПОНЕНТИ СИСТЕМИ")
    doc.append("")
    
    component_categories = {
        'Завантаження': ['p_000_loader.py'],
        'Конфігурація': ['p_010_config_collector.py', 'p_020_config_validator.py'],
        'Сервіси': ['p_050_universal_deps_checker.py', 'p_060_error_handler.py', 
                   'p_075_events.py', 'p_080_registry.py', 'p_090_gui_manager.py', 
                   'p_100_logger.py'],
        'Функціонал': ['p_300_test_actions.py', 'p_310_tts_config.py', 
                     'p_312_tts_engine.py', 'p_350_tts_gradio.py'],
        'Тестування': ['p_400_test_integration.py'],
        'Інформація': ['p_900_project_info.py']
    }
    
    for category, modules in component_categories.items():
        doc.append(f"### {category}")
        for module in modules:
            if module in self.modules_info:
                info = self.modules_info[module]
                doc.append(f"- **{module}**")
                if info.get('description'):
                    doc.append(f"  - {info['description']}")
                doc.append(f"  - Префікс: {info.get('prefix', 'N/A')}")
                doc.append(f"  - Залежності: {len(info.get('external_dependencies', []))}")
                doc.append("")
    
    # Залежності між модулями
    doc.append("## 🔗 ЗАЛЕЖНОСТІ МІЖ МОДУЛЯМИ")
    doc.append("")
    
    for module_name, info in sorted(self.modules_info.items(), 
                                   key=lambda x: x[1].get('prefix', 999)):
        deps = info.get('internal_dependencies', [])
        if deps:
            doc.append(f"- **{module_name}** залежить від: {', '.join(deps)}")
    
    # Конфігурація
    doc.append("## ⚙️ СИСТЕМА КОНФІГУРАЦІЇ")
    doc.append("""
Система конфігурації працює за принципом пріоритетів:
config.yaml у корені - найвищий пріоритет (користувацькі налаштування)
config/*.yaml - середній пріоритет (згенеровані модульні конфіги)
DEFAULT_CONFIG у модулях - низький пріоритет
Кожен модуль може мати:
prepare_config_models() - повертає моделі Pydantic для конфігурації
DEFAULT_CONFIG - словник зі значеннями за замовчуванням
check_dependencies() - перевірка залежностей
initialize(app_context) - ініціалізація модуля
stop(app_context) - очищення ресурсів
""")
    # Правила розробки
    doc.append("## 📝 ПРАВИЛА РОЗРОБКИ ДЛЯ ШІ")
    doc.append("""
Назви файлів: p_NNN_name.py де NNN - тризначний префікс

Префікси:

000-099: Ядро системи

010-029: Конфігурація

050-099: Базові сервіси

100-199: Утиліти

200-899: Бізнес-логіка

900+: Інформація та документація

Обов'язкові функції:

initialize(app_context) - ініціалізація

Опційно: prepare_config_models(), check_dependencies(), stop()

Комунікація: Через app_context, не через прямі імпорти

Конфігурація: Використовувати Pydantic моделі

Документація: Додавати docstrings для всіх функцій та класів
""")
    # Швидкий старт
    doc.append("## 🚀 ШВИДКИЙ СТАРТ ДЛЯ НОВОГО ШІ")
    doc.append("""
Щоб додати новий функціонал:

Створіть файл у kod/ з наступним вільним префіксом

Додайте обов'язкову функцію initialize(app_context)

Опишіть конфігурацію через prepare_config_models() (опційно)

Реєструйте дії через app_context['action_registry']

Використовуйте існуючі сервіси з app_context

Приклад простого модуля:
# p_250_example.py
from typing import Dict, Any
from pydantic import BaseModel

class ExampleConfig(BaseModel):
    enabled: bool = True
    message: str = "Приклад"

def prepare_config_models():
    return {'example': ExampleConfig}

DEFAULT_CONFIG = {
    'example': {
        'enabled': True,
        'message': 'Приклад'
    }
}

def initialize(app_context: Dict[str, Any]):
    config = app_context.get('config')
    logger = app_context.get('logger')
    
    if logger:
        logger.info("Прикладний модуль ініціалізовано")
    
    return {"status": "ready"}
""")
    return "\n".join(doc)

def generate_json_report(self) -> Dict[str, Any]:
    """Генерує JSON звіт для програмного використання."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'project_root': str(self.project_root),
        'modules': self.modules_info,
        'dependencies': {k: list(v) for k, v in self.dependencies.items()},
        'config_sections': list(self.config_sections),
        'components': self.components,
        'summary': {
            'total_modules': len(self.modules_info),
            'total_config_sections': len(self.config_sections),
            'total_components': len(self.components),
            'modules_by_prefix': {}
        }
    }
    
    # Групуємо модулі за префіксом
    for module in self.modules_info.values():
        prefix_range = f"{(module.get('prefix', 999) // 100) * 100:03d}-{((module.get('prefix', 999) // 100) * 100 + 99):03d}"
        report['summary']['modules_by_prefix'][prefix_range] = \
            report['summary']['modules_by_prefix'].get(prefix_range, 0) + 1
    
    return report

def save_all_reports(self):
    """Зберігає всі звіти у файли."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Короткий звіт
    summary = self.generate_module_summary()
    summary_path = self.output_dir / f"project_summary_{timestamp}.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary)
    
    # 2. Детальний звіт
    detailed = self.generate_detailed_report()
    detailed_path = self.output_dir / f"project_details_{timestamp}.txt"
    with open(detailed_path, 'w', encoding='utf-8') as f:
        f.write(detailed)
    
    # 3. Документ архітектури
    architecture = self.generate_architecture_doc()
    arch_path = self.output_dir / f"architecture_{timestamp}.md"
    with open(arch_path, 'w', encoding='utf-8') as f:
        f.write(architecture)
    
    # 4. JSON звіт
    json_report = self.generate_json_report()
    json_path = self.output_dir / f"project_data_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)
    
    # 5. Постійні файли (остання версія)
    permanent_files = {
        'PROJECT_SUMMARY.txt': summary,
        'ARCHITECTURE.md': architecture,
        'project_info.json': json.dumps(json_report, indent=2, ensure_ascii=False)
    }
    
    for filename, content in permanent_files.items():
        path = self.project_root / filename
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    self.logger.info(f"📄 Збережено звіти у: {self.output_dir}/")
    self.logger.info(f"📄 Постійні файли: PROJECT_SUMMARY.txt, ARCHITECTURE.md, project_info.json")

def run(self):
    """Запускає повний аналіз проекту."""
    self.logger.info("🚀 Запуск аналізу проекту...")
    
    # Скануємо модулі
    self.scan_all_modules()
    
    # Збираємо системну інформацію
    self.collect_system_info()
    
    # Зберігаємо звіти
    self.save_all_reports()
    
    # Виводимо короткий звіт у консоль
    summary = self.generate_module_summary()
    print("\n" + "=" * 100)
    print("📊 ЗВЕДЕННЯ ПРОЄКТУ")
    print("=" * 100)
    print(summary.split('\n', 10)[10])  # Перші 10 рядків
    
    self.logger.info("✅ Аналіз проекту завершено")
def prepare_config_models():
"""Повертає модель конфігурації для модуля інформації про проект."""
return {}

def initialize(app_context: Dict[str, Any]):
"""Ініціалізація модуля інформації про проект."""
logger = app_context.get('logger', logging.getLogger("ProjectInfo"))
logger.info("📊 Ініціалізація модуля інформації про проект...")
# Створюємо збирача
collector = ProjectInfoCollector(app_context)

# Запускаємо аналіз
collector.run()

# Зберігаємо в контексті
app_context['project_info'] = collector

logger.info("✅ Інформація про проект зібрана та збережена")

return collector
def stop(app_context: Dict[str, Any]) -> None:
"""Зупинка модуля інформації про проект."""
if 'project_info' in app_context:
del app_context['project_info']
logger = app_context.get('logger')
if logger:
    logger.info("Модуль інформації про проект зупинено")

## 🎯 **Що робить цей модуль:**

1. **📊 Автоматичний аналіз** - сканує всі модулі проекту
2. **🔍 Детальна інформація** - збирає дані про кожен модуль
3. **📄 Генерація звітів** - створює кілька форматів документації:
   - `PROJECT_SUMMARY.txt` - короткий звіт
   - `ARCHITECTURE.md` - документ архітектури з Mermaid діаграмою
   - `project_info.json` - структуровані дані для програмного використання
   - Детальні звіти у папці `project_info/` з timestamp

4. **🧩 Категоризація** - групує модулі за типами
5. **🔗 Аналіз залежностей** - показує зв'язки між модулями
6. **📝 Інструкції для ШІ** - містить правила розробки та приклади

## 🚀 **Як користуватися:**

Після запуску системи, модуль автоматично:
1. Проаналізує всі файли в `kod/`
2. Згенерує звіти у різних форматах
3. Створить постійні файли у корені проекту

**Для ШІ/нового розробника** достатньо прочитати:
- `ARCHITECTURE.md` - повна архітектура
- `PROJECT_SUMMARY.txt` - короткий огляд
- `project_info.json` - структуровані дані

Тепер будь-який ШІ зможе швидко зрозуміти структуру вашого проекту та доповнювати його! 🎉