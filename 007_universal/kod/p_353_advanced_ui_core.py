import logging
from typing import Dict, Any, Optional
import gradio as gr
from p_354_ui_builder import AdvancedUIBuilder

def prepare_config_models():
    """Конфігурація не потрібна."""
    return {}

def initialize(app_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Єдина точка входу для ініціалізації розширеного UI."""
    logger = app_context.get('logger', logging.getLogger("AdvancedUI_Core"))
    logger.info("🎨 Ініціалізація розширеного UI ядра...")
    
    try:
        # === 1. ПЕРЕВІРКА ЗАЛЕЖНОСТЕЙ ===
        required_components = ['tts_engine', 'dialog_parser', 'sfx_handler']
        missing = [comp for comp in required_components if comp not in app_context]
        
        if missing:
            logger.error(f"Відсутні компоненти: {', '.join(missing)}")
            return {'status': 'error', 'message': f'Відсутні: {missing}'}
        
        logger.info("✅ Всі компоненти доступні")
        
        # === 2. ПОБУДОВА ІНТЕРФЕЙСУ ===
        builder = AdvancedUIBuilder(
            tts_engine=app_context['tts_engine'],
            dialog_parser=app_context['dialog_parser'],
            sfx_handler=app_context['sfx_handler'],
            logger=logger
        )
        
        demo = builder.build()
        
        if not demo:
            raise RuntimeError("Не вдалося створити інтерфейс")
        
        # === 3. РЕЄСТРАЦІЯ ===
        app_context['tts_gradio_advanced_demo'] = demo
        app_context['advanced_ui_initialized'] = True
        
        logger.info("✅ Розширений UI успішно ініціалізовано")
        
        return {
            'status': 'ready',
            'demo': demo,
            'port': 7862,
            'description': 'Розширений інтерфейс для Multi Dialog TTS з SFX'
        }
    
    except Exception as e:
        logger.error(f"Помилка ініціалізації: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'error', 'error': str(e)}

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка UI."""
    logger = app_context.get('logger', logging.getLogger("AdvancedUI_Core"))
    
    if 'tts_gradio_advanced_demo' in app_context:
        del app_context['tts_gradio_advanced_demo']
    
    logger.info("🛑 Розширений UI зупинено")