"""
a_1_6_ui_settings_save.py
UI блок: збереження / завантаження налаштувань голосів.
"""

import gradio as gr


def create_settings_save_block():
    """
    Створює блок з кнопками для експорту / імпорту налаштувань.
    
    Returns три окремих компоненти (NOT tuple of tuple):
        save_download_btn, save_default_btn, load_btn
    """
    with gr.Row():
        save_download_btn = gr.DownloadButton(
            "💾 Завантажити налаштування (.txt)"
        )
        save_default_btn = gr.Button("📁 Зберегти в папку за замовчуванням")
        load_btn = gr.UploadButton(
            "📂 Завантажити налаштування (.txt)",
            file_types=[".txt"],
            file_count="single"
        )
    
    # Повертаємо як три окремих значення, а не кортеж
    return save_download_btn, save_default_btn, load_btn
