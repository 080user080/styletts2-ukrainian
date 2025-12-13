"""
a_9_main.py
Головний файл: запуск всієї програми.
"""

import os
from datetime import datetime
import gradio as gr

from app import prompts_list
from a_1_ui_main import create_multi_dialog_tab, setup_text_change_handlers
from a_8_pipeline import batch_synthesize_dialog_events
from a_8_2_event_registration import register_all_events


# Налаштування директорії вивіду
OUTPUT_DIR_BASE = "output_audio"

def make_session_output_dir(base: str = OUTPUT_DIR_BASE) -> str:
    """Створює директорію для сесії з timestamp-ом."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(base, ts)
    try:
        os.makedirs(out, exist_ok=True)
    except Exception:
        out = base
        os.makedirs(out, exist_ok=True)
    return out

# Глобальна директорія для всієї сесії
OUTPUT_DIR = make_session_output_dir()


def main():
    """Основна функція запуску."""
    
    # Створити Gradio Blocks інтерфейс
    with gr.Blocks(title="Batch TTS з Прогресом") as demo:
        with gr.Tabs():
            with gr.TabItem('Multi Dialog'):
                
                # Створити всі компоненти UI
                (text_input, file_input,
                 voice_components, speed_components,
                 btn_start, save_option, ignore_speed_chk,
                 output_audio, part_slider, autoplay_chk,
                 timer_text, start_time_text, end_time_text, est_end_time_text,
                 remaining_time_text, parts_progress,
                 accordion_refs,
                 save_buttons_inner, save_buttons_top) = create_multi_dialog_tab(prompts_list)
                
                # Налаштувати обробники зміни тексту (автовидимість спікерів)
                setup_text_change_handlers(
                    text_input, file_input,
                    voice_components, speed_components,
                    accordion_refs
                )
                
                # Підготувати словник з усіма компонентами для реєстрації подій
                ui_components = {
                    'text_input': text_input,
                    'file_input': file_input,
                    'voice_components': voice_components,
                    'speed_components': speed_components,
                    'btn_start': btn_start,
                    'save_option': save_option,
                    'ignore_speed_chk': ignore_speed_chk,
                    'output_audio': output_audio,
                    'part_slider': part_slider,
                    'autoplay_chk': autoplay_chk,
                    'timer_text': timer_text,
                    'start_time_text': start_time_text,
                    'end_time_text': end_time_text,
                    'est_end_time_text': est_end_time_text,
                    'remaining_time_text': remaining_time_text,
                    'parts_progress': parts_progress,
                    'save_buttons_inner': save_buttons_inner,
                    'save_buttons_top': save_buttons_top,
                }
                
                # Реєструвати всі обробники подій
                # Передати pipeline_func з OUTPUT_DIR в замиканні
                def pipeline_with_output_dir(text_input, file_input, speeds, voices, save_opt, ignore_speed):
                    return batch_synthesize_dialog_events(
                        text_input, file_input, speeds, voices, save_opt, ignore_speed, OUTPUT_DIR
                    )
                
                register_all_events(
                    ui_components,
                    pipeline_with_output_dir,
                    OUTPUT_DIR
                )
    
    # Запустити интерфейс
    demo.queue().launch()


if __name__ == '__main__':
    main()
