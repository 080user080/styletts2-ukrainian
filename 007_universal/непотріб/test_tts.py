#!/usr/bin/env python3
"""
Тестування TTS Engine
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from main import app_context

def test_basic():
    """Базовий тест синтезу"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ 1: Базовий синтез")
    print("="*60 + "\n")
    
    engine = app_context.get('tts_engine')
    if not engine:
        print("❌ TTS Engine не знайдено!")
        return
    
    # Тестовий текст
    text = "Привіт! Це тест синтезу мовлення."
    
    print(f"📝 Текст: {text}")
    print(f"🎤 Голос: default")
    print(f"⚡ Швидкість: 0.88")
    print("\n🔄 Синтез...")
    
    try:
        result = engine.synthesize(
            text=text,
            speaker_id=1,
            speed=0.88
        )
        
        print(f"✅ Успішно!")
        print(f"   Тривалість: {result['duration']:.2f} сек")
        print(f"   Sample rate: {result['sample_rate']} Hz")
        print(f"   Аудіо: {result['audio'].shape}")
        if result.get('output_path'):
            print(f"   💾 Збережено: {result['output_path']}")
        
    except Exception as e:
        print(f"❌ Помилка: {e}")
        import traceback
        traceback.print_exc()

def test_voices():
    """Тест списку голосів"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ 2: Доступні голоси")
    print("="*60 + "\n")
    
    engine = app_context.get('tts_engine')
    if not engine:
        print("❌ TTS Engine не знайдено!")
        return
    
    try:
        voices = engine.get_available_voices()
        print(f"📋 Знайдено голосів: {len(voices)}\n")
        for i, voice in enumerate(voices, 1):
            print(f"   {i}. {voice}")
    except Exception as e:
        print(f"❌ Помилка: {e}")

def test_status():
    """Тест статусу"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ 3: Статус TTS Engine")
    print("="*60 + "\n")
    
    engine = app_context.get('tts_engine')
    if not engine:
        print("❌ TTS Engine не знайдено!")
        return
    
    try:
        status = engine.get_status()
        print("📊 Статус:")
        print(f"   Ініціалізовано: {status['initialized']}")
        print(f"   Сесія: {status['session_id']}")
        print(f"   Вихідна папка: {status['output_dir']}")
        print(f"   Доступно голосів: {status['available_voices']}")
        print(f"\n⚙️ Конфігурація:")
        for key, val in status['config'].items():
            print(f"   {key}: {val}")
        print(f"\n📦 Залежності:")
        for key, val in status['dependencies'].items():
            icon = "✅" if val else "❌"
            print(f"   {icon} {key}")
    except Exception as e:
        print(f"❌ Помилка: {e}")

def test_actions():
    """Тест зареєстрованих дій"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ 4: Зареєстровані дії")
    print("="*60 + "\n")
    
    registry = app_context.get('action_registry')
    if not registry:
        print("❌ ActionRegistry не знайдено!")
        return
    
    try:
        # Отримати всі дії (якщо є такий метод)
        if hasattr(registry, 'get_all_actions'):
            actions = registry.get_all_actions()
            tts_actions = [a for a in actions if a.get('id', '').startswith('tts.')]
            
            print(f"📋 TTS дії: {len(tts_actions)}\n")
            for action in tts_actions:
                print(f"   • {action.get('name', 'N/A')}")
                print(f"     ID: {action.get('id', 'N/A')}")
                print(f"     Опис: {action.get('description', 'N/A')}\n")
        else:
            print("⚠️ Метод get_all_actions() не доступний")
            print("   Спробуйте виконати дію напряму:")
            print("   action_registry.execute('tts.get_status')")
    except Exception as e:
        print(f"❌ Помилка: {e}")

def main():
    print("\n🚀 ТЕСТУВАННЯ TTS СИСТЕМИ\n")
    
    # Перевірити наявність компонентів
    if 'tts_engine' not in app_context:
        print("❌ TTS Engine не завантажено!")
        return
    
    print("✅ TTS Engine знайдено\n")
    
    # Запустити тести
    test_status()
    test_voices()
    test_basic()
    test_actions()
    
    print("\n" + "="*60)
    print("✅ ВСІ ТЕСТИ ЗАВЕРШЕНО")
    print("="*60 + "\n")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Критична помилка: {e}")
        import traceback
        traceback.print_exc()
