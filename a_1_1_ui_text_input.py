"""
a_1_1_ui_text_input.py
UI блок для введення тексту або вибору файлу.
"""

import gradio as gr


def create_text_input_block():
    """
    Створює блок введення тексту / вибору файлу.
    
    Returns:
        (text_input: gr.Textbox, file_input: gr.File)
    """
    text_input = gr.Textbox(
        label='📋 Введіть текст або залиште порожнім і оберіть файл',
        lines=10,
        placeholder='Вставте текст тут...'
    )
    
    file_input = gr.File(
        label='Або оберіть текстовий файл',
        type='filepath'
    )
    
    return text_input, file_input
