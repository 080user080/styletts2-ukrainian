# p_353_advanced_ui_core.py
"""
Головний модуль розширеного UI для Multi Dialog TTS.
Координує роботу всіх UI компонентів та збирає інтерфейс.
"""

import logging
import gradio as gr
from typing import Dict, Any, Optional

def prepare_config_models():
    """Конфігурація не потрібна для цього модуля."""
    return {}

def create_fallback_interface_simple(app_context: Dict[str, Any]) -> gr.Blocks:
    """
    Створює простий інтерфейс як fallback при помилках.
    Використовується коли не вдається завантажити повний розширений UI.
    """
    logger = logging.getLogger("AdvancedUI_Core")
    logger.warning("Створення fallback інтерфейсу...")
    
    with gr.Blocks(title="TTS Multi Dialog (Simple Mode)", theme="default") as demo:
        gr.Markdown("""
        # ⚠️ Розширений UI (простий режим)
        
        Розширений інтерфейс не завантажився повністю. Використовуйте базові функції синтезу.
        """)
        
        with gr.Row():
            with gr.Column():
                text_input = gr.Textbox(
                    label="📋 Текст або сценарій",
                    lines=10,
                    placeholder="Введіть текст або сценарій з тегами #g1, #g2 тощо..."
                )
                
                with gr.Row():
                    speaker_id = gr.Slider(
                        1, 30, value=1, step=1,
                        label="Спікер (якщо немає тегів)"
                    )
                    speed = gr.Slider(
                        0.7, 1.3, value=0.88, step=0.01,
                        label="Швидкість"
                    )
                
                btn_synthesize = gr.Button("🎵 Синтезувати", variant="primary")
            
            with gr.Column():
                audio_output = gr.Audio(label="🔊 Результат")
                status_info = gr.Textbox(label="Статус", interactive=False, lines=3)
        
        # Обробка синтезу (якщо доступний TTS двигун)
        tts_engine = app_context.get('tts_engine')
        if tts_engine:
            def synthesize_simple(text, speaker, speed_val):
                try:
                    result = tts_engine.synthesize(
                        text=text,
                        speaker_id=int(speaker),
                        speed=float(speed_val)
                    )
                    
                    # Зберегти тимчасовий файл для Gradio
                    import tempfile
                    import soundfile as sf
                    
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        sf.write(tmp.name, result['audio'], result['sample_rate'])
                        return tmp.name, "✅ Синтез завершено успішно"
                        
                except Exception as e:
                    return None, f"❌ Помилка: {str(e)}"
            
            btn_synthesize.click(
                synthesize_simple,
                inputs=[text_input, speaker_id, speed],
                outputs=[audio_output, status_info]
            )
    
    logger.info("Fallback інтерфейс створено")
    return demo

