"""
a_1_6_ui_settings_save.py
UI блок: збереження / завантаження налаштувань голосів.
"""

import gradio as gr


def create_settings_save_block():
    """
    Створює блок з кнопками для експорту / імпорту налаштувань.
    
    Returns три окремих компоненти:
        save_download_btn, save_default_btn, load_btn
    """
    with gr.Row():
        # Змінено з DownloadButton на звичайну Button
        save_download_btn = gr.Button(
            "💾 Завантажити налаштування (.txt)"
        )
        # Додано File компонент для завантаження
        save_download_file = gr.File(
            visible=False,
            label="Файл налаштувань"
        )
        
        save_default_btn = gr.Button("📁 Зберегти в папку за замовчуванням")
        
        load_btn = gr.UploadButton(
            "📂 Завантажити налаштування (.txt)",
            file_types=[".txt"],
            file_count="single"
        )
    
    # Повертаємо кнопку, файл та інші компоненти
    return save_download_btn, save_download_file, save_default_btn, load_btn
