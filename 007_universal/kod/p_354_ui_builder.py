import logging
from typing import Dict, Any, Tuple
import gradio as gr
from p_357_ui_utils import create_output_directory
from p_356_ui_styles import get_orange_theme, get_css_styles
from p_355_ui_handlers import UIEventHandlers

class AdvancedUIBuilder:
    """Будує розширений інтерфейс."""
    
    def __init__(self, 
                 tts_engine: Any,
                 dialog_parser: Any,
                 sfx_handler: Any,
                 logger: logging.Logger = None):
        self.logger = logger or logging.getLogger("UIBuilder")
        self.handlers = UIEventHandlers(
            tts_engine=tts_engine,
            dialog_parser=dialog_parser,
            sfx_handler=sfx_handler,
            logger=logger
        )
        self.available_voices = tts_engine.get_available_voices()
        self.available_sfx = sfx_handler.get_available_sfx_ids()
        self.output_dir = create_output_directory()
        
        self.logger.info(f"📂 Папка для збереження: {self.output_dir}")
    
    def build(self) -> gr.Blocks:
        """Будує весь інтерфейс."""
        theme = get_orange_theme()
        css = get_css_styles()
        
        with gr.Blocks(title="TTS Multi Dialog Advanced", theme=theme, css=css) as demo:
            # Заголовок
            self._add_header()
            
            # Вхід
            text_input, file_input = self._add_input_section()
            
            # Спікери
            voice_dropdowns, speed_sliders = self._add_speakers_section()
            
            # Опції
            save_option, ignore_speed_chk = self._add_options_section()
            
            # Кнопки
            btn_start, btn_export = self._add_buttons_section()
            
            # Прогрес
            audio_output, part_slider, timer, remaining, progress_slider, file_info = self._add_progress_section()
            
            # Довідка
            self._add_help_section()
            
            # Обробники
            self._setup_event_handlers(
                btn_start, btn_export, text_input, file_input,
                voice_dropdowns, speed_sliders, save_option, ignore_speed_chk,
                audio_output, part_slider, timer, remaining, progress_slider, file_info
            )
        
        return demo
    
    def _add_header(self):
        """Додає заголовок."""
        gr.Markdown(f"""
        # 🎙️ TTS Multi Dialog - Розширений режим
        
        **Введіть сценарій** з тегами або завантажте файл:
        - `#gN: текст` — озвучити голосом №N (1-30)
        - `#gN_fast` / `#gN_slow` — швидкість
        - `#sfx_bell` — звуковий ефект
        
        ⚠️ **Увага:** Оберіть файл .txt, а не директорію!
        """)
    
    def _add_input_section(self) -> Tuple[gr.Textbox, gr.File]:
        """Додає секцію вводу."""
        with gr.Row():
            with gr.Column(scale=2):
                text_input = gr.Textbox(
                    label="📋 Сценарій",
                    lines=10,
                    placeholder="#g1: Привіт!\n#g2_fast: Як справи?\n#sfx_bell"
                )
            with gr.Column(scale=1):
                file_input = gr.File(
                    label="📂 Або файл .txt", 
                    type='filepath',
                    file_types=['.txt']  # Обмежуємо тільки текстовими файлами
                )
        
        return text_input, file_input
    
    def _add_speakers_section(self) -> Tuple[list, list]:
        """Додає спікери в акордеонах."""
        voice_dropdowns = []
        speed_sliders = []
        
        with gr.Accordion("⚙️ Налаштування спікерів", open=False):
            # Спікери 1-3
            with gr.Accordion("Спікери #g1-#g3", open=True):
                with gr.Row():
                    for i in range(1, 4):
                        with gr.Column():
                            voice_dropdowns.append(
                                gr.Dropdown(
                                    label=f"🎙️ Голос #g{i}",
                                    choices=self.available_voices,
                                    value=self.available_voices[0] if self.available_voices else "default"
                                )
                            )
                            speed_sliders.append(
                                gr.Slider(0.7, 1.3, value=0.88, label=f"⏱️ #g{i}", step=0.01)
                            )
            
            # Спікери 4-30 (скомпоновано)
            with gr.Accordion("Спікери #g4-#g30", open=False):
                for row_start in range(4, 31, 3):
                    with gr.Row():
                        for i in range(row_start, min(row_start + 3, 31)):
                            with gr.Column():
                                voice_dropdowns.append(
                                    gr.Dropdown(
                                        label=f"🎙️ #g{i}",
                                        choices=self.available_voices,
                                        value=self.available_voices[0] if self.available_voices else "default"
                                    )
                                )
                                speed_sliders.append(
                                    gr.Slider(0.7, 1.3, value=0.88, label=f"⏱️ #g{i}", step=0.01)
                                )
        
        return voice_dropdowns, speed_sliders
    
    def _add_options_section(self) -> Tuple[gr.Radio, gr.Checkbox]:
        """Додає опції."""
        with gr.Row():
            save_option = gr.Radio(
                ["Зберегти всі частини", "Без збереження"],
                label="💾 Збереження",
                value="Без збереження"  # За замовчуванням не зберігаємо
            )
            ignore_speed_chk = gr.Checkbox(
                label="⚡ Ігнорувати швидкість",
                value=False
            )
        return save_option, ignore_speed_chk
    
    def _add_buttons_section(self) -> Tuple[gr.Button, gr.Button]:
        """Додає кнопки."""
        with gr.Row():
            btn_start = gr.Button("▶️ Розпочати синтез", variant="primary", scale=2)
            btn_export = gr.Button("💾 Експорт налаштувань", scale=1)
        return btn_start, btn_export
    
    def _add_progress_section(self) -> Tuple:
        """Додає секцію прогресу."""
        with gr.Accordion("🔊 Результати синтезу", open=True):
            with gr.Row():
                audio_output = gr.Audio(label="🔊 Поточна частина", type='filepath')
                part_slider = gr.Slider(label="📍 Номер частини", minimum=1, maximum=1, step=1, value=1)
            
            with gr.Row():
                timer = gr.Textbox(label="⏱️ Час", value="0", interactive=False)
                remaining = gr.Textbox(label="⏳ Залишилось", interactive=False)
            
            progress_slider = gr.Slider(label="📈 Прогрес", minimum=0, maximum=1, step=1, value=0, interactive=False)
            file_info = gr.Textbox(label="📄 Статус", value="Готово до синтезу", interactive=False)
        
        return audio_output, part_slider, timer, remaining, progress_slider, file_info
    
    def _add_help_section(self):
        """Додає довідку."""
        with gr.Accordion("📖 Синтаксис тегів", open=False):
            sfx_list = ', '.join(self.available_sfx) if self.available_sfx else 'Немає'
            gr.Markdown(f"""
            **Синтаксис:**
            - `#gN: текст` - озвучити голосом №N
            - `#gN_slow` - медленно (0.80)
            - `#gN_fast` - швидко (1.20)
            
            **Доступні SFX:** {sfx_list}
            
            **Увага:** При виборі файлу оберіть файл .txt, а не папку!
            """)
    
    def _setup_event_handlers(self, btn_start, btn_export, text_input, file_input,
                             voice_dropdowns, speed_sliders, save_option, ignore_speed_chk,
                             audio_output, part_slider, timer, remaining, progress_slider, file_info):
        """Налаштовує обробники."""
        all_inputs = [
            text_input, file_input,
            *speed_sliders,
            *voice_dropdowns,
            save_option,
            ignore_speed_chk
        ]
        
        outputs = [
            audio_output,
            part_slider,
            timer,
            remaining,
            progress_slider,
            file_info
        ]
        
        btn_start.click(
            fn=self.handlers.synthesize_batch,
            inputs=all_inputs,
            outputs=outputs,
            show_progress=False
        )
        
        btn_export.click(
            fn=self.handlers.export_settings,
            inputs=voice_dropdowns + speed_sliders,
            outputs=btn_export
        )

def prepare_config_models():
    """Конфігурація не потрібна."""
    return {}