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


DEFAULT_VISIBLE = 3  # кількість спікерів за замовчуванням


def create_multi_dialog_tab(speaker_choices: list) -> Tuple:
    """
    Створює вкладку 'Multi Dialog' з усіма компонентами.
    
    Returns:
        (text_input, file_input, voice_components, speed_components,
         btn_start, save_option, ignore_speed_chk,
         output_audio, part_slider, autoplay_chk,
         timer_text, start_time_text, end_time_text, est_end_time_text,
         remaining_time_text, parts_progress,
         accordion_refs,
         save_buttons_inner, save_buttons_top)
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
    save_buttons_inner, save_buttons_top = create_settings_save_block()
    
    return (
        text_input, file_input,
        voice_components, speed_components,
        btn_start, save_option, ignore_speed_chk,
        output_audio, part_slider, autoplay_chk,
        timer_text, start_time_text, end_time_text, est_end_time_text,
        remaining_time_text, parts_progress,
        accordion_refs,
        save_buttons_inner, save_buttons_top
    )


def setup_text_change_handlers(
    text_input: gr.Textbox,
    file_input: gr.File,
    voice_components: list,
    speed_components: list,
    accordion_refs: list
):
    """
    Налаштовує обробники зміни тексту для автовизначення видимості спікерів.
    """
    _g_tag_re = re.compile(r'#g\s*([1-9]|[12]\d|30)', re.IGNORECASE)
    
    def _max_g_tag_from_text(s: str | None) -> int:
        if not s:
            return DEFAULT_VISIBLE
        m = [int(x) for x in _g_tag_re.findall(s)]
        if not m:
            return DEFAULT_VISIBLE
        return max(1, min(30, max(m)))
    
    def _visibility_updates(n: int):
        # 30 dropdown + 30 sliders
        updates = []
        for i in range(1, 31):
            show = (i <= n)
            updates.append(gr.update(visible=show))  # dropdown
        for i in range(1, 31):
            show = (i <= n)
            updates.append(gr.update(visible=show))  # slider
        
        # Акордеони повинні бути ВИДИМІ та ВІДКРИТІ, якщо в їхньому діапазоні є хоч один спікер
        # acc_1_3 (g1-g3), acc_4_12 (g4-g12), acc_more, acc_13_21 (g13-g21), acc_22_30 (g22-g30)
        acc_updates = [
            gr.update(open=(n >= 1)),     # acc_1_3: відкрити якщо n >= 1
            gr.update(open=(n >= 4)),     # acc_4_12: відкрити якщо n >= 4
            gr.update(open=(n >= 13)),    # acc_more: відкрити якщо n >= 13
            gr.update(open=(n >= 13)),    # acc_13_21: відкрити якщо n >= 13
            gr.update(open=(n >= 22)),    # acc_22_30: відкрити якщо n >= 22
        ]
        return updates + acc_updates
    
    def on_text_changed(txt):
        n = _max_g_tag_from_text(txt)
        return _visibility_updates(n)
    
    def on_file_changed(path_like):
        p = None
        if isinstance(path_like, str):
            p = path_like
        elif isinstance(path_like, dict):
            p = path_like.get("name") or path_like.get("path")
        if not p or not os.path.exists(p):
            return _visibility_updates(DEFAULT_VISIBLE)
        try:
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read()
        except Exception:
            txt = ""
        n = _max_g_tag_from_text(txt)
        return _visibility_updates(n)
    
    # accordion_refs порядок: [acc_1_3, acc_4_12, acc_13_21, acc_22_30, acc_more]
    text_input.change(
        fn=on_text_changed,
        inputs=[text_input],
        outputs=(voice_components + speed_components + accordion_refs)
    )
    
    file_input.change(
        fn=on_file_changed,
        inputs=[file_input],
        outputs=(voice_components + speed_components + accordion_refs)
    )
