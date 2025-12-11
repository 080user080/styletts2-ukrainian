# config_tool.py в корені проєкту
"""
Утиліта для керування конфігурацією.
"""

import yaml
from pathlib import Path
import sys
import shutil
import os

def show_summary():
    """Показати зведення конфігурації."""
    config_dir = Path("config")
    
    if not config_dir.exists():
        print("❌ Папка config/ не існує")
        return
    
    print("📊 ЗВЕДЕННЯ КОНФІГУРАЦІЇ")
    print("="*50)
    
    yaml_files = list(config_dir.glob("*.yaml"))
    print(f"Файлів конфігурації: {len(yaml_files)}\n")
    
    for yaml_file in sorted(yaml_files):
        with open(yaml_file, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        
        print(f"📄 {yaml_file.name}")
        print(f"   {first_line}")
        
        if yaml_file.name == "_config_summary.yaml":
            print("   ⚠️  Зведення (не редагувати вручну)")
        
        print()

def regenerate():
    """Перегенерувати конфігураційні файли."""
    config_dir = Path("config")
    
    if config_dir.exists():
        # Створюємо резервну копію
        backup_dir = Path("config_backup")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        
        shutil.copytree(config_dir, backup_dir)
        print(f"📦 Створено резервну копію: {backup_dir}")
        
        # Видаляємо згенеровані файли (крім користувацьких)
        for yaml_file in config_dir.glob("*.yaml"):
            if not yaml_file.name.startswith("_"):
                yaml_file.unlink()
    
    print("🔄 Для генерації нових файлів запустіть систему:")
    print("   python main.py")

def create_config_structure():
    """Створити базову структуру конфігурації."""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    # Створюємо базовий config.yaml
    config_file = Path("config.yaml")
    if not config_file.exists():
        base_config = {
            'app': {
                'name': 'Мій Модульний Проєкт',
                'version': '1.0.0',
                'mode': 'DEBUG'
            },
            'note': 'Цей файл має найвищий пріоритет. Редагуйте його для налаштувань.'
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(base_config, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        print("✅ Створено базовий config.yaml")
    
    print("📁 Структура конфігурації створена")
    print("   Запустіть python main.py для генерації модульних конфігів")

def main():
    """Головна функція."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "show":
            show_summary()
        elif command == "regenerate":
            regenerate()
        elif command == "init":
            create_config_structure()
        elif command == "help":
            print("Доступні команди:")
            print("  python config_tool.py show      - показати зведення")
            print("  python config_tool.py regenerate - перегенерувати файли")
            print("  python config_tool.py init      - створити базову структуру")
            print("  python config_tool.py help      - ця довідка")
        else:
            print(f"Невідома команда: {command}")
    else:
        show_summary()

if __name__ == "__main__":
    main()