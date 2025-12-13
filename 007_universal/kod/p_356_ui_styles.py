"""
p_356_ui_styles.py - Стилі для UI компонентів.
"""

import gradio as gr
from typing import Dict, Any
import logging

class UIStyles:
    """Контейнер стилів для UI."""
    
    @staticmethod
    def get_styles():
        """Повертає словник стилів."""
        return {
            'primary_color': '#185900',
            'secondary_color': '#f08030',
            'text_color': '#333333',
            'background_color': '#ffffff',
            'border_radius': '8px',
            'font_family': 'Arial, sans-serif',
            'font_size': '14px'
        }
    
    @staticmethod
    def get_button_styles():
        """Стилі для кнопок."""
        return {
            'primary': {
                'background': 'linear-gradient(90deg, #185900, #f08030)',
                'color': '#ffffff',
                'border': 'none',
                'border_radius': '6px',
                'padding': '8px 16px',
                'font_weight': 'bold'
            },
            'secondary': {
                'background': '#f0f0f0',
                'color': '#333333',
                'border': '1px solid #ccc',
                'border_radius': '6px',
                'padding': '8px 16px'
            }
        }
    
    @staticmethod
    def get_input_styles():
        """Стилі для полів вводу."""
        return {
            'background': '#fff3e0',
            'border': '1px solid #185900',
            'border_radius': '4px',
            'padding': '6px 10px',
            'focus': {
                'border_color': '#f08030',
                'box_shadow': '0 0 0 2px rgba(24, 89, 0, 0.2)'
            }
        }

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

def initialize(app_context: Dict[str, Any]) -> UIStyles:
    """Ініціалізація стилів UI."""
    logger = app_context.get('logger', logging.getLogger("UIStyles"))
    logger.info("🎨 Ініціалізація стилів UI...")
    
    styles = UIStyles()
    app_context['ui_styles'] = styles
    
    logger.info("✅ Стилі UI готові")
    return styles

def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка модуля."""
    if 'ui_styles' in app_context:
        del app_context['ui_styles']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("Стилі UI зупинено")