# main.py
"""
Головний файл для запуску системи.
"""

import sys
from pathlib import Path

# Додаємо папку kod до шляху пошуку модулів
sys.path.insert(0, str(Path(__file__).parent / "kod"))

def main():
    """Головна функція запуску."""
    print("🚀 Запуск модульної системи...")
    
    # Імпортуємо та запускаємо завантажувач
    from p_000_loader import initialize
    
    app_context = {}
    initialize(app_context)
    
    print("\n" + "="*50)
    print("✅ СИСТЕМА УСПІШНО ЗАВАНТАЖЕНА")
    print("="*50)
    
    # Показуємо доступні компоненти
    print("\n📦 Доступні компоненти:")
    for key, value in app_context.items():
        if not key.startswith('_'):
            print(f"  • {key}: {type(value).__name__}")
    
    print("\n🎯 Готово до роботи!")
    return app_context

if __name__ == "__main__":
    main()