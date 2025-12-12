"""
p_305_tts_gradio_main.py - Головний Gradio інтерфейс StyleTTS2
(Виділено з app.py)
"""

import gradio as gr
from typing import Dict, Any, Optional
import logging
import re
from unicodedata import normalize
from .p_100_logger import logger

# Конфігурація
from pydantic import BaseModel

class GradioMainConfig(BaseModel):
    enabled: bool = True
    port: int = 7860
    server_name: str = "0.0.0.0"
    share: bool = False
    analytics_enabled: bool = False

def prepare_config_models():
    return {'gradio_main': GradioMainConfig}

DEFAULT_CONFIG = {
    'gradio_main': {
        'enabled': True,
        'port': 7860,
        'server_name': '0.0.0.0',
        'share': False,
        'analytics_enabled': False
    }
}

def check_dependencies() -> bool:
    """Перевірка залежностей."""
    try:
        import gradio
        import torch
        import ipa_uk
        from ukrainian_word_stress import Stressifier, StressSymbol
        return True
    except ImportError:
        return False

def create_main_interface(app_context: Dict[str, Any]):
    """
    Створити головний інтерфейс Gradio.
    Адаптовано з app.py
    """
    logger = app_context.get('logger', logging.getLogger("GradioMain"))
    
    # Отримати необхідні компоненти
    tts_models = app_context.get('tts_models')
    verbalizer = app_context.get('verbalizer')
    tts_utils = app_context.get('tts_utils', {})
    
    if not tts_models:
        logger.error("TTS моделі не знайдено в контексті")
        return None
    
    # Імпорт специфічних бібліотек
    try:
        from ipa_uk import ipa
        from ukrainian_word_stress import Stressifier, StressSymbol
        stressify = Stressifier()
    except ImportError as e:
        logger.error(f"Не вдалося імпортувати бібліотеки: {e}")
        return None
    
    # Отримати дані з менеджера моделей
    prompts_list = tts_models.get_available_voices()
    
    # Функція синтезу (адаптована з app.py)
    def synthesize(model_name: str, text: str, speed: float, 
                  voice_name: Optional[str] = None, 
                  progress=gr.Progress()):
        
        if text.strip() == "":
            raise gr.Error("Потрібно ввести текст")
        
        if len(text) > 50000:
            raise gr.Error("Текст має бути менше 50к символів")
        
        result_wav = []
        
        # Використати утиліту для розбиття тексту
        if 'split_to_parts' in tts_utils:
            text_parts = tts_utils['split_to_parts'](text)
        else:
            # Fallback
            text_parts = [text]
        
        for t in progress.tqdm(text_parts):
            t = t.strip()
            t = t.replace('"', '')
            if not t:
                continue
            
            # Обробка тексту (з app.py)
            t = t.replace('+', StressSymbol.CombiningAcuteAccent)
            t = normalize('NFKC', t)
            t = re.sub(r'[᠆‐‑‒–—―⁻₋−⸺⸻]', '-', t)
            t = re.sub(r' - ', ': ', t)
            
            # Конвертація в IPA
            ps = ipa(stressify(t))
            
            if ps:
                # Вибір моделі
                if model_name == 'single':
                    model, style = tts_models.get_single_model()
                    if not style:
                        raise gr.Error("Single стиль не завантажено")
                    
                    tokens = model.tokenizer.encode(ps)
                    wav = model(tokens, speed=speed, s_prev=style)
                    
                elif model_name == 'multi':
                    model, style = tts_models.get_multi_model(voice_name)
                    if not style:
                        raise gr.Error(f"Стиль для голосу '{voice_name}' не знайдено")
                    
                    tokens = model.tokenizer.encode(ps)
                    wav = model(tokens, speed=speed, s_prev=style)
                
                else:
                    raise gr.Error(f"Невідома модель: {model_name}")
                
                result_wav.append(wav)
        
        if not result_wav:
            raise gr.Error("Не вдалося синтезувати аудіо")
        
        # Об'єднати всі частини
        import torch
        concatenated = torch.concatenate(result_wav).cpu().numpy()
        
        return 24000, concatenated
    
    # Функція вербалізації
    def verbalize_handler(text: str) -> str:
        if 'verbalize_text' in tts_utils:
            return tts_utils['verbalize_text'](text)
        return text
    
    # Функція вибору прикладу
    def select_example(evt: gr.SelectData):
        return evt.row_value
    
    # Приклади (з app.py)
    examples = [
        ["Одна дівчинка стала королевою Франції. Звали її Анна, і була вона донькою Ярослава Му+дрого, великого київського князя.", 1.0],
    ]
    
    description = '''
    <h1 style="text-align:center;">StyleTTS2: Українська. Інтеграція в модульну систему</h1><br>
    Програма може не коректно визначати деякі наголоси.
    Якщо наголос не правильний, використовуйте символ + після наголошеного складу.
    '''
    
    # Створення інтерфейсу
    with gr.Blocks(title="StyleTTS2 Ukrainian", css="") as demo:
        gr.Markdown(description)
        
        # Single speaker вкладка
        with gr.Tab("Single speaker"):
            with gr.Row():
                with gr.Column(scale=1):
                    input_text = gr.Text(label='Text:', lines=5, max_lines=10)
                    verbalize_button = gr.Button("Вербалізувати(beta)")
                    speed = gr.Slider(label='Швидкість:', maximum=1.3, minimum=0.7, value=0.9)
                    verbalize_button.click(verbalize_handler, inputs=[input_text], outputs=[input_text])
                    
                with gr.Column(scale=1):
                    output_audio = gr.Audio(
                        label="Audio:",
                        autoplay=False,
                        streaming=False,
                        type="numpy",
                    )
                    synthesise_button = gr.Button("Синтезувати")
                    single_text = gr.Text(value='single', visible=False)
                    synthesise_button.click(
                        synthesize, 
                        inputs=[single_text, input_text, speed], 
                        outputs=[output_audio]
                    )
        
        # Multi speaker вкладка
        with gr.Tab("Multi speaker"):
            with gr.Row():
                with gr.Column(scale=1):
                    input_text_multi = gr.Text(label='Text:', lines=5, max_lines=10)
                    verbalize_button_multi = gr.Button("Вербалізувати(beta)")
                    speed_multi = gr.Slider(label='Швидкість:', maximum=1.3, minimum=0.7, value=0.9)
                    speaker = gr.Dropdown(
                        label="Голос:", 
                        choices=prompts_list, 
                        value=prompts_list[0] if prompts_list else None
                    )
                    verbalize_button_multi.click(
                        verbalize_handler, 
                        inputs=[input_text_multi], 
                        outputs=[input_text_multi]
                    )
                
                with gr.Column(scale=1):
                    output_audio_multi = gr.Audio(
                        label="Audio:",
                        autoplay=False,
                        streaming=False,
                        type="numpy",
                    )
                    synthesise_button_multi = gr.Button("Синтезувати")
                    multi_text = gr.Text(value='multi', visible=False)
                    synthesise_button_multi.click(
                        synthesize,
                        inputs=[multi_text, input_text_multi, speed_multi, speaker],
                        outputs=[output_audio_multi]
                    )
        
        # Приклади
        with gr.Row():
            examples_table = gr.Dataframe(
                wrap=True, 
                headers=["Текст", "Швидкість"], 
                datatype=["str", "number"], 
                value=examples, 
                interactive=False
            )
            examples_table.select(
                select_example, 
                inputs=[examples_table], 
                outputs=[input_text, speed]
            )
    
    return demo

