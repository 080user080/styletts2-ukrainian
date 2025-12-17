"""
a_1_2_ui_speakers.py
UI блок акордеонів для налаштування голосів і швидкостей #g1–#g30.
"""

import gradio as gr
from typing import Tuple, List


def create_speaker_block(speaker_choices: list) -> Tuple[list, list, list]:
    """
    Створює акордеони для налаштування голосів і швидкостей.
    
    Returns:
        (voice_components, speed_components, accordion_refs)
    
    voice_components: список з 30 gr.Dropdown
    speed_components: список з 30 gr.Slider
    accordion_refs: [acc_1_3, acc_4_12, acc_more, acc_13_21, acc_22_30, acc_opts]
    """
    voice_components = []
    speed_components = []
    accordion_refs = []
    
    def _speaker_cell(i: int):
        """Допоміжна функція: створює dropdown + slider для одного спікера."""
        dd = gr.Dropdown(
            label=f'Голос для #g{i}',
            choices=speaker_choices,
            value=speaker_choices[0],
            visible=True
        )
        sv = gr.Slider(
            0.7, 1.3,
            value=0.88,
            label=f'Швидкість для #g{i}',
            visible=True
        )
        voice_components.append(dd)
        speed_components.append(sv)
    
    # ===== ГРУПА 1: #g1–#g3 (відкритий) =====
    with gr.Accordion("Спікери #g1–#g3", open=True) as acc_1_3:
        with gr.Row():
            for i in (1, 2, 3):
                with gr.Column():
                    _speaker_cell(i)
    accordion_refs.append(acc_1_3)
    
    # ===== ГРУПА 2: #g4–#g12 (закритий) =====
    with gr.Accordion("Спікери #g4–#g12", open=False) as acc_4_12:
        with gr.Row():
            for i in (4, 5, 6):
                with gr.Column():
                    _speaker_cell(i)
        with gr.Row():
            for i in (7, 8, 9):
                with gr.Column():
                    _speaker_cell(i)
        with gr.Row():
            for i in (10, 11, 12):
                with gr.Column():
                    _speaker_cell(i)
    accordion_refs.append(acc_4_12)
    
    # ===== ГРУПА 3: Додаткові голоси (закритий) =====
    with gr.Accordion("Додаткові голоси", open=False) as acc_more:
        
        # Підгрупа: #g13–#g21
        with gr.Accordion("Спікери #g13–#g21", open=False) as acc_13_21:
            with gr.Row():
                for i in (13, 14, 15):
                    with gr.Column():
                        _speaker_cell(i)
            with gr.Row():
                for i in (16, 17, 18):
                    with gr.Column():
                        _speaker_cell(i)
            with gr.Row():
                for i in (19, 20, 21):
                    with gr.Column():
                        _speaker_cell(i)
        accordion_refs.append(acc_13_21)
        
        # Підгрупа: #g22–#g30
        with gr.Accordion("Спікери #g22–#g30", open=False) as acc_22_30:
            with gr.Row():
                for i in (22, 23, 24):
                    with gr.Column():
                        _speaker_cell(i)
            with gr.Row():
                for i in (25, 26, 27):
                    with gr.Column():
                        _speaker_cell(i)
            with gr.Row():
                for i in (28, 29, 30):
                    with gr.Column():
                        _speaker_cell(i)
        accordion_refs.append(acc_22_30)
    
    accordion_refs.append(acc_more)
    
    # Порядок accordion_refs: [acc_1_3, acc_4_12, acc_13_21, acc_22_30, acc_more]
    return voice_components, speed_components, accordion_refs
