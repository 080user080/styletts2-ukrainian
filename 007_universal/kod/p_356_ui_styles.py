# p_356_ui_styles.py
"""
Стилі та теми для розширеного UI Multi Dialog TTS.
Кольорова схема #b54d04, тема Gradio та CSS стилі.
"""

import gradio as gr
from typing import Dict, Any, Optional

def get_orange_theme() -> gr.Theme:
    """
    Створює та повертає оранжеву тему з основним кольором #b54d04.
    Використовує мінімальну кількість параметрів для сумісності з Gradio 3.x.
    """
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.orange,
        secondary_hue=gr.themes.colors.orange,
    ).set(
        # === ТОЧНИЙ КОЛІР #b54d04 ===
        # Тільки основні параметри, які підтримуються Gradio 3.x
        
        # Кнопки первинні
        button_primary_background_fill="linear-gradient(90deg, #b54d04, #f08030)",
        button_primary_background_fill_hover="linear-gradient(90deg, #d85a05, #b54d04)",
        button_primary_text_color="#ffffff",
        
        # Акценти блоків
        block_title_text_color="#b54d04",
        block_label_text_color="#b54d04",
        
        # Інтерактивні елементи вводу (обмежена підтримка)
        input_background_fill="#fff3e0",
        
        # Слайдер
        slider_color="#b54d04",
    )

def get_custom_css() -> str:
    """
    Повертає додаткові CSS стилі для UI.
    Більшість стилів перенесено сюди, оскільки Gradio 3.x має обмежену підтримку тем.
    """
    return """
    /* Основні оранжеві акценти */
    .orange-accent {
        color: #b54d04 !important;
    }
    
    /* Кнопки */
    .orange-button {
        background: linear-gradient(90deg, #b54d04, #f08030) !important;
        color: white !important;
        border: 1px solid #d85a05 !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    .orange-button:hover {
        background: linear-gradient(90deg, #d85a05, #b54d04) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(233, 101, 8, 0.3) !important;
    }
    
    /* Випадаючі списки */
    .gradio-dropdown {
        border: 1px solid #b54d04 !important;
        border-radius: 4px !important;
    }
    
    .gradio-dropdown:hover {
        border-color: #d85a05 !important;
        box-shadow: 0 0 0 1px rgba(233, 101, 8, 0.2) !important;
    }
    
    /* Текстові поля */
    textarea, input[type="text"] {
        border: 1px solid #b54d04 !important;
        border-radius: 4px !important;
        background: #fff3e0 !important;
    }
    
    textarea:hover, input[type="text"]:hover {
        border-color: #d85a05 !important;
        box-shadow: 0 0 0 1px rgba(233, 101, 8, 0.2) !important;
    }
    
    /* Чекбокси та радіо кнопки через CSS */
    input[type="checkbox"], input[type="radio"] {
        accent-color: #b54d04 !important;
    }
    
    /* Слайдери */
    input[type="range"]::-webkit-slider-thumb {
        background: #b54d04 !important;
        border: 2px solid white !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    }
    
    input[type="range"]::-moz-range-thumb {
        background: #b54d04 !important;
        border: 2px solid white !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* Аккордеони */
    .accordion > label {
        background: linear-gradient(90deg, #fff3e0, #ffffff) !important;
        border-left: 4px solid #b54d04 !important;
        color: #b54d04 !important;
        font-weight: bold !important;
        border-radius: 4px !important;
    }
    
    /* Вкладки */
    .tab-nav button {
        color: #666 !important;
        border-bottom: 3px solid transparent !important;
    }
    
    .tab-nav button.selected {
        color: #b54d04 !important;
        border-bottom: 3px solid #b54d04 !important;
        font-weight: bold !important;
    }
    
    /* Статусні повідомлення */
    .success-box {
        background: linear-gradient(90deg, #e8f5e9, #ffffff) !important;
        border-left: 4px solid #4CAF50 !important;
        padding: 10px !important;
        border-radius: 4px !important;
        margin: 10px 0 !important;
    }
    
    .warning-box {
        background: linear-gradient(90deg, #fff3e0, #ffffff) !important;
        border-left: 4px solid #ff9800 !important;
        padding: 10px !important;
        border-radius: 4px !important;
        margin: 10px 0 !important;
    }
    
    .error-box {
        background: linear-gradient(90deg, #ffebee, #ffffff) !important;
        border-left: 4px solid #f44336 !important;
        padding: 10px !important;
        border-radius: 4px !important;
        margin: 10px 0 !important;
    }
    
    /* Картки прикладів */
    .example-card {
        border: 1px solid #e0e0e0 !important;
        border-radius: 8px !important;
        padding: 15px !important;
        margin: 10px 0 !important;
        background: #f9f9f9 !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
    }
    
    .example-card:hover {
        border-color: #b54d04 !important;
        box-shadow: 0 4px 12px rgba(233, 101, 8, 0.1) !important;
        transform: translateY(-2px) !important;
    }
    
    /* Анімація завантаження */
    @keyframes orange-pulse {
        0% { box-shadow: 0 0 0 0 rgba(233, 101, 8, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(233, 101, 8, 0); }
        100% { box-shadow: 0 0 0 0 rgba(233, 101, 8, 0); }
    }
    
    .loading-pulse {
        animation: orange-pulse 2s infinite !important;
    }
    """

def get_simple_theme() -> gr.Theme:
    """
    Повертає просту тему з мінімальною кількістю параметрів.
    Використовується як fallback.
    """
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.orange
    )

# Константи для використання в інших модулях
ORANGE_PRIMARY = "#b54d04"
ORANGE_SECONDARY = "#f08030"
ORANGE_LIGHT = "#fff3e0"
ORANGE_DARK = "#d85a05"

CSS_CLASSES = {
    'button': 'orange-button',
    'accent': 'orange-accent',
    'success': 'success-box',
    'warning': 'warning-box',
    'error': 'error-box',
    'example': 'example-card',
    'loading': 'loading-pulse',
}