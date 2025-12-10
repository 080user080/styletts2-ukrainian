# p_012_config_updater.py
"""
Модуль для автоматичного створення та оновлення основного config.yaml.
Додає тільки нові секції для нових модулів, не перезаписуючи існуючі налаштування.
"""

import yaml
import ast
from pathlib import Path
from typing import Dict, Any, Tuple
import logging
import os

def prepare_config_models():
    """Повертає моделі конфігурації."""
    return {}

def extract_default_config_from_file(filepath: Path) -> Tuple[str, Dict[str, Any]]:
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
                            return None, {}
    
    except Exception as e:
        pass
    
    return None, {}

def deep_merge_existing_only(target: Dict, source: Dict):
    """
    Додає тільки відсутні ключі з source в target.
    Не змінює вже існуючі значення.
    """
    for key, value in source.items():
        if key not in target:
            target[key] = value
        elif isinstance(value, dict) and isinstance(target[key], dict):
            deep_merge_existing_only(target[key], value)

def scan_modules_for_default_configs(project_root: Path) -> Dict[str, Any]:
    """Сканує всі модулі та збирає їх DEFAULT_CONFIG."""
    kod_path = project_root / "kod"
    all_defaults = {}
    
    for py_file in kod_path.glob("**/p_*.py"):
        if not py_file.name.startswith('p_'):
            continue
        
        module_name, defaults = extract_default_config_from_file(py_file)
        if defaults and isinstance(defaults, dict):
            # Додаємо конфігурацію модуля
            for key, value in defaults.items():
                if key not in all_defaults:
                    all_defaults[key] = {}
                deep_merge_existing_only(all_defaults[key], value)
    
    return all_defaults

def initialize(app_context: Dict[str, Any]):
    """
    Ініціалізація модуля оновлення config.yaml.
    Створює або доповнює config.yaml тільки новими секціями.
    """
    logger = app_context.get('logger', logging.getLogger("ConfigUpdater"))
    logger.info("🔄 Оновлення основного config.yaml...")
    
    # Шляхи
    project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_filepath = project_root / "config.yaml"
    
    # 1. Скануємо всі модулі для збору DEFAULT_CONFIG
    logger.info("📦 Сканування модулів для збору конфігурацій...")
    default_configs = scan_modules_for_default_configs(project_root)
    
    if not default_configs:
        logger.warning("⚠️ Не знайдено DEFAULT_CONFIG у модулях")
        return
    
    logger.info(f"📊 Знайдено {len(default_configs)} секцій конфігурації")
    
    # 2. Завантажуємо поточний config.yaml (якщо існує)
    current_config = {}
    config_exists = config_filepath.exists()
    
    if config_exists:
        try:
            with open(config_filepath, 'r', encoding='utf-8') as f:
                current_config = yaml.safe_load(f) or {}
            logger.info("📄 Завантажено існуючий config.yaml")
        except Exception as e:
            logger.error(f"❌ Помилка читання config.yaml: {e}")
            current_config = {}
    else:
        logger.info("📄 config.yaml не знайдено, буде створено новий")
    
    # 3. Доповнюємо тільки відсутні секції
    added_sections = []
    updated_sections = []
    
    for section, defaults in default_configs.items():
        if section not in current_config:
            # Нова секція - додаємо повністю
            current_config[section] = defaults
            added_sections.append(section)
        else:
            # Секція вже існує - додаємо тільки нові підключі
            section_added_keys = []
            for key, value in defaults.items():
                if key not in current_config[section]:
                    if isinstance(current_config[section], dict):
                        current_config[section][key] = value
                        section_added_keys.append(key)
            
            if section_added_keys:
                updated_sections.append((section, section_added_keys))
    
    # 4. Зберігаємо config.yaml
    try:
        # Додаємо коментар-попередження на початок
        yaml_content = "# Основна конфігурація проекту\n"
        yaml_content += "# Цей файл автоматично оновлюється при додаванні нових модулів\n"
        yaml_content += "# Ручні зміни ЗБЕРІГАЮТЬСЯ, додаються тільки нові поля\n"
        yaml_content += "---\n\n"
        
        # Конвертуємо словник в YAML
        yaml_content += yaml.dump(current_config, 
                                 default_flow_style=False, 
                                 sort_keys=True, 
                                 allow_unicode=True, 
                                 indent=2)
        
        with open(config_filepath, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # Логуємо зміни
        if added_sections:
            logger.info(f"✅ Додано нові секції: {', '.join(added_sections)}")
        
        if updated_sections:
            for section, keys in updated_sections:
                logger.info(f"🔧 Оновлено секцію '{section}': {', '.join(keys)}")
        
        if not added_sections and not updated_sections:
            logger.info("ℹ️ config.yaml вже актуальний, змін не потрібно")
        
        logger.info(f"💾 config.yaml збережено: {config_filepath}")
        
        # Створюємо докладний звіт
        create_config_report(project_root, current_config, default_configs, logger)
        
    except Exception as e:
        logger.error(f"❌ Помилка збереження config.yaml: {e}")
    
    # 5. Додаємо утиліту в контекст
    app_context['config_updater'] = {
        'scan_configs': lambda: scan_modules_for_default_configs(project_root),
        'get_current_config': lambda: current_config,
        'force_update': lambda: initialize(app_context)  # Для примусового оновлення
    }

def create_config_report(project_root: Path, current_config: Dict, 
                        default_configs: Dict, logger):
    """Створює докладний звіт про конфігурацію."""
    report_dir = project_root / "config_reports"
    report_dir.mkdir(exist_ok=True)
    
    report = {
        'summary': {
            'total_sections': len(current_config),
            'sections_from_modules': list(default_configs.keys()),
            'all_sections': list(current_config.keys())
        },
        'module_defaults': default_configs,
        'current_config': current_config,
        'notes': [
            "Цей звіт генерується автоматично",
            "Зміни в config.yaml відбуваються при додаванні нових модулів",
            "Існуючі налаштування користувача не перезаписуються"
        ]
    }
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"config_report_{timestamp}.yaml"
    
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            yaml.dump(report, f, 
                     default_flow_style=False, 
                     sort_keys=True, 
                     allow_unicode=True, 
                     indent=2)
        logger.debug(f"📋 Звіт збережено: {report_path}")
    except Exception as e:
        logger.debug(f"Не вдалося зберегти звіт: {e}")

def stop(app_context: Dict[str, Any]):
    """Зупинка модуля."""
    if 'config_updater' in app_context:
        del app_context['config_updater']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("Модуль оновлення config.yaml зупинено")

# CLI інтерфейс для ручного запуску
if __name__ == "__main__":
    import sys
    
    # Простий контекст для CLI
    class SimpleLogger:
        def info(self, msg): print(f"[INFO] {msg}")
        def warning(self, msg): print(f"[WARN] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")
        def debug(self, msg): print(f"[DEBUG] {msg}")
    
    context = {'logger': SimpleLogger()}
    
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        print("🔄 Примусове оновлення config.yaml...")
        initialize(context)
    else:
        print("Використання:")
        print("  python -m kod.p_012_config_updater update  - оновити config.yaml")