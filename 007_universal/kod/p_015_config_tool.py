# p_015_config_tool.py
"""
Модуль утиліт для керування конфігурацією.
Надає CLI команди та автоматичне створення config.yaml
"""

import yaml
from pathlib import Path
import sys
import shutil
from typing import Dict, Any
import logging

# Константи шляхів
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
MAIN_CONFIG = PROJECT_ROOT / "config.yaml"

def prepare_config_models():
    """Повертає моделі конфігурації (опційно)."""
    return {}

def initialize(app_context: Dict[str, Any]):
    """
    Ініціалізація модуля.
    Автоматично створює config.yaml якщо не існує.
    """
    logger = app_context.get('logger', logging.getLogger("ConfigTool"))
    
    # Перевірка та створення основного config.yaml
    if not MAIN_CONFIG.exists():
        create_main_config()
        logger.info("✅ Створено основний config.yaml")
    
    # Перевірка папки config
    CONFIG_DIR.mkdir(exist_ok=True)
    
    logger.info("🚀 Модуль керування конфігурацією активований")
    
    # Додаємо утиліту в контекст
    app_context['config_tool'] = {
        'show_summary': show_summary,
        'regenerate': regenerate_configs,
        'create_structure': create_config_structure
    }
    
    return None

def stop(app_context: Dict[str, Any]):
    """Зупинка модуля."""
    if 'config_tool' in app_context:
        del app_context['config_tool']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("Модуль config_tool зупинено")

# ============================================================================
# УТІЛІТНІ ФУНКЦІЇ
# ============================================================================

def create_main_config():
    """Створити основний config.yaml з базовими налаштуваннями."""
    base_config = {
        'app': {
            'name': 'Мій Модульний Проєкт',
            'version': '1.0.0',
            'mode': 'DEBUG'
        },
        'note': 'Цей файл має найвищий пріоритет. Редагуйте його для налаштувань.'
    }
    
    with open(MAIN_CONFIG, 'w', encoding='utf-8') as f:
        yaml.dump(base_config, f, 
                  default_flow_style=False, 
                  allow_unicode=True, 
                  indent=2)

def show_summary():
    """Показати зведення конфігурації."""
    print("📊 ЗВЕДЕННЯ КОНФІГУРАЦІЇ")
    print("="*50)
    
    # Основні файли
    main_exists = MAIN_CONFIG.exists()
    config_exists = CONFIG_DIR.exists()
    
    print(f"Основні файли:")
    print(f"  📄 config.yaml: {'✅' if main_exists else '❌'}")
    print(f"  📁 Папка config/: {'✅' if config_exists else '❌'}")
    print()
    
    if config_exists:
        yaml_files = list(CONFIG_DIR.glob("*.yaml"))
        print(f"Модульних файлів: {len(yaml_files)}")
        
        for yaml_file in sorted(yaml_files):
            with open(yaml_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
            
            prefix = "⚠️  " if yaml_file.name.startswith('_') else "📄 "
            print(f"  {prefix}{yaml_file.name}")
            
            if len(first_line) > 0:
                print(f"      {first_line}")

def regenerate_configs():
    """Перегенерувати модульні конфігураційні файли."""
    if CONFIG_DIR.exists():
        # Резервна копія
        backup_dir = PROJECT_ROOT / "config_backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(CONFIG_DIR, backup_dir)
        print(f"📦 Резервна копія: {backup_dir}")
        
        # Видаляємо автоматично згенеровані файли
        for yaml_file in CONFIG_DIR.glob("*.yaml"):
            if not yaml_file.name.startswith("_"):
                yaml_file.unlink()
    
    print("\n🔄 Для генерації нових файлів запустіть систему:")
    print("   python main.py")

def create_config_structure():
    """Створити повну структуру конфігурації."""
    # Основний config.yaml
    if not MAIN_CONFIG.exists():
        create_main_config()
        print("✅ Створено config.yaml")
    
    # Папка config
    CONFIG_DIR.mkdir(exist_ok=True)
    
    # Файл-підказка
    help_file = CONFIG_DIR / "_README.md"
    if not help_file.exists():
        with open(help_file, 'w', encoding='utf-8') as f:
            f.write("""# Папка конфігурації

Тут зберігаються автоматично згенеровані файли налаштувань.

## Правила:
- Файли з префіксом `_` не змінюються вручну
- Для налаштувань редагуйте `config.yaml` в корені
- Для перегенерації: `python kod/p_015_config_tool.py regenerate`
""")
    
    print("📁 Структура конфігурації створена")

# ============================================================================
# CLI ІНТЕРФЕЙС
# ============================================================================

def main_cli():
    """Головна CLI функція."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "show":
            show_summary()
        elif command == "regenerate":
            regenerate_configs()
        elif command == "init":
            create_config_structure()
        elif command == "help":
            print("Доступні команди:")
            print("  python -m kod.p_015_config_tool show      - показати зведення")
            print("  python -m kod.p_015_config_tool regenerate - перегенерувати файли")
            print("  python -m kod.p_015_config_tool init      - створити структуру")
            print("  python -m kod.p_015_config_tool help      - довідка")
        else:
            print(f"Невідома команда: {command}")
    else:
        show_summary()

if __name__ == "__main__":
    main_cli()