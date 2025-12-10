# p_900_project_info.py
"""
Модуль для документування проекту.
Збирає інформацію про всі модулі, конфігурації, залежності та взаємодії.
Створює повну документацію проекту для швидкого розуміння архітектури.
"""

import os
import ast
from pathlib import Path
from typing import Dict, Any, Set
import logging
import json
from datetime import datetime


class ProjectInfoCollector:
    """Збирач інформації про весь проект."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("ProjectInfo")
        self.project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.kod_path = self.project_root / "kod"
        self.output_dir = self.project_root / "project_info"
        self.output_dir.mkdir(exist_ok=True)
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
                
                if info['name'].startswith('p_') and len(info['name']) > 3:
                    try:
                        prefix = int(info['name'][2:5])
                        info['prefix'] = prefix
                    except:
                        pass
                
                tree = ast.parse(content, filename=filepath.name)
                info['docstring'] = ast.get_docstring(tree) or ''
                if info['docstring']:
                    info['description'] = info['docstring'].split('\n')[0]
                
                self._extract_ast_info(tree, info, filepath)
                self._extract_config_info(content, info)
                self._extract_dependencies(content, info)
                self._extract_api_info(content, info)
                
        except Exception as e:
            self.logger.warning(f"Помилка аналізу {filepath.name}: {e}")
            info['error'] = str(e)
        
        return info
    
    def _extract_ast_info(self, tree: ast.AST, info: Dict, filepath: Path):
        """Витягує інформацію з AST дерева."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'docstring': ast.get_docstring(node) or '',
                    'lineno': node.lineno,
                    'args': [arg.arg for arg in node.args.args],
                    'returns': 'bool' if node.returns else 'None'
                }
                
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
                
                if node.name in ['initialize', 'prepare_config_models']:
                    info['api'].append({
                        'function': node.name,
                        'description': ast.get_docstring(node) or '',
                        'type': 'required' if node.name == 'initialize' else 'optional'
                    })
            
            elif isinstance(node, ast.ClassDef):
                class_info = {
                    'name': node.name,
                    'docstring': ast.get_docstring(node) or '',
                    'lineno': node.lineno,
                    'bases': [base.id if isinstance(base, ast.Name) else str(base) 
                             for base in node.bases]
                }
                info['classes'].append(class_info)
            
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    info['imports'].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    info['imports'].append(f"{module}.{alias.name}" if module else alias.name)
    
    def _extract_config_info(self, content: str, info: Dict):
        """Витягує інформацію про конфігурацію."""
        if 'DEFAULT_CONFIG' in content:
            info['has_default_config'] = True
        
        if 'prepare_config_models' in content:
            info['has_config_models'] = True
            import re
            pattern = r"return\s+{([^}]+)}"
            matches = re.search(pattern, content, re.DOTALL)
            if matches:
                sections = re.findall(r"'([^']+)'", matches.group(1))
                info['config_sections'] = sections
                self.config_sections.update(sections)
    
    def _extract_dependencies(self, content: str, info: Dict):
        """Витягує інформацію про залежності."""
        external_deps = set()
        internal_deps = set()
        
        std_modules = {
            'os', 'sys', 'json', 'yaml', 'logging', 'pathlib', 'typing',
            'datetime', 'time', 're', 'inspect', 'ast', 'importlib',
            'dataclasses', 'enum', 'collections', 'itertools', 'functools'
        }
        
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
        self.dependencies[info['name']] = external_deps
    
    def _extract_api_info(self, content: str, info: Dict):
        """Визначає API модуля."""
        api_functions = ['initialize', 'prepare_config_models', 'check_dependencies', 'stop']
        
        for func in api_functions:
            if f"def {func}(" in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if f"def {func}(" in line:
                        docstring = ''
                        for j in range(i+1, min(i+10, len(lines))):
                            if '"""' in lines[j] or "'''" in lines[j]:
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
        for key, value in self.app_context.items():
            if not key.startswith('_'):
                self.components[key] = {
                    'type': type(value).__name__,
                    'module': getattr(value, '__module__', 'unknown')
                }
        
        if 'config' in self.app_context:
            config = self.app_context['config']
            if hasattr(config, '__dict__'):
                self.config_sections = set(config.__dict__.keys())
    
    def generate_module_summary(self) -> str:
        """Генерує короткий звіт по модулях."""
        summary = ["=" * 100, "📦 МОДУЛЬНА СТРУКТУРА ПРОЄКТУ", "=" * 100]
        summary.append(f"Загальна кількість модулів: {len(self.modules_info)}")
        summary.append(f"Секції конфігурації: {len(self.config_sections)}")
        summary.append(f"Компонентів у системі: {len(self.components)}\n")
        
        categories = {
            'core': [], 'config': [], 'services': [], 
            'utils': [], 'features': [], 'info': []
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
        """Генерує детальний звіт."""
        report = ["=" * 120, "🔍 ДЕТАЛЬНА ІНФОРМАЦІЯ ПО КОЖНОМУ МОДУЛЮ", "=" * 120, ""]
        sorted_modules = sorted(self.modules_info.values(), key=lambda x: x.get('prefix', 999))
        
        for module in sorted_modules:
            report.append(f"\n{'='*80}")
            report.append(f"📄 МОДУЛЬ: {module['name']}")
            report.append(f"📁 Файл: {module['file']}")
            if 'prefix' in module:
                report.append(f"🔢 Префікс: {module['prefix']}")
            report.append(f"📏 Розмір: {module.get('line_count', '?')} рядків")
            report.append(f"{'='*80}")
            
            if module.get('description'):
                report.append(f"\n📝 ОПИС:\n  {module['description']}")
            
            if module.get('api'):
                report.append(f"\n🔌 API МОДУЛЯ:")
                for api in module['api']:
                    req = "🔵 Обов'язкова" if api.get('required') else "🟢 Опційна"
                    report.append(f"  • {api['function']}() - {req}")
                    if api.get('description'):
                        report.append(f"    {api['description'][:80]}...")
            
            if module.get('functions'):
                report.append(f"\n⚙️  ФУНКЦІЇ ({len(module['functions'])}):")
                for func in module['functions'][:10]:
                    if func['name'] not in ['initialize', 'prepare_config_models', 'check_dependencies', 'stop']:
                        report.append(f"  • {func['name']}()")
                        if func['docstring']:
                            report.append(f"    {func['docstring'][:60]}...")
            
            if module.get('classes'):
                report.append(f"\n🏛️  КЛАСИ ({len(module['classes'])}):")
                for cls in module['classes'][:5]:
                    report.append(f"  • {cls['name']}")
                    if cls['docstring']:
                        report.append(f"    {cls['docstring'][:60]}...")
            
            if module.get('external_dependencies'):
                report.append(f"\n📦 ЗОВНІШНІ ЗАЛЕЖНОСТІ:")
                for dep in sorted(module['external_dependencies']):
                    report.append(f"  • {dep}")
            
            if module.get('internal_dependencies'):
                report.append(f"\n🔗 ВНУТРІШНІ ЗАЛЕЖНОСТІ:")
                for dep in sorted(module['internal_dependencies']):
                    report.append(f"  • {dep}")
            
            if module.get('has_default_config'):
                report.append(f"\n⚙️  КОНФІГУРАЦІЯ: Має DEFAULT_CONFIG")
            if module.get('config_sections'):
                report.append(f"📋 СЕКЦІЇ КОНФІГУРАЦІЇ: {', '.join(module['config_sections'])}")
        
        return "\n".join(report)
    
    def generate_full_documentation(self) -> str:
        """Генерує повну документацію проекту (об'єднує все в один файл)."""
        doc = [
            "# 🏗️ ПОВНА ДОКУМЕНТАЦІЯ ПРОЄКТУ",
            f"*Автоматично згенеровано: {datetime.now().isoformat()}*",
            f"*Оновлюється автоматично при кожному запуску системи*\n",
            "=" * 100,
            "## 📊 ЗАГАЛЬНА ІНФОРМАЦІЯ",
            "=" * 100,
            f"- **Загальна кількість модулів**: {len(self.modules_info)}",
            f"- **Секції конфігурації**: {len(self.config_sections)}",
            f"- **Активних компонентів**: {len(self.components)}",
            f"- **Коренева папка**: {self.project_root}\n"
        ]
        
        # Додаємо короткий звіт по категоріям
        categories = {
            'core': [], 'config': [], 'services': [], 
            'utils': [], 'features': [], 'info': []
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
        
        for category, modules in categories.items():
            if modules:
                doc.append(f"\n### 📦 {category.upper()} ({len(modules)} модулів)")
                for module in sorted(modules, key=lambda x: x.get('prefix', 999)):
                    name = module['name']
                    desc = module.get('description', 'Без опису')
                    doc.append(f"- `[{module.get('prefix', '???')}]` **{name}** - {desc[:80]}")
        
        # Схема роботи
        doc.extend([
            "\n" + "=" * 100,
            "## 🔄 СХЕМА РОБОТИ СИСТЕМИ",
            "=" * 100,
            "```mermaid",
            "graph TD",
            "    A[main.py] --> B[p_000_loader.py]",
            "    B --> C[Сканування модулів]",
            "    C --> D[Збір конфігурацій]",
            "    D --> E[Валідація конфігурації]",
            "    E --> F[Перевірка залежностей]",
            "    F --> G[Ініціалізація модулів]",
            "    G --> H[Запуск системи]",
            "```\n"
        ])
        
        # Залежності
        doc.extend([
            "=" * 100,
            "## 🔗 ЗАЛЕЖНОСТІ МІЖ МОДУЛЯМИ",
            "=" * 100
        ])
        
        for module_name, info in sorted(self.modules_info.items(), key=lambda x: x[1].get('prefix', 999)):
            deps = info.get('internal_dependencies', [])
            if deps:
                doc.append(f"- **{module_name}** ← {', '.join(deps)}")
        
        # Правила розробки
        doc.extend([
            "\n" + "=" * 100,
            "## 📝 ПРАВИЛА РОЗРОБКИ ДЛЯ ШІ",
            "=" * 100,
            "\n**Назви файлів:** `p_NNN_name.py` де NNN - тризначний префікс\n",
            "**Префікси:**",
            "- `000-009`: Ядро системи (loader)",
            "- `010-029`: Конфігурація",
            "- `050-099`: Базові сервіси",
            "- `100-199`: Утиліти",
            "- `200-899`: Бізнес-логіка та функції",
            "- `900+`: Інформація та документація\n",
            "**Обов'язкові функції:**",
            "- `initialize(app_context)` - ОБОВ'ЯЗКОВА, ініціалізація модуля",
            "- `prepare_config_models()` - опційно, для конфігурації",
            "- `check_dependencies()` - опційно, перевірка залежностей",
            "- `stop(app_context)` - опційно, очищення ресурсів\n",
            "**Комунікація:** Тільки через `app_context`, НЕ через прямі імпорти!\n",
            "**Приклад нового модуля:**",
            "```python",
            "# p_250_my_feature.py",
            "from typing import Dict, Any",
            "from pydantic import BaseModel\n",
            "class MyConfig(BaseModel):",
            "    enabled: bool = True\n",
            "def prepare_config_models():",
            "    return {'my_feature': MyConfig}\n",
            "DEFAULT_CONFIG = {'my_feature': {'enabled': True}}\n",
            "def initialize(app_context: Dict[str, Any]):",
            "    logger = app_context.get('logger')",
            "    logger.info('Мій модуль запущено!')",
            "    return {'status': 'ready'}",
            "```\n"
        ])
        
        return "\n".join(doc)
    
    def generate_json_report(self) -> Dict[str, Any]:
        """Генерує JSON звіт."""
        return {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'modules': self.modules_info,
            'dependencies': {k: list(v) for k, v in self.dependencies.items()},
            'config_sections': list(self.config_sections),
            'components': self.components,
            'summary': {
                'total_modules': len(self.modules_info),
                'total_config_sections': len(self.config_sections),
                'total_components': len(self.components)
            }
        }
    
    def save_all_reports(self):
        """Зберігає всі звіти у файли."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Генеруємо звіти
        full_doc = self.generate_full_documentation()
        detailed = self.generate_detailed_report()
        
        # Зберігаємо у папку project_info з timestamp (архів)
        archive_files = {
            'full_documentation': (self.output_dir / f"documentation_{timestamp}.md", full_doc),
            'detailed': (self.output_dir / f"detailed_{timestamp}.txt", detailed)
        }
        
        for name, (path, content) in archive_files.items():
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Зберігаємо у корінь проекту (постійні файли, які завжди оновлюються)
        main_doc_path = self.project_root / "PROJECT_DOCUMENTATION.md"
        with open(main_doc_path, 'w', encoding='utf-8') as f:
            f.write(full_doc)
        
        self.logger.info("📄 Документація оновлена:")
        self.logger.info(f"   └─ {main_doc_path.name} (головний файл)")
        self.logger.info(f"   └─ Архів: {self.output_dir}/documentation_{timestamp}.md")
    
    def run(self):
        """Запускає повний аналіз проекту."""
        self.logger.info("🚀 Аналіз проекту запущено...")
        self.scan_all_modules()
        self.collect_system_info()
        self.save_all_reports()
        self.logger.info("✅ Документація оновлена! Читай: PROJECT_DOCUMENTATION.md")


def prepare_config_models():
    """Повертає модель конфігурації."""
    return {}


def initialize(app_context: Dict[str, Any]):
    """Ініціалізація модуля інформації про проект."""
    logger = app_context.get('logger', logging.getLogger("ProjectInfo"))
    logger.info("📊 Ініціалізація модуля інформації про проект...")
    collector = ProjectInfoCollector(app_context)
    collector.run()
    app_context['project_info'] = collector
    logger.info("✅ Інформація про проект зібрана та збережена")
    return collector


def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка модуля."""
    if 'project_info' in app_context:
        del app_context['project_info']
    logger = app_context.get('logger')
    if logger:
        logger.info("Модуль інформації про проект зупинено")
