# p_350_tts_gradio.py
"""
Мінімальний Gradio UI для тестування інтеграції TTS.
Цей модуль демонструє, як TTS інтегрується в систему.
"""

import gradio as gr
from typing import Dict, Any, Optional, Tuple
import logging
import os
import tempfile
from datetime import datetime

def prepare_config_models():
    """Конфігурація для Gradio UI."""
    # Модель конфігурації вже визначена в p_310_tts_config.py
    return {}

def check_dependencies() -> bool:
    """Перевірка залежностей для Gradio."""
    try:
        import gradio
        return True
    except ImportError:
        print("GRADIO не встановлено. Встановіть: pip install gradio")
        return False

def initialize(app_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ініціалізація Gradio UI модуля.
    Створює простий інтерфейс для тестування TTS інтеграції.
    """
    logger = app_context.get('logger', logging.getLogger("TTS_Gradio"))
    
    # Перевірка доступності TTS двигуна
    if 'tts_engine' not in app_context:
        logger.error("TTSEngine не знайдено в контексті")
        return {"status": "error", "message": "TTSEngine не ініціалізовано"}
    
    tts_engine = app_context['tts_engine']
    config = app_context.get('config', {})
    
    # Отримання налаштувань UI
    ui_config = {}
    if hasattr(config, 'gradio_ui'):
        ui_config = config.gradio_ui.dict()
    
    # Створення базового UI
    def create_test_interface():
        """Створення тестового інтерфейсу."""
        
        def synthesize_handler(text: str, speaker_id: int, speed: float) -> Tuple[Dict, str]:
            """Обробник синтезу."""
            try:
                if not text.strip():
                    return None, "❌ Введіть текст для синтезу"
                
                logger.info(f"Синтез: {len(text)} символів, спікер {speaker_id}, швидкість {speed}")
                
                # Виклик TTS двигуна
                result = tts_engine.synthesize(text, speaker_id, speed)
                
                # Створення тимчасового файлу для Gradio
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    import soundfile as sf
                    sf.write(tmp.name, result.audio, result.sample_rate)
                    
                    # Інформація про результат
                    info = f"""
                    ✅ Успішно синтезовано!
                    Тривалість: {result.duration:.2f} сек
                    Частота дискретизації: {result.sample_rate} Гц
                    Спікер: {speaker_id}
                    Швидкість: {speed}
                    """
                    
                    return tmp.name, info
                    
            except Exception as e:
                error_msg = f"❌ Помилка синтезу: {str(e)}"
                logger.error(f"Помилка синтезу: {e}")
                return None, error_msg
        
        def split_text_handler(text: str) -> str:
            """Обробник розбиття тексту."""
            try:
                parts = tts_engine.split_to_parts(text)
                result = f"Знайдено частин: {len(parts)}\n\n"
                
                for i, part in enumerate(parts, 1):
                    result += f"--- Частина {i} ({len(part)} символів) ---\n"
                    result += part + "\n\n"
                
                return result
            except Exception as e:
                return f"❌ Помилка розбиття: {e}"
        
        def parse_dialog_handler(text: str) -> str:
            """Обробник парсингу діалогу."""
            try:
                parsed = tts_engine.parse_dialog_tags(text)
                result = f"Знайдено реплік: {len(parsed)}\n\n"
                
                for i, (speaker, line) in enumerate(parsed, 1):
                    result += f"#{i}: Спікер {speaker}: {line[:100]}{'...' if len(line) > 100 else ''}\n"
                
                return result
            except Exception as e:
                return f"❌ Помилка парсингу: {e}"
        
        def get_status_handler() -> str:
            """Отримання статусу TTS."""
            try:
                status = tts_engine.get_status()
                result = "📊 Статус TTS двигуна:\n\n"
                
                for key, value in status.items():
                    if isinstance(value, dict):
                        result += f"{key}:\n"
                        for k, v in value.items():
                            result += f"  {k}: {v}\n"
                    else:
                        result += f"{key}: {value}\n"
                
                return result
            except Exception as e:
                return f"❌ Помилка отримання статусу: {e}"
        
        # --- Створення інтерфейсу ---
        with gr.Blocks(
            title="TTS Test Interface",
            theme=ui_config.get('theme', 'default')
        ) as demo:
            
            gr.Markdown("# 🎤 Тестування TTS Інтеграції")
            gr.Markdown("Простий інтерфейс для перевірки роботи TTS у модульній системі")
            
            with gr.Tab("🔊 Синтез мови"):
                with gr.Row():
                    with gr.Column(scale=2):
                        input_text = gr.Textbox(
                            label="Введіть текст",
                            placeholder="Введіть текст для синтезу мови...",
                            lines=8,
                            max_lines=20
                        )
                        
                        with gr.Row():
                            speaker_id = gr.Slider(
                                minimum=1,
                                maximum=tts_engine.config['tts'].get('speaker_max', 30),
                                value=1,
                                step=1,
                                label="ID спікера"
                            )
                            
                            speed = gr.Slider(
                                minimum=0.5,
                                maximum=2.0,
                                value=tts_engine.config['tts'].get('default_speed', 0.88),
                                step=0.01,
                                label="Швидкість"
                            )
                        
                        synthesize_btn = gr.Button("🎵 Синтезувати", variant="primary")
                    
                    with gr.Column(scale=1):
                        output_audio = gr.Audio(
                            label="Результат",
                            type="filepath",
                            interactive=False
                        )
                        
                        status_info = gr.Textbox(
                            label="Статус",
                            interactive=False,
                            lines=6
                        )
                
                synthesize_btn.click(
                    fn=synthesize_handler,
                    inputs=[input_text, speaker_id, speed],
                    outputs=[output_audio, status_info]
                )
            
            with gr.Tab("📝 Обробка тексту"):
                with gr.Row():
                    text_for_processing = gr.Textbox(
                        label="Текст для обробки",
                        placeholder="Введіть текст для розбиття на частини...",
                        lines=10
                    )
                
                with gr.Row():
                    split_btn = gr.Button("✂️ Розбити текст")
                    parse_btn = gr.Button("🎭 Парсинг діалогу")
                
                with gr.Row():
                    output_processing = gr.Textbox(
                        label="Результат обробки",
                        lines=15,
                        interactive=False
                    )
                
                split_btn.click(
                    fn=split_text_handler,
                    inputs=[text_for_processing],
                    outputs=[output_processing]
                )
                
                parse_btn.click(
                    fn=parse_dialog_handler,
                    inputs=[text_for_processing],
                    outputs=[output_processing]
                )
            
            with gr.Tab("⚙️ Налаштування та статус"):
                with gr.Row():
                    status_btn = gr.Button("🔄 Оновити статус")
                
                with gr.Row():
                    status_output = gr.Textbox(
                        label="Статус системи",
                        lines=20,
                        interactive=False
                    )
                
                status_btn.click(
                    fn=get_status_handler,
                    inputs=[],
                    outputs=[status_output]
                )
            
            with gr.Tab("ℹ️ Довідка"):
                gr.Markdown("""
                ## Довідка по TTS модулю
                
                ### Основні функції:
                1. **Синтез мови** - перетворення тексту в мову
                2. **Розбиття тексту** - автоматичне розділення довгого тексту
                3. **Парсинг діалогу** - розпізнавання тегів #g1, #g2 тощо
                
                ### Використання тегів:
                ```
                #g1: Привіт, як справи?
                #g2: Все добре, дякую!
                #g3_fast: Швидка репліка!
                ```
                
                ### Конфігурація:
                - Спікери: 1-30
                - Швидкість: 0.5 - 2.0
                - Автозбереження: увімкнено
                
                ### Інтеграція:
                Цей модуль повністю інтегрований у модульну систему фреймворку.
                """)
        
        return demo
    
    # Реєстрація в контексті
    app_context['tts_gradio_interface'] = create_test_interface
    
    # Реєстрація дій для запуску UI
    if 'action_registry' in app_context:
        from .p_080_registry import register_action
        
        def launch_interface():
            """Запуск інтерфейсу."""
            demo = create_test_interface()
            demo.launch(
                server_name=ui_config.get('server_name', '0.0.0.0'),
                server_port=ui_config.get('port', 7860),
                share=ui_config.get('share', False)
            )
            return "✅ Інтерфейс запущено"
        
        register_action(
            app_context,
            action_id="tts.launch_test_ui",
            name="🚀 Запустити TTS тест UI",
            callback=launch_interface,
            description="Запуск тестового інтерфейсу Gradio для TTS",
            module="p_350_tts_gradio",
            category="TTS",
            icon="🚀"
        )
    
    logger.info("Gradio UI модуль успішно ініціалізовано")
    
    return {
        "status": "success",
        "interface_creator": create_test_interface,
        "config": ui_config,
        "engine_status": tts_engine.get_status()
    }

def launch_standalone(app_context: Dict[str, Any]):
    """Запуск автономного інтерфейсу."""
    result = initialize(app_context)
    
    if result["status"] == "success":
        demo = result["interface_creator"]()
        
        # Отримання конфігурації
        ui_config = result.get("config", {})
        
        print("🚀 Запуск TTS Gradio інтерфейсу...")
        print(f"📡 Адреса: http://localhost:{ui_config.get('port', 7860)}")
        print(f"🎨 Тема: {ui_config.get('theme', 'default')}")
        
        demo.queue()
        demo.launch(
            server_name=ui_config.get('server_name', '0.0.0.0'),
            server_port=ui_config.get('port', 7860),
            share=ui_config.get('share', False),
            show_error=ui_config.get('show_error', True)
        )
    else:
        print("❌ Не вдалося ініціалізувати Gradio UI")

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка Gradio UI модуля."""
    logger = app_context.get('logger')
    if logger:
        logger.info("Зупинка TTS Gradio модуля...")
    
    # Видалення посилань з контексту
    for key in ['tts_gradio_interface', 'tts_gradio_demo']:
        if key in app_context:
            del app_context[key]
    
    if logger:
        logger.info("TTS Gradio модуль зупинено")