"""
p_353_advanced_ui_core.py - Розширений UI для Multi Dialog TTS
ВИПРАВЛЕНА ВЕРСІЯ: правильна ініціалізація та реєстрація demo
"""

import logging
from typing import Dict, Any, Optional
import gradio as gr

def prepare_config_models():
    """Конфігурація не потрібна."""
    return {}

def initialize(app_context: Dict[str, Any]) -> Optional[gr.Blocks]:
    """
    Ініціалізація розширеного UI ядра.
    
    ВАЖЛИВО: Функція повертає gr.Blocks об'єкт напряму!
    Лаунчер очікує саме gr.Blocks, а не Dict.
    
    Args:
        app_context: Контекст додатку з усіма компонентами
    
    Returns:
        gr.Blocks - готовий інтерфейс до запуску
    """
    logger = app_context.get('logger', logging.getLogger("AdvancedUI_Core"))
    logger.info("🎨 Ініціалізація розширеного UI ядра...")
    
    try:
        # === 1. ПЕРЕВІРКА ЗАЛЕЖНОСТЕЙ ===
        required_components = ['tts_engine', 'dialog_parser', 'sfx_handler']
        missing = [comp for comp in required_components if comp not in app_context]
        
        if missing:
            logger.error(f"❌ Відсутні обов'язкові компоненти: {', '.join(missing)}")
            logger.error("   Розширений UI потребує: tts_engine, dialog_parser, sfx_handler")
            
            # Fallback: повертаємо простий інтерфейс
            demo = _create_fallback_interface(app_context, missing)
            
            # Обов'язково зберігаємо в контекст!
            app_context['tts_gradio_advanced_demo'] = demo
            
            return demo
        
        logger.info("✅ Всі обов'язкові компоненти доступні")
        
        # === 2. ІМПОРТ UI КОМПОНЕНТІВ ===
        try:
            logger.info("🛠️  Імпорт UI компонентів...")
            from p_354_ui_builder import AdvancedUIBuilder
            logger.info("✅ UI компоненти успішно імпортовано")
        except ImportError as import_err:
            logger.error(f"❌ Помилка імпорту UI компонентів: {import_err}")
            logger.warning("   Перевірте, що файли p_354-p_357 присутні")
            
            # Fallback: простий інтерфейс
            demo = _create_fallback_interface(app_context, ['p_354_ui_builder'])
            app_context['tts_gradio_advanced_demo'] = demo
            
            return demo
        
        # === 3. ПОБУДОВА ІНТЕРФЕЙСУ ===
        logger.info("🛠️  Побудова розширеного інтерфейсу...")
        
        try:
            builder = AdvancedUIBuilder(
                tts_engine=app_context['tts_engine'],
                dialog_parser=app_context['dialog_parser'],
                sfx_handler=app_context['sfx_handler'],
                logger=logger
            )
            
            demo = builder.build()
            
            if not demo:
                raise RuntimeError("Builder повернув None")
            
            logger.info("✅ Інтерфейс успішно побудований")
            
        except Exception as build_error:
            logger.error(f"❌ Помилка побудови інтерфейсу: {build_error}")
            import traceback
            traceback.print_exc()
            
            # Fallback: простий інтерфейс
            demo = _create_fallback_interface(app_context, ['builder'])
        
        # === 4. РЕЄСТРАЦІЯ В КОНТЕКСТІ ===
        logger.info("📝 Реєстрація інтерфейсу в контексті...")
        
        # ОБОВ'ЯЗКОВО зберігаємо demo в контекст з тим же ключем!
        app_context['tts_gradio_advanced_demo'] = demo
        app_context['advanced_ui_initialized'] = True
        
        logger.info("✅ Розширений UI ядро успішно ініціалізовано на порту 7862")
        
        # === 5. ПОВЕРНЕННЯ РЕЗУЛЬТАТУ ===
        # ВАЖЛИВО: Лаунчер очікує gr.Blocks, а не Dict!
        return demo
    
    except Exception as e:
        logger.error(f"❌ КРИТИЧНА ПОМИЛКА ініціалізації: {e}")
        import traceback
        traceback.print_exc()
        
        # Навіть при критичній помилці повернемо щось корисне
        demo = _create_fallback_interface(app_context, ['critical_error'])
        app_context['tts_gradio_advanced_demo'] = demo
        
        return demo

def _create_fallback_interface(app_context: Dict[str, Any], reason: list) -> gr.Blocks:
    """
    Створює простий fallback інтерфейс при помилках.
    
    Args:
        app_context: Контекст додатку
        reason: Список причин помилки
    
    Returns:
        gr.Blocks - простий інтерфейс
    """
    logger = app_context.get('logger', logging.getLogger("AdvancedUI_Core"))
    logger.warning("⚠️  Створення fallback інтерфейсу...")
    
    with gr.Blocks(title="TTS - Режим сумісності", theme="default") as demo:
        gr.Markdown("""
        # ⚠️ TTS Розширений режим (Режим сумісності)
        
        Повний розширений інтерфейс не вдалося завантажити.
        Використовуються базові функції синтезу.
        
        **Причина помилки:**
        """)
        
        for r in reason:
            gr.Markdown(f"- ❌ {r}")
        
        with gr.Row():
            with gr.Column():
                text_input = gr.Textbox(
                    label="📋 Текст для синтезу",
                    lines=5,
                    placeholder="Введіть текст для озвучення..."
                )
                
                with gr.Row():
                    speaker_id = gr.Slider(
                        1, 30, value=1, step=1,
                        label="🎤 Спікер"
                    )
                    speed = gr.Slider(
                        0.7, 1.3, value=0.88, step=0.01,
                        label="⏱️ Швидкість"
                    )
                
                btn_synthesize = gr.Button("🎵 Синтезувати", variant="primary")
            
            with gr.Column():
                audio_output = gr.Audio(label="🔊 Результат")
                status_info = gr.Textbox(label="ℹ️ Статус", interactive=False, lines=2)
        
        # Обробка синтезу (якщо TTS доступний)
        tts_engine = app_context.get('tts_engine')
        if tts_engine:
            def synthesize_simple(text, speaker, speed_val):
                """Простий синтез без мультидіалогу."""
                try:
                    if not text or not text.strip():
                        return None, "❌ Будь ласка, введіть текст"
                    
                    result = tts_engine.synthesize(
                        text=text,
                        speaker_id=int(speaker),
                        speed=float(speed_val)
                    )
                    
                    import tempfile
                    import soundfile as sf
                    
                    # Збереження в тимчасовий файл
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        sf.write(tmp.name, result['audio'], result['sample_rate'])
                        return tmp.name, "✅ Синтез завершено успішно"
                    
                except Exception as e:
                    return None, f"❌ Помилка синтезу: {str(e)}"
            
            btn_synthesize.click(
                synthesize_simple,
                inputs=[text_input, speaker_id, speed],
                outputs=[audio_output, status_info]
            )
    
    logger.info("✅ Fallback інтерфейс створено")
    return demo

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка розширеного UI та очищення ресурсів."""
    logger = app_context.get('logger', logging.getLogger("AdvancedUI_Core"))
    
    # Видаляємо компоненти з контексту
    ui_keys = [
        'tts_gradio_advanced_demo',
        'advanced_ui_initialized',
    ]
    
    for key in ui_keys:
        if key in app_context:
            del app_context[key]
            logger.debug(f"Видалено з контексту: {key}")
    
    logger.info("🛑 Розширений UI ядро зупинено")