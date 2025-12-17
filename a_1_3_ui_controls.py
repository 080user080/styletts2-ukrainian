"""
a_1_3_ui_controls.py
UI блок: кнопка запуску, опції збереження (в спойлері), чекбокс ігнорування швидкості.
"""

import gradio as gr
from typing import Tuple


SAVE_CHOICES = ['Зберегти всі частини озвученого тексту', 'Без збереження']


def create_controls_block() -> Tuple[gr.Button, gr.Radio, gr.Checkbox]:
    """
    Створює блок з кнопкою запуску, опціями збереження (в Accordion), 
    чекбоксом ігнорування швидкості.
    
    Returns:
        (btn_start, save_option, ignore_speed_chk)
    """
    btn_start = gr.Button('▶ Розпочати')
    
    with gr.Accordion("Опції збереження", open=False):
        save_option = gr.Radio(
            choices=SAVE_CHOICES,
            label='Опції збереження',
            value=SAVE_CHOICES[1]
        )
    
    ignore_speed_chk = gr.Checkbox(
        label='Ігнорувати швидкість',
        value=False
    )
    
    return btn_start, save_option, ignore_speed_chk
