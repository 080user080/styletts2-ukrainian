"""
p_996_gui_launcher.py - Покращений CLI для вибору та запуску GUI інтерфейсів
ДИНАМІЧНИЙ СКАНЕР ВСІх доступних демо в app_context
"""

import sys
import threading
import logging
import time
from typing import Dict, Any, List, Tuple, Optional

# === КОНФІГУРАЦІЯ ВІДОМИХ ІНТЕРФЕЙСІВ ===
KNOWN_GUI_PATTERNS = {
    # ключ контексту → (назва, порт, пріоритет)
    'p_000_loader_demo': ("🚀 Основне завантаження", 7850, 200),
    'gradio_main_demo': ("🎙️ Головний TTS (StyleTTS2)", 7860, 100),
    'tts_gradio_interface': ("🧪 Тестовий TTS", 7861, 90),
    'p_353_advanced_ui_core_demo': ("🎨 Розширений TTS (Модульна версія)", 7862, 95),
    'tts_gradio_advanced_demo': ("🎨 Розширений TTS (Multi Dialog + SFX)", 7862, 95),
    'p_360_tts_gradio_advanced_ui_demo': ("🎨 Розширений TTS v360 (Legacy)", 7863, 85),
}

def prepare_config_models():
    """Конфігурація не потрібна."""
    return {}

def _find_all_gui_interfaces(app_context: Dict[str, Any]) -> List[Tuple[int, str, str, int, Any, int]]:
    """
    Сканує app_context і знаходить ВСІ доступні GUI інтерфейси.
    
    Returns:
        List[(номер_меню, назва, ключ_контексту, порт, об'єкт_демо, пріоритет)]
    """
    found_guis = []
    port_counter = 7860
    
    # === ПЕРШИЙ ПРОХІД: ВІДОМІ ІНТЕРФЕЙСИ (за пріоритетом) ===
    known_sorted = sorted(
        KNOWN_GUI_PATTERNS.items(),
        key=lambda x: x[1][2],  # Сортування за пріоритетом
        reverse=True
    )
    
    for key, (name, preferred_port, priority) in known_sorted:
        if key in app_context:
            demo_obj = app_context[key]
            
            # Перевірка, що це валідний об'єкт
            if demo_obj is not None and (hasattr(demo_obj, 'launch') or callable(demo_obj)):
                found_guis.append((
                    len(found_guis) + 1,  # номер меню
                    name,                  # назва
                    key,                   # ключ контексту
                    preferred_port,        # порт
                    demo_obj,              # об'єкт
                    priority               # пріоритет
                ))
    
    # === ДРУГИЙ ПРОХІД: НЕВІДОМІ ІНТЕРФЕЙСИ (динамічне сканування) ===
    # Шукаємо всі ключи з 'demo' або 'gradio' в названні, які ще не додані
    added_keys = {item[2] for item in found_guis}
    
    for key in sorted(app_context.keys()):
        if key in added_keys:
            continue  # Уже додано
        
        # Критерії для визначення GUI інтерфейсу
        is_gui = (
            ('demo' in key.lower() or 'gradio' in key.lower() or 'gui' in key.lower()) and
            app_context[key] is not None
        )
        
        if is_gui:
            demo_obj = app_context[key]
            
            # Перевірка валідності
            if hasattr(demo_obj, 'launch') or callable(demo_obj):
                port_counter += 1
                found_guis.append((
                    len(found_guis) + 1,  # номер меню
                    f"🌐 {key}",           # назва з ключа
                    key,                   # ключ контексту
                    port_counter,          # автоматичний порт
                    demo_obj,              # об'єкт
                    0                      # низький пріоритет
                ))
    
    return found_guis

def _display_menu(available_guis: List[Tuple], logger: logging.Logger) -> None:
    """Показує меню вибору інтерфейсів."""
    print("\n" + "="*70)
    print("🎨 МЕНЮ ВИБОРУ ГРАФІЧНИХ ІНТЕРФЕЙСІВ")
    print("="*70)
    print("\nДоступні інтерфейси:")
    
    for num, name, key, port, _, priority in available_guis:
        print(f"  [{num}] {name} (порт: {port})")
    
    print(f"\n  [Q] Вийти (без запуску GUI)")
    print(f"  [L] Показати всі доступні компоненти")
    print("="*70)

def _show_all_components(app_context: Dict[str, Any]) -> None:
    """Показує ВСІ компоненти в контексті (для отладки)."""
    print("\n📦 ВСІ ДОСТУПНІ КОМПОНЕНТИ В КОНТЕКСТІ:")
    print("-" * 70)
    
    categories = {
        'GUI/Demo': [],
        'TTS': [],
        'Dialog': [],
        'SFX': [],
        'Config': [],
        'Logger': [],
        'Registry': [],
        'Other': []
    }
    
    for key in sorted(app_context.keys()):
        value = app_context[key]
        
        # Класифікація
        if 'demo' in key.lower() or 'gradio' in key.lower() or 'gui' in key.lower():
            categories['GUI/Demo'].append(key)
        elif 'tts' in key.lower():
            categories['TTS'].append(key)
        elif 'dialog' in key.lower() or 'parser' in key.lower():
            categories['Dialog'].append(key)
        elif 'sfx' in key.lower():
            categories['SFX'].append(key)
        elif 'config' in key.lower():
            categories['Config'].append(key)
        elif 'logger' in key.lower():
            categories['Logger'].append(key)
        elif 'registry' in key.lower() or 'action' in key.lower():
            categories['Registry'].append(key)
        else:
            categories['Other'].append(key)
    
    for category, items in categories.items():
        if items:
            print(f"\n{category}:")
            for item in items:
                val_type = type(app_context[item]).__name__
                has_launch = hasattr(app_context[item], 'launch') if app_context[item] else False
                launch_marker = "✅ .launch()" if has_launch else ""
                print(f"  • {item} ({val_type}) {launch_marker}")
    
    print("\n" + "="*70)

