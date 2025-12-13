import gradio as gr
from typing import Dict, Any

def get_orange_theme() -> gr.Theme:
    """Повертає оранжеву тему."""
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.orange,
        secondary_hue=gr.themes.colors.orange,
    ).set(
        button_primary_background_fill="linear-gradient(90deg, #185900, #f08030)",
        button_primary_background_fill_hover="linear-gradient(90deg, #d85a05, #185900)",
        button_primary_text_color="#ffffff",
        block_title_text_color="#185900",
        block_label_text_color="#185900",
        input_background_fill="#fff3e0",
        input_border_color="#185900",
        slider_color="#185900",
        checkbox_background_color="#185900",
        checkbox_border_color="#185900",
    )

def get_css_styles() -> str:
    """Повертає CSS стилі."""
    return """
    .orange-accent { color: #185900 !important; }
    .orange-button { background: linear-gradient(90deg, #185900, #f08030) !important; }
    .speaker-group { border-left: 4px solid #185900; padding-left: 10px; }
    """

def prepare_config_models():
    """Конфігурація не потрібна."""
    return {}