def initialize(app_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Ініціалізація розширеного Gradio UI.
    Координує всі UI компоненти та збирає фінальний інтерфейс.
    
    Структура:
    1. Перевірка залежностей
    2. Імпорт UI компонентів
    3. Збірка інтерфейсу
    4. Реєстрація в системі
    """
    logger = app_context.get('logger', logging.getLogger("AdvancedUI_Core"))
    logger.info("🎨 Ініціалізація розширеного UI ядра...")
    
    try:
        # === 1. ПЕРЕВІРКА ЗАЛЕЖНОСТЕЙ ===
        required_components = ['tts_engine', 'dialog_parser', 'sfx_handler']
        missing = [comp for comp in required_components if comp not in app_context]
        
        if missing:
            logger.error(f"Відсутні необхідні компоненти: {', '.join(missing)}")
            logger.error("Розширений UI потребує: TTS Engine, Dialog Parser, SFX Handler")
            
            # Створюємо простий fallback інтерфейс
            demo = create_fallback_interface_simple(app_context)
            app_context['tts_gradio_advanced_demo'] = demo
            
            logger.warning("Створено fallback інтерфейс через відсутність компонентів")
            return {
                'status': 'fallback',
                'demo': demo,
                'reason': f"Відсутні компоненти: {', '.join(missing)}",
                'message': 'Використовується простий режим'
            }
        
        logger.info("✅ Всі необхідні компоненти доступні")
        
        # === 2. ІМПОРТ UI КОМПОНЕНТІВ ===
        # Імпортуємо всередині try-except для уникнення проблем з циклічними імпортами
        try:
            logger.info("🛠️  Імпорт UI компонентів...")
            from p_356_ui_styles import get_orange_theme
            from p_354_ui_builder import create_advanced_interface
            logger.info("✅ UI компоненти успішно імпортовано")
        except ImportError as import_err:
            logger.error(f"Помилка імпорту UI компонентів: {import_err}")
            logger.error("Переконайтеся, що всі UI модулі (p_354-p_357) присутні")
            
            # Створюємо простий інтерфейс як fallback
            demo = create_fallback_interface_simple(app_context)
            app_context['tts_gradio_advanced_demo'] = demo
            
            return {
                'status': 'fallback',
                'demo': demo,
                'reason': f'Import error: {import_err}',
                'message': 'Використовується простий режим через помилку імпорту'
            }
        
        # === 3. ЗБІРКА ІНТЕРФЕЙСУ ===
        logger.info("🛠️  Збірка розширеного інтерфейсу...")
        
        try:
            # Отримуємо тему та створюємо інтерфейс
            theme = get_orange_theme()
            demo = create_advanced_interface(app_context, theme)
            
            if not demo:
                raise RuntimeError("Не вдалося створити інтерфейс (повернуто None)")
                
        except Exception as build_error:
            logger.error(f"Помилка збірки інтерфейсу: {build_error}")
            logger.info("Створення fallback інтерфейсу...")
            
            # Fallback на простий інтерфейс
            demo = create_fallback_interface_simple(app_context)
            status = 'fallback'
            reason = f'Build error: {build_error}'
        else:
            status = 'ready'
            reason = ''
        
        # === 4. РЕЄСТРАЦІЯ В СИСТЕМІ ===
        app_context['tts_gradio_advanced_demo'] = demo
        app_context['advanced_ui_initialized'] = True
        
        # Реєстрація в GUI менеджері (якщо він доступний)
        gui_manager = app_context.get('gui_manager')
        if gui_manager:
            try:
                # Імпортуємо тип GUI всередині блоку
                from kod.p_090_gui_manager import GUIInfo, GUIType
                
                gui_info = GUIInfo(
                    module_name="p_353_advanced_ui_core",
                    gui_type=GUIType.GRADIO,
                    display_name="🎨 Розширений TTS (Multi Dialog)",
                    description="Розширений інтерфейс для складних сценаріїв з SFX",
                    priority=10  # Високий пріоритет
                )
                gui_manager.register_gui(gui_info)
                logger.info("✅ Розширений UI зареєстровано в GUI менеджері")
            except Exception as e:
                logger.warning(f"Не вдалося зареєструвати GUI: {e}")
        
        # Реєстрація дії для запуску (якщо реєстр доступний)
        action_registry = app_context.get('action_registry')
        if action_registry:
            try:
                def launch_advanced_interface():
                    """Запуск розширеного інтерфейсу."""
                    demo.launch(
                        server_name="0.0.0.0",
                        server_port=7862,
                        share=False
                    )
                    return "🎨 Розширений інтерфейс запущено на порту 7862"
                
                action_registry.register_action(
                    action_id="tts.launch_advanced_ui",
                    name="🎨 Запустити розширений UI",
                    callback=launch_advanced_interface,
                    description="Запуск розширеного інтерфейсу для Multi Dialog TTS",
                    module="p_353_advanced_ui_core",
                    category="TTS",
                    icon="🎭"
                )
                logger.info("✅ Дія для запуску розширеного UI зареєстрована")
            except Exception as e:
                logger.warning(f"Не вдалося зареєструвати дію: {e}")
        
        # === 5. ПОВЕРНЕННЯ РЕЗУЛЬТАТУ ===
        logger.info("✅ Розширений UI ядро успішно ініціалізовано")
        
        return {
            'status': status,
            'demo': demo,
            'port': 7862,
            'components': ['tts_engine', 'dialog_parser', 'sfx_handler', 'styles', 'builder'],
            'description': 'Розширений інтерфейс для Multi Dialog TTS з SFX підтримкою',
            'reason': reason,
            'is_fallback': status == 'fallback'
        }
    
    except Exception as e:
        logger.error(f"Критична помилка ініціалізації розширеного UI: {e}")
        import traceback
        traceback.print_exc()
        
        # Створюємо максимально простий інтерфейс навіть при критичній помилці
        try:
            demo = create_fallback_interface_simple(app_context)
            app_context['tts_gradio_advanced_demo'] = demo
            
            return {
                'status': 'error_fallback',
                'demo': demo,
                'port': 7862,
                'error': str(e),
                'message': 'Критична помилка, використовується мінімальний інтерфейс'
            }
        except Exception as final_error:
            logger.critical(f"Навіть fallback інтерфейс не вдалося створити: {final_error}")
            return None

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка розширеного UI та очищення ресурсів."""
    logger = app_context.get('logger', logging.getLogger("AdvancedUI_Core"))
    
    # Видаляємо всі компоненти UI з контексту
    ui_keys = [
        'tts_gradio_advanced_demo',
        'advanced_ui_initialized',
        'tts_advanced_interface',
        'advanced_ui_demo'
    ]
    
    for key in ui_keys:
        if key in app_context:
            del app_context[key]
            logger.debug(f"Видалено з контексту: {key}")
    
    logger.info("🛑 Розширений UI ядро зупинено")

# Додаткові утилітні функції для внутрішнього використання
def _check_ui_dependencies() -> Dict[str, bool]:
    """
    Перевіряє наявність всіх необхідних UI модулів.
    
    Returns:
        Словник з результатами перевірки
    """
    dependencies = {
        'p_354_ui_builder': False,
        'p_355_ui_handlers': False,
        'p_356_ui_styles': False,
        'p_357_ui_utils': False,
    }
    
    for module_name in dependencies.keys():
        try:
            __import__(module_name)
            dependencies[module_name] = True
        except ImportError:
            pass
    
    return dependencies

def get_ui_status(app_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Повертає статус розширеного UI.
    
    Returns:
        Словник з інформацією про стан UI
    """
    demo = app_context.get('tts_gradio_advanced_demo')
    
    return {
        'initialized': 'tts_gradio_advanced_demo' in app_context,
        'demo_exists': demo is not None,
        'demo_type': type(demo).__name__ if demo else None,
        'dependencies': _check_ui_dependencies(),
        'required_components': {
            'tts_engine': 'tts_engine' in app_context,
            'dialog_parser': 'dialog_parser' in app_context,
            'sfx_handler': 'sfx_handler' in app_context,
        },
        'gui_registered': 'advanced_ui_initialized' in app_context,
        'port': 7862,
        'timestamp': __import__('time').time(),
    }