def _launch_gui(demo_obj: Any, key: str, name: str, port: int, logger: logging.Logger) -> Optional[Dict]:
    """Запускає вибраний GUI інтерфейс."""
    print(f"\n🚀 Запускаю {name}...")
    print(f"   📍 Адреса: http://localhost:{port}")
    print(f"   🔑 Ключ контексту: {key}")
    
    try:
        # Варіант 1: gr.Blocks об'єкт з методом .launch()
        if hasattr(demo_obj, 'launch'):
            logger.info(f"Запуск Gradio демо: {key}")
            
            def run_gradio():
                try:
                    demo_obj.launch(
                        server_name="0.0.0.0",
                        server_port=port,
                        share=False,
                        show_error=True,
                        quiet=True
                    )
                except Exception as e:
                    print(f"   ❌ Помилка під час роботи: {e}")
                    logger.error(f"Помилка при роботі Gradio: {e}")
            
            thread = threading.Thread(target=run_gradio, daemon=True)
            thread.start()
            
            print("   ✅ Інтерфейс запущено успішно")
            print("   💡 Натисніть Ctrl+C в цьому вікні для зупинки")
            
            try:
                while thread.is_alive():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\n\n👋 Інтерфейс зупинено користувачем")
            
            return {"launched": key, "port": port}
        
        # Варіант 2: Функція-творець
        elif callable(demo_obj):
            logger.info(f"Запуск функції-творця GUI: {key}")
            print("   ⏳ Ініціалізація...")
            
            demo = demo_obj()  # Викликаємо функцію
            
            if not hasattr(demo, 'launch'):
                raise RuntimeError(f"Функція не повернула об'єкт Gradio")
            
            def run_gradio():
                try:
                    demo.launch(
                        server_name="0.0.0.0",
                        server_port=port,
                        share=False,
                        show_error=True,
                        quiet=True
                    )
                except Exception as e:
                    print(f"   ❌ Помилка під час роботи: {e}")
                    logger.error(f"Помилка при роботі Gradio: {e}")
            
            thread = threading.Thread(target=run_gradio, daemon=True)
            thread.start()
            
            print("   ✅ Інтерфейс запущено успішно")
            print("   💡 Натисніть Ctrl+C в цьому вікні для зупинки")
            
            try:
                while thread.is_alive():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\n\n👋 Інтерфейс зупинено користувачем")
            
            return {"launched": key, "port": port}
        
        else:
            print(f"   ❌ Невідомий тип GUI: {type(demo_obj)}")
            logger.error(f"Невідомий тип GUI для {key}: {type(demo_obj)}")
            return None
    
    except Exception as e:
        print(f"   ❌ Помилка запуску: {e}")
        logger.error(f"Помилка запуску {key}: {e}")
        import traceback
        traceback.print_exc()
        return None

def initialize(app_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Ініціалізація GUI ланчера з ДИНАМІЧНИМ сканером всех інтерфейсів.
    """
    logger = app_context.get('logger', logging.getLogger("GUILauncher"))
    
    # Даємо системі трохи часу на завершення ініціалізації
    time.sleep(0.5)
    
    # === СКАНУВАННЯ ВСЕХ ДОСТУПНИХ ІНТЕРФЕЙСІВ ===
    available_guis = _find_all_gui_interfaces(app_context)
    
    if not available_guis:
        print("\n" + "="*70)
        print("🎨 МЕНЮ ВИБОРУ ГРАФІЧНИХ ІНТЕРФЕЙСІВ")
        print("="*70)
        print("\n   ⚠️  Не знайдено доступних GUI інтерфейсів")
        print("\n   Доступні компоненти в контексті:")
        
        component_count = 0
        for key in sorted(app_context.keys()):
            if component_count >= 10:
                print(f"   ... та ще {len(app_context) - 10} компонентів")
                break
            print(f"     • {key}")
            component_count += 1
        
        print("\n   Для запуску інтерфейсу вручну:")
        print("     demo.launch(server_port=7860)")
        print("\n" + "="*70)
        return None
    
    # === ОСНОВНИЙ ЦИКЛ МЕНЮ ===
    while True:
        _display_menu(available_guis, logger)
        
        choice = input("\n🎯 Ваш вибір (номер, Q або L): ").strip().upper()
        
        if choice == 'Q':
            print("👋 Вихід без запуску GUI")
            return None
        
        if choice == 'L':
            _show_all_components(app_context)
            continue
        
        # Обробка вибору номера
        try:
            choice_num = int(choice)
            
            for num, name, key, port, demo_obj, priority in available_guis:
                if num == choice_num:
                    result = _launch_gui(demo_obj, key, name, port, logger)
                    return result
            
            print(f"❌ Невірний номер: {choice_num}")
        
        except ValueError:
            print("❌ Невірний формат вводу! Введіть номер, Q або L")

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка GUI ланчера."""
    logger = app_context.get('logger')
    if logger:
        logger.info("GUI Launcher зупинено")