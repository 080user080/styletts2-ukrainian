"""
a_1_6_ui_settings_save.py
UI блок: збереження / завантаження налаштувань голосів.
"""

import gradio as gr
from typing import Tuple


def create_settings_save_block() -> Tuple:
    """
    Створює блок з кнопками для експорту / імпорту налаштувань.
    
    Returns:
        (save_download_btn, save_default_btn, load_btn)
    """

    # Повернені кнопки (видимі зверху)
    with gr.Row():
        save_download_btn_top = gr.DownloadButton("💾 Зберегти налаштування мовців")
        save_default_btn_top = gr.Button("📁 Зберегти у папку за замовчуванням")
        load_btn_top = gr.UploadButton(
            "📂 Завантажити налаштування (.txt)",
            file_types=[".txt"],
            file_count="single"
        )
    
    return (
        (save_download_btn_top, save_default_btn_top, load_btn_top)
    )
