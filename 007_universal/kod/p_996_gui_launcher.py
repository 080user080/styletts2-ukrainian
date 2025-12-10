"""
p_996_gui_launcher.py - CLI для вибору та запуску GUI інтерфейсів (високий префікс)
Запускається після всіх інших модулів.
"""

import sys
import threading
import logging
import time
from typing import Dict, Any, List, Tuple, Optional

def prepare_config_models():
    return {}

def initialize(app_context: Dict[str, Any]):
    """Ініціалізація GUI ланчера з інтерактивним меню."""
    logger = app_context.get('logger', logging.getLogger("GUILauncher"))
    
    # Даємо системі трохи часу на завершення ініціалізації
    time.sleep(0.5)
    
    print("\n" + "="*60)
    print("🎨 МЕНЮ ВИБОРУ ГРАФІЧНИХ ІНТЕРФЕЙСІВ")
    print("="*60)
    print("\nДоступні інтерфейси:")
    
    # Список доступних GUI
    available_guis = []
    
    # 1. Головний інтерфейс TTS
    if 'gradio_main_demo' in app_context:
        available_guis.append((1, "🎙️ Головний TTS інтерфейс (StyleTTS2)", "main_tts", 7860))
    
    # 2. Тестовий інтерфейс
    if 'tts_gradio_interface' in app_context:
        available_guis.append((2, "🧪 Тестовий TTS інтерфейс", "test_tts", 7861))
    
    # 3. Розширений інтерфейс
    if '355_tts_gradio_advanced' in app_context:
        available_guis.append((3, "🎨 Розширений TTS інтерфейс", "advanced_tts", 7862))
    
    # 4. Перевірити інші можливі GUI
    for key in app_context:
        if 'demo' in key.lower() and 'gradio' in key.lower():
            if key not in ['gradio_main_demo']:
                available_guis.append((len(available_guis)+1, f"🌐 {key}", key, 7863 + len(available_guis)))
    
    if not available_guis:
        print("   ⚠️  Не знайдено доступних GUI інтерфейсів")
        print("\n   Доступні компоненти:")
        for key in sorted(app_context.keys()):
            if 'gradio' in key.lower() or 'gui' in key.lower() or 'demo' in key.lower():
                print(f"     • {key}")
        print("\n   Запустіть будь-який GUI через Python код:")
        print("     app_context['gradio_main_demo'].launch(server_port=7860)")
        return None
    
    # Показати меню
    for num, name, key, port in available_guis:
        print(f"  [{num}] {name} (порт: {port})")
    
    print(f"  [Q] Вийти (без запуску GUI)")
    
    choice = input("\n🎯 Ваш вибір (номер або Q): ").strip().upper()
    
    if choice == 'Q':
        print("👋 Вихід без запуску GUI")
        return None
    
    # Обробка вибору
    try:
        choice_num = int(choice)
        for num, name, key, port in available_guis:
            if num == choice_num:
                print(f"\n🚀 Запускаю {name}...")
                
                if key == "main_tts":
                    demo = app_context['gradio_main_demo']
                    thread = threading.Thread(
                        target=demo.launch,
                        kwargs={"server_port": port, "share": False, "show_error": True},
                        daemon=True
                    )
                    thread.start()
                    print(f"🌐 Інтерфейс доступний за адресою: http://localhost:{port}")
                    print("   Натисніть Ctrl+C в цьому вікні для зупинки")
                    
                    # Чекаємо завершення
                    try:
                        while thread.is_alive():
                            time.sleep(1)
                    except KeyboardInterrupt:
                        print("\n👋 Інтерфейс зупинено користувачем")
                    
                    return {"launched": key}
                
                elif key == "test_tts":
                    create_func = app_context['tts_gradio_interface']
                    demo = create_func()
                    demo.launch(server_port=port, share=False)
                    return {"launched": key}
                
                elif key == "advanced_tts":
                    module_data = app_context['355_tts_gradio_advanced']
                    if 'demo' in module_data:
                        demo = module_data['demo']
                        demo.launch(server_port=port, share=False)
                        return {"launched": key}
                
                else:
                    # Інші GUI
                    demo = app_context[key]
                    if hasattr(demo, 'launch'):
                        demo.launch(server_port=port, share=False)
                    return {"launched": key}
        
        print(f"❌ Невірний номер: {choice_num}")
        
    except ValueError:
        print("❌ Невірний формат вводу!")
    except Exception as e:
        print(f"❌ Помилка запуску: {e}")
        import traceback
        traceback.print_exc()
    
    return None

def stop(app_context: Dict[str, Any]):
    """Зупинка GUI ланчера."""
    pass