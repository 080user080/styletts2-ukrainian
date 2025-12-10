#!/usr/bin/env python3
"""
Запуск розширеного Gradio UI для TTS
"""

import sys
import os

# Додати поточну директорію до шляху
sys.path.insert(0, os.getcwd())

# Імпортувати завантажену систему
from main import app_context

def main():
    print("\n" + "="*60)
    print("🎨 ЗАПУСК GRADIO UI")
    print("="*60 + "\n")
    
    # Перевірити наявність компонентів
    if 'tts_engine' not in app_context:
        print("❌ TTS Engine не знайдено в системі!")
        return
    
    if '355_tts_gradio_advanced' not in app_context:
        print("❌ Розширений Gradio UI не знайдено!")
        return
    
    # Отримати інтерфейс
    ui_module = app_context['355_tts_gradio_advanced']
    
    if 'demo' not in ui_module:
        print("❌ Gradio demo не знайдено в модулі!")
        return
    
    demo = ui_module['demo']
    
    print("✅ Всі компоненти готові!")
    print("\n📍 Інтерфейс буде доступний за адресою:")
    print("   http://localhost:7860")
    print("\n💡 Для зупинки: Ctrl+C\n")
    
    # Запустити інтерфейс
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Зупинка сервера...")
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
