# p_001_config_collector.py
"""
Модуль збирання конфігурацій.
Збирає DEFAULT_CONFIG з Python файлів БЕЗ їх імпорту, через аналіз коду.
"""

import os
import yaml
import ast
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging
from dataclasses import dataclass
import sys

@dataclass
class ConfigSource:
    """Інформація про джерело конфігурації."""
    key: str
    value: Any
    source: str
    priority: int

class ConfigCollector:
    """Збирач конфігурацій."""
        # В клас ConfigCollector додати:
    def create_main_config(self):
        """Створити основний config.yaml з базовими налаштуваннями."""
        base_config = {
            'app': {
                'name': 'Мій Модульний Проєкт',
                'version': '1.0.0',
                'mode': 'DEBUG'
            },
            'note': 'Цей файл має найвищий пріоритет. Редагуйте його для налаштувань.'
        }
        
        with open(self.config_filepath, 'w', encoding='utf-8') as f:
            yaml.dump(base_config, f, 
                      default_flow_style=False, 
                      allow_unicode=True, 
                      indent=2)
        
        self.logger.info(f"Створено основний конфігураційний файл: {self.config_filepath}")
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("ConfigCollector")
        
        # ⭐ СПОЧАТКУ ІНІЦІАЛІЗУЄМО ШЛЯХИ
        self.project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.kod_path = self.project_root / "kod"
        self.config_filepath = self.project_root / "config.yaml"
        self.config_dir = self.project_root / "config"
        
        # ⭐ ПОТІМ ВИКОРИСТОВУЄМО ЇХ
        self.config_dir.mkdir(exist_ok=True)
        
        # Створюємо основний config.yaml, якщо не існує
        if not self.config_filepath.exists():
            self.create_main_config()
        
        # Зберігаємо джерела конфігурації
        self.config_sources: List[ConfigSource] = []
    
    def extract_default_config_from_file(self, filepath: Path) -> Tuple[str, Dict[str, Any]]:
        """
        Вилучає DEFAULT_CONFIG з файлу без його імпорту.
        Використовує ast для аналізу Python коду.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Парсимо AST
            tree = ast.parse(content)
            
            # Шукаємо змінну DEFAULT_CONFIG
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == 'DEFAULT_CONFIG':
                            # Знайшли DEFAULT_CONFIG
                            try:
                                # Конвертуємо AST назад у Python об'єкт
                                # Створюємо тимчасовий контекст для виконання
                                local_vars = {}
                                global_vars = {}
                                
                                # Виконуємо присвоєння в безпечному середовищі
                                code = compile(ast.Module(body=[node], type_ignores=[]), 
                                             filename=filepath.name, mode='exec')
                                exec(code, global_vars, local_vars)
                                
                                # Отримуємо значення DEFAULT_CONFIG
                                if 'DEFAULT_CONFIG' in local_vars:
                                    config = local_vars['DEFAULT_CONFIG']
                                    if isinstance(config, dict):
                                        module_name = filepath.stem
                                        return module_name, config
                                
                            except Exception as e:
                                self.logger.debug(f"Не вдалося витягти DEFAULT_CONFIG з {filepath.name}: {e}")
                                return None, {}
        
        except Exception as e:
            self.logger.warning(f"Помилка читання {filepath}: {e}")
        
        return None, {}
    
    def extract_prepare_config_models_from_file(self, filepath: Path) -> Dict[str, Any]:
        """
        Вилучає prepare_config_models з файлу без імпорту.
        Повертає моделі конфігурації.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Шукаємо функцію prepare_config_models
            # Спрощений пошук за допомогою регулярних виразів
            import re
            
            # Пошук моделей у вигляді {'section': Model}
            pattern = r"def\s+prepare_config_models\s*\([^)]*\)\s*:.*?return\s+({.*?})"
            matches = re.search(pattern, content, re.DOTALL)
            
            if matches:
                # Спробуємо витягнути словник
                dict_str = matches.group(1)
                
                # Спрощений парсинг (можна було б використовувати ast знову)
                # Але для початку будемо вважати, що це простий dict з іменами класів
                
                # Шукаємо імена класів Pydantic у файлі
                class_pattern = r"class\s+(\w+Config)\s*\([^)]*BaseModel[^)]*\)"
                class_matches = re.findall(class_pattern, content)
                
                if class_matches:
                    # Повертаємо словник з іменами класів
                    # Фактичні класи будуть завантажені пізніше при валідації
                    result = {}
                    for class_name in class_matches:
                        # Використовуємо ім'я файлу як ключ
                        key = filepath.stem.replace('p_', '').replace('_', ' ')
                        result[key] = f"{filepath.stem}.{class_name}"
                    
                    return result
            
        except Exception as e:
            self.logger.debug(f"Не вдалося витягти prepare_config_models з {filepath.name}: {e}")
        
        return {}
    
    def collect_default_configs_from_files(self) -> Dict[str, Any]:
        """Збирає всі DEFAULT_CONFIG з файлів без імпорту."""
        self.logger.info("📦 Збір DEFAULT_CONFIG з файлів модулів...")
        
        all_configs = {}
        
        # Скануємо всі Python файли в kod/
        for py_file in self.kod_path.glob("**/p_*.py"):
            if py_file.name.startswith('p_'):
                module_name = py_file.stem
                
                # Вилучаємо DEFAULT_CONFIG
                mod_name, defaults = self.extract_default_config_from_file(py_file)
                
                if defaults and isinstance(defaults, dict):
                    self.logger.debug(f"  → {module_name}: знайдено конфігурацію")
                    
                    # Додаємо до загального словника
                    for key, value in defaults.items():
                        if key not in all_configs:
                            all_configs[key] = {}
                        
                        # Рекурсивно об'єднуємо
                        self._deep_merge(all_configs[key], value)
                    
                    # Записуємо джерела
                    for key_path, value in self._flatten_dict(defaults):
                        self.config_sources.append(ConfigSource(
                            key=key_path,
                            value=value,
                            source=f"module:{module_name}",
                            priority=1000  # Низький пріоритет
                        ))
        
        return all_configs
    
    def generate_config_files(self, default_configs: Dict[str, Any]):
        """Генерує окремі конфігураційні файли для кожного модуля."""
        self.logger.info("🔧 Генерація конфігураційних файлів...")
        
        # Скануємо всі Python файли
        for py_file in self.kod_path.glob("**/p_*.py"):
            if not py_file.name.startswith('p_'):
                continue
            
            module_name = py_file.stem
            
            # Вилучаємо DEFAULT_CONFIG
            mod_name, defaults = self.extract_default_config_from_file(py_file)
            if not defaults or not isinstance(defaults, dict):
                continue
            
            # Отримуємо префікс з імені файлу
            try:
                prefix = int(module_name[2:5])
            except:
                prefix = 999
            
            # Формуємо назву файлу
            clean_name = module_name.replace('p_', '').replace('_', ' ').title().replace(' ', '')
            config_filename = f"{prefix:03d}_{clean_name}.yaml"
            config_path = self.config_dir / config_filename
            
            # Генеруємо файл, якщо не існує
            if not config_path.exists():
                try:
                    with open(config_path, 'w', encoding='utf-8') as f:
                        # Додаємо заголовок
                        f.write(f"# Конфігурація модуля: {module_name}\n")
                        f.write(f"# Автоматично згенеровано з {py_file.name}\n")
                        f.write("# Змінюйте цей файл для налаштувань\n")
                        f.write("---\n\n")
                        
                        # Записуємо конфігурацію
                        yaml.dump(defaults, f, 
                                  default_flow_style=False, 
                                  sort_keys=True, 
                                  allow_unicode=True, 
                                  indent=2)
                    
                    self.logger.info(f"  ✅ Згенеровано: {config_filename}")
                    
                    # Записуємо джерело
                    for key_path, value in self._flatten_dict(defaults):
                        self.config_sources.append(ConfigSource(
                            key=key_path,
                            value=value,
                            source=f"file:{config_filename}",
                            priority=500  # Середній пріоритет
                        ))
                        
                except Exception as e:
                    self.logger.error(f"  ❌ Помилка генерації {config_filename}: {e}")
    
    def load_config_files(self) -> Dict[str, Any]:
        """Завантажує всі конфігураційні файли."""
        self.logger.info("📥 Завантаження конфігураційних файлів...")
        
        merged_config = {}
        
        # 1. Завантаження автоматично згенерованих файлів
        if self.config_dir.exists():
            # Сортуємо файли за префіксом
            config_files = sorted(self.config_dir.glob("*.yaml"))
            
            for cfg_file in config_files:
                # Пропускаємо зведення
                if cfg_file.name.startswith('_'):
                    continue
                    
                try:
                    with open(cfg_file, 'r', encoding='utf-8') as f:
                        content = yaml.safe_load(f)
                    
                    if not isinstance(content, dict):
                        continue
                    
                    # Визначаємо пріоритет з назви файлу
                    priority = 400  # Середній пріоритет
                    if cfg_file.stem[:3].isdigit():
                        priority = 1000 - int(cfg_file.stem[:3])
                    
                    # Мерджимо конфігурацію
                    self._deep_merge(merged_config, content)
                    
                    # Записуємо джерела
                    for key_path, value in self._flatten_dict(content):
                        self.config_sources.append(ConfigSource(
                            key=key_path,
                            value=value,
                            source=f"file:{cfg_file.name}",
                            priority=priority
                        ))
                    
                    self.logger.debug(f"  📄 {cfg_file.name} (пріоритет: {priority})")
                    
                except Exception as e:
                    self.logger.warning(f"  ⚠️ Не вдалося завантажити {cfg_file.name}: {e}")
        
        # 2. Завантаження користувацького config.yaml (ВИСОКИЙ пріоритет)
        if self.config_filepath.exists():
            try:
                with open(self.config_filepath, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                
                if isinstance(user_config, dict):
                    self._deep_merge(merged_config, user_config)
                    
                    # Записуємо джерела з ВИСОКИМ пріоритетом
                    for key_path, value in self._flatten_dict(user_config):
                        self.config_sources.append(ConfigSource(
                            key=key_path,
                            value=value,
                            source="user:config.yaml",
                            priority=100  # Високий пріоритет
                        ))
                    
                    self.logger.info("  👤 Завантажено користувацький config.yaml")
                    
            except Exception as e:
                self.logger.error(f"  ❌ Помилка читання config.yaml: {e}")
        
        return merged_config
    
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Рекурсивно оновлює словник."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '.') -> List[Tuple[str, Any]]:
        """Робить словник плоским."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep))
            else:
                items.append((new_key, v))
        return items
    
    def get_final_config(self) -> Dict[str, Any]:
        """Отримує фінальну конфігурацію з урахуванням пріоритетів."""
        # 1. Збираємо дефолтні конфіги з файлів
        default_configs = self.collect_default_configs_from_files()
        
        # 2. Генеруємо конфігураційні файли
        self.generate_config_files(default_configs)
        
        # 3. Завантажуємо всі конфіги
        merged_config = self.load_config_files()
        
        # 4. Застосовуємо пріоритети
        final_config = {}
        
        # Сортуємо джерела за пріоритетом
        sorted_sources = sorted(self.config_sources, key=lambda x: x.priority)
        
        # Застосовуємо значення в порядку пріоритету
        for source in sorted_sources:
            self._set_nested_value(final_config, source.key.split('.'), source.value)
        
        # 5. Логуємо результат
        self.logger.info(f"📊 Зібрано конфігураційних ключів: {len(self.config_sources)}")
        self.logger.info(f"📁 Фінальних секцій: {len(final_config)}")
        
        return final_config
    
    def _set_nested_value(self, d: Dict, keys: List[str], value: Any) -> None:
        """Встановлює значення по вкладених ключах."""
        if len(keys) == 1:
            d[keys[0]] = value
        else:
            if keys[0] not in d:
                d[keys[0]] = {}
            self._set_nested_value(d[keys[0]], keys[1:], value)
    
    def save_config_summary(self, config: Dict[str, Any]):
        """Зберігає зведення конфігурації."""
        summary_path = self.config_dir / "_config_summary.yaml"
        
        try:
            summary = {
                'total_sources': len(self.config_sources),
                'total_sections': len(config),
                'config_sources': [
                    {
                        'key': s.key,
                        'source': s.source,
                        'priority': s.priority,
                        'value': s.value
                    }
                    for s in sorted(self.config_sources, key=lambda x: x.key)[:50]  # Обмежуємо для читабельності
                ],
                'sections': list(config.keys())
            }
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                yaml.dump(summary, f, 
                         default_flow_style=False, 
                         sort_keys=True, 
                         allow_unicode=True, 
                         indent=2)
            
            self.logger.info(f"📋 Зведення конфігурації збережено: {summary_path.name}")
            
        except Exception as e:
            self.logger.error(f"Помилка збереження зведення: {e}")

def prepare_config_models():
    """Повертає модель конфігурації для збирача конфігів."""
    return {}

def initialize(app_context: Dict[str, Any]):
    """Ініціалізація збирача конфігурацій."""
    logger = app_context.get('logger', logging.getLogger("ConfigCollector"))
    logger.info("🚀 Ініціалізація збирача конфігурацій...")
    
    # Створюємо збирача
    collector = ConfigCollector(app_context)
    
    # Збираємо конфігурацію
    final_config = collector.get_final_config()
    
    # Зберігаємо результат у контексті
    app_context['raw_config'] = final_config
    
    # Зберігаємо зведення
    collector.save_config_summary(final_config)
    
    logger.info("✅ Конфігурація зібрана та збережена")
    
    # Додаємо утиліту для керування конфігами
    app_context['config_collector'] = collector
    
    return collector

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка збирача конфігурацій."""
    if 'config_collector' in app_context:
        del app_context['config_collector']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("Збирач конфігурацій зупинено")