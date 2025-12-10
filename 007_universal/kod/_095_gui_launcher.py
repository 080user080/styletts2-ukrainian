"""
p_095_gui_launcher.py - CLI для вибору та запуску GUI інтерфейсів
"""

import sys
import threading
import logging
from typing import Dict, Any, List, Tuple, Optional

def prepare_config_models():
    return {}

def initialize(app_context: Dict[str, Any]):
    """Ініціалізація GUI ланчера з інтерактивним меню."""
    logger = app_context.get('logger', logging.getLogger("GUILauncher"))
    
    # Отримати список доступних GUI
    available_guis = []
    
    # 1. Головний інтерфейс TTS (p_305_tts_gradio_main)
    if 'gradio_main_demo' in app_context:
        available_guis.append(("main_tts", "🎙️ Головний TTS інтерфейс (StyleTTS2)", "p_305_tts_gradio_main", 7860))
    
    # 2. Перевірити інші модулі
    for key in app_context:
        if key.endswith('_gradio') or 'gradio' in key.lower():
            if key != 'gradio_main_demo' and key != 'tts_gradio_interface':
                available_guis.append((key, f"🎨 {key}", key, 7861))
    
    # 3. Перевірити GUI менеджер
    gui_manager = app_context.get('gui_manager')
    if gui_manager and hasattr(gui_manager, 'guis') and gui_manager.guis:
        for gui_name, gui_info in gui_manager.guis.items():
            available_guis.append((gui_name, gui_info.display_name, gui_info.module_name, 7862))
    
    if not available_guis:
        logger.info("Немає доступних GUI для запуску")
        return None
    
    # Інтерактивне меню
    print("\n" + "="*60)
    print("🎨 МЕНЮ ЗАПУСКУ ГРАФІЧНИХ ІНТЕРФЕЙСІВ")
    print("="*60)
    print("\nДоступні інтерфейси:")
    
    for i, (key, name, module, port) in enumerate(available_guis, 1):
        print(f"  [{i}] {name} (порт: {port})")
    
    print(f"  [Q] Вийти (без запуску GUI)")
    
    choice = input("\n🎯 Ваш вибір (номер або Q): ").strip().upper()
    
    if choice == 'Q':
        print("👋 Вихід без запуску GUI")
        return None
    
    # Обробка числового вибору
    try:
        choice_num = int(choice)
        if 1 <= choice_num <= len(available_guis):
            key, name, module, port = available_guis[choice_num - 1]
            print(f"🚀 Запускаю {name}...")
            
            if key == "main_tts" and 'gradio_main_demo' in app_context:
                demo = app_context['gradio_main_demo']
                thread = threading.Thread(
                    target=demo.launch,
                    kwargs={"server_port": port, "share": False},
                    daemon=True
                )
                thread.start()
                print(f"🌐 Інтерфейс доступний за адресою: http://localhost:{port}")
                print("   Натисніть Ctrl+C для зупинки")
                
                try:
                    thread.join()
                except KeyboardInterrupt:
                    print("\n👋 Інтерфійс зупинено користувачем")
                
                return {"launched": key, "thread": thread}
        else:
            print("❌ Невірний номер!")
    except ValueError:
        print("❌ Невірний вибір!")
    
    return None

def stop(app_context: Dict[str, Any]):
    """Зупинка GUI ланчера."""
    pass