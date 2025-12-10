#!/usr/bin/env python3
"""
run_tts_menu.py - Запуск TTS системи з меню вибору GUI
"""

import sys
from pathlib import Path

# Додаємо шлях до модулів
sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("🚀 Запуск TTS системи з меню вибору...")
    
    try:
        # Імпортуємо та запускаємо систему
        from main import main as init_system
        app_context = init_system()
        
        # Тепер виконаємо меню вибору вручну
        print("\n" + "="*60)
        print("🎨 МЕНЮ ВИБОРУ ГРАФІЧНИХ ІНТЕРФЕЙСІВ")
        print("="*60)
        print("\nДоступні інтерфейси:")
        
        # Перелік доступних GUI
        guis = []
        
        # Головний інтерфейс
        if 'gradio_main_demo' in app_context:
            guis.append(("main", "🎙️ Головний TTS інтерфейс (StyleTTS2)", 7860))
        
        # Тестовий інтерфейс
        if 'tts_gradio_interface' in app_context:
            guis.append(("test", "🧪 Тестовий TTS інтерфейс", 7861))
        
        # Розширений інтерфейс
        if '355_tts_gradio_advanced' in app_context:
            guis.append(("advanced", "🎨 Розширений TTS інтерфейс", 7862))
        
        if not guis:
            print("❌ Не знайдено доступних GUI")
            return
        
        # Показати меню
        for i, (key, name, port) in enumerate(guis, 1):
            print(f"  [{i}] {name}")
        
        print(f"  [Q] Вийти")
        
        while True:
            choice = input("\n🎯 Ваш вибір (номер або Q): ").strip().upper()
            
            if choice == 'Q':
                print("👋 Вихід")
                return
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(guis):
                    key, name, port = guis[choice_num - 1]
                    
                    if key == "main":
                        print(f"🚀 Запускаю {name}...")
                        print(f"🌐 Адреса: http://localhost:{port}")
                        print("   Натисніть Ctrl+C для зупинки")
                        demo = app_context['gradio_main_demo']
                        demo.launch(server_port=port, share=False, show_error=True)
                        break
                    
                    elif key == "test":
                        print(f"🚀 Запускаю {name}...")
                        print(f"🌐 Адреса: http://localhost:{port}")
                        print("   Натисніть Ctrl+C для зупинки")
                        create_func = app_context['tts_gradio_interface']
                        demo = create_func()
                        demo.launch(server_port=port, share=False)
                        break
                    
                    elif key == "advanced":
                        print(f"🚀 Запускаю {name}...")
                        print(f"🌐 Адреса: http://localhost:{port}")
                        print("   Натисніть Ctrl+C для зупинки")
                        module_data = app_context['355_tts_gradio_advanced']
                        demo = module_data['demo']
                        demo.launch(server_port=port, share=False)
                        break
                
                else:
                    print(f"❌ Невірний номер: {choice_num}")
                    
            except ValueError:
                print("❌ Невірний формат вводу!")
            except KeyboardInterrupt:
                print("\n👋 Зупинено користувачем")
                break
            except Exception as e:
                print(f"❌ Помилка запуску: {e}")
                import traceback
                traceback.print_exc()
                break
        
    except KeyboardInterrupt:
        print("\n👋 Система зупинена користувачем")
    except Exception as e:
        print(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()