def initialize(app_context: Dict[str, Any]):
    """
    Ініціалізація головного Gradio інтерфейсу.
    """
    logger = app_context.get('logger', logging.getLogger("GradioMain"))
    
    # Отримати конфігурацію
    config = app_context.get('config')
    if not config or not hasattr(config, 'gradio_main'):
        logger.warning("Конфігурація gradio_main не знайдена")
        return None
    
    main_config = config.gradio_main
    if not main_config.enabled:
        logger.info("Головний Gradio інтерфейс вимкнено")
        return None
    
    # Перевірка залежностей
    if not check_dependencies():
        logger.error("Відсутні залежності для Gradio інтерфейсу")
        return None
    
    # Створити інтерфейс
    demo = create_main_interface(app_context)
    if not demo:
        logger.error("Не вдалося створити Gradio інтерфейс")
        return None
    
    # Додати в контекст
    app_context['gradio_main_demo'] = demo
    
    # Реєстрація в GUI менеджері
    gui_manager = app_context.get('gui_manager')
    if gui_manager:
        try:
            # Імпорт тут, щоб уникнути циркулярних залежностей
            from kod.p_090_gui_manager import GUIInfo, GUIType
            
            gui_info = GUIInfo(
                module_name="p_305_tts_gradio_main",
                gui_type=GUIType.GRADIO,
                display_name="StyleTTS2 Ukrainian (Main)",
                description="Головний інтерфейс StyleTTS2 з підтримкою single/multi speaker",
                priority=5
            )
            gui_manager.register_gui(gui_info)
            logger.info("✅ Головний інтерфейс зареєстровано в GUI менеджері")
        except Exception as e:
            logger.warning(f"Не вдалося зареєструвати GUI: {e}")
    
    # Реєстрація дії для запуску
    action_registry = app_context.get('action_registry')
    if action_registry:
        try:
            def launch_main_interface():
                demo.launch(
                    server_name=main_config.server_name,
                    server_port=main_config.port,
                    share=main_config.share
                )
                return "Головний інтерфейс запущено"
            
            action_registry.register_action(
                action_id="tts.launch_main_interface",
                name="🚀 Запустити головний TTS інтерфейс",
                callback=launch_main_interface,
                description="Запуск головного інтерфейсу StyleTTS2",
                module="p_305_tts_gradio_main",
                category="TTS",
                icon="🎙️"
            )
            logger.info("✅ Дія для запуску головного інтерфейсу зареєстрована")
        except Exception as e:
            logger.warning(f"Не вдалося зареєструвати дію: {e}")
    
    logger.info("✅ Головний Gradio інтерфейс ініціалізовано")
    
    return {
        'demo': demo,
        'config': main_config,
        'launch': lambda: demo.launch(
            server_name=main_config.server_name,
            server_port=main_config.port,
            share=main_config.share
        )
    }

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка головного інтерфейсу."""
    for key in ['gradio_main_demo', 'gradio_main']:
        if key in app_context:
            del app_context[key]
    
    logger = app_context.get('logger')
    if logger:
        logger.info("Головний Gradio інтерфейс зупинено")