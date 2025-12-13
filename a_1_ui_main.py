"""
a_1_ui_main.py
Головний UI: складає разом усі блоки.
"""

import re
import os
import gradio as gr
from typing import Tuple

from a_1_1_ui_text_input import create_text_input_block
from a_1_2_ui_speakers import create_speaker_block
from a_1_3_ui_controls import create_controls_block, SAVE_CHOICES
from a_1_4_ui_output import create_output_block
from a_1_5_ui_syntax_help import create_syntax_help_block
from a_1_6_ui_settings_save import create_settings_save_block
from a_1_7_ui_accordion_manager import (
    find_max_speaker_tag,
    get_accordion_visibility,
    read_text_from_file,
    get_max_speaker_from_input
)


DEFAULT_VISIBLE = 3  # кількість спікерів за замовчуванням


def create_multi_dialog_tab(speaker_choices: list) -> Tuple:
    """
    Створює вкладку 'Multi Dialog' з усіма компонентами.
    
    Returns (19 значень):
        1. text_input
        2. file_input
        3-32. voice_components (30)
        33-62. speed_components (30)
        63. btn_start
        64. save_option
        65. ignore_speed_chk
        66. output_audio
        67. part_slider
        68. autoplay_chk
        69. timer_text
        70. start_time_text
        71. end_time_text
        72. est_end_time_text
        73. remaining_time_text
        74. parts_progress
        75. accordion_refs (список з 5 акордеонів)
        76. save_buttons (кортеж з 3 кнопок)
    
    Всього: 2 + 30 + 30 + 1 + 1 + 1 + 9 + 1 + 1 + 3 = 79 (але групуємо)
    
    Повертаємо: 1 + 1 + 30 + 30 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 3 = 19 значень
    """
    
    # Блок 1: Введення тексту
    text_input, file_input = create_text_input_block()
    
    # Блок 2: Спікери (акордеони)
    voice_components, speed_components, accordion_refs = create_speaker_block(speaker_choices)
    
    # Блок 3: Керування (кнопка запуску, опції)
    btn_start, save_option, ignore_speed_chk = create_controls_block()
    
    # Блок 4: Вивід (аудіо, слайдер, таймери)
    (output_audio, part_slider, autoplay_chk,
     timer_text, start_time_text, end_time_text, est_end_time_text,
     remaining_time_text, parts_progress) = create_output_block()
    
    # Блок 5: Синтаксис
    create_syntax_help_block()
    
    # Блок 6: Збереження/завантаження
    save_buttons = create_settings_save_block()
    
    # Повертаємо як словник для зручності
    return {
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
        'accordion_refs': accordion_refs,
        'save_buttons': save_buttons,
    }


def setup_text_change_handlers(
    text_input: gr.Textbox,
    file_input: gr.File,
    voice_components: list,
    speed_components: list,
    accordion_refs: list
):
    """
    Налаштовує обробники зміни тексту для автовизначення видимості акордеонів.
    На основі максимального номера спікера #gN показує потрібні акордеони.
    """
    
    def on_text_changed(txt):
        """Обробник зміни текстового поля."""
        max_speaker = find_max_speaker_tag(txt)
        print(f"DEBUG: text changed, max_speaker={max_speaker}")
        
        if max_speaker == 0:
            # Якщо нема тегів — показати все за замовчуванням
            return _get_accordion_updates(3, accordion_refs)
        
        return _get_accordion_updates(max_speaker, accordion_refs)
    
    def on_file_changed(file_obj):
        """Обробник зміни файлу."""
        if not file_obj:
            return _get_accordion_updates(3, accordion_refs)
        
        # Отримати шлях до файлу
        file_path = None
        if isinstance(file_obj, str):
            file_path = file_obj
        elif isinstance(file_obj, dict):
            file_path = file_obj.get("name") or file_obj.get("path")
        
        file_text = read_text_from_file(file_path) if file_path else ""
        max_speaker = find_max_speaker_tag(file_text)
        print(f"DEBUG: file changed, max_speaker={max_speaker}")
        
        if max_speaker == 0:
            return _get_accordion_updates(3, accordion_refs)
        
        return _get_accordion_updates(max_speaker, accordion_refs)
    
    text_input.change(
        fn=on_text_changed,
        inputs=[text_input],
        outputs=accordion_refs
    )
    
    file_input.change(
        fn=on_file_changed,
        inputs=[file_input],
        outputs=accordion_refs
    )


def _get_accordion_updates(max_speaker: int, accordion_refs: list) -> list:
    """
    Повертає оновлення для акордеонів на основі максимального спікера.
    
    accordion_refs порядок: [acc_1_3, acc_4_12, acc_13_21, acc_22_30, acc_more]
    """
    visibility = get_accordion_visibility(max_speaker)
    
    updates = [
        gr.update(visible=visibility["acc_1_3"]),     # [0] acc_1_3
        gr.update(visible=visibility["acc_4_12"]),    # [1] acc_4_12
        gr.update(visible=visibility["acc_13_21"]),   # [2] acc_13_21
        gr.update(visible=visibility["acc_22_30"]),   # [3] acc_22_30
        gr.update(visible=visibility["acc_more"]),    # [4] acc_more
    ]
    
    print(f"DEBUG: accordion visibility updates: acc_1_3={visibility['acc_1_3']}, "
          f"acc_4_12={visibility['acc_4_12']}, acc_13_21={visibility['acc_13_21']}, "
          f"acc_22_30={visibility['acc_22_30']}, acc_more={visibility['acc_more']}")
    
    return updates
