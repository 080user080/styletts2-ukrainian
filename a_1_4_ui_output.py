"""
a_1_4_ui_output.py
UI блок: аудіо-плеєр, слайдер частин, таблиця часу.
"""

import gradio as gr
from typing import Tuple


def create_output_block() -> Tuple:
    """
    Створює блок з аудіо-плеєром, слайдером частин, таймерами.
    
    Returns:
        (output_audio, part_slider, autoplay_chk,
         timer_text, start_time_text, end_time_text, est_end_time_text,
         remaining_time_text, parts_progress)
    """
    with gr.Accordion('🔊 Поточна частина', open=False):
        autoplay_chk = gr.Checkbox(
            label='Автовідтворення при зміні частини',
            value=False
        )
        output_audio = gr.Audio(
            label='🔊 Поточна частина',
            type='filepath',
            autoplay=False
        )
        part_slider = gr.Slider(
            label='Частина тексту',
            minimum=1, maximum=1, step=1, value=1,
            interactive=False
        )
    
    with gr.Row():
        timer_text = gr.Textbox(
            label="⏱️ Відлік часу (сек)",
            value="0",
            interactive=False
        )
        start_time_text = gr.Textbox(
            label="Початок озвучення",
            interactive=False
        )
        end_time_text = gr.Textbox(
            label="Закінчення озвучення попередньої частини",
            interactive=False
        )
    
    with gr.Row():
        parts_progress = gr.Slider(
            label='Частин для озвучення',
            minimum=0, maximum=1, step=1, value=0,
            interactive=False
        )
    
    with gr.Row():
        est_end_time_text = gr.Textbox(
            label="Прогноз закінчення",
            interactive=False
        )
        remaining_time_text = gr.Textbox(
            label="Час до закінчення",
            interactive=False
        )
    
    return (
        output_audio, part_slider, autoplay_chk,
        timer_text, start_time_text, end_time_text, est_end_time_text,
        remaining_time_text, parts_progress
    )
