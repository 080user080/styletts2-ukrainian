"""
a_8_2_event_registration.py
Реєстрація всіх обробників подій для UI компонентів.
"""

import gradio as gr
from a_8_1_event_handlers import (
    create_btn_start_handler,
    create_export_settings_handler,
    create_save_to_default_handler,
    create_load_settings_handler,
    create_part_slider_handler
)


def register_all_events(
    ui_components: dict,
    pipeline_func,
    output_dir: str
):
    """
    Реєструє всі обробники подій для UI.
    
    Parameters:
        ui_components: словник з усіма UI компонентами (від a_1_ui_main)
        pipeline_func: функція батч-синтезу (a_8_pipeline.batch_synthesize_dialog_events)
        output_dir: директорія для вивідних файлів
    """
    
    # Розпакувати компоненти
    text_input = ui_components['text_input']
    file_input = ui_components['file_input']
    voice_components = ui_components['voice_components']
    speed_components = ui_components['speed_components']
    btn_start = ui_components['btn_start']
    save_option = ui_components['save_option']
    ignore_speed_chk = ui_components['ignore_speed_chk']
    output_audio = ui_components['output_audio']
    part_slider = ui_components['part_slider']
    autoplay_chk = ui_components['autoplay_chk']
    timer_text = ui_components['timer_text']
    start_time_text = ui_components['start_time_text']
    end_time_text = ui_components['end_time_text']
    est_end_time_text = ui_components['est_end_time_text']
    remaining_time_text = ui_components['remaining_time_text']
    parts_progress = ui_components['parts_progress']
    save_buttons_inner = ui_components['save_buttons_inner']
    save_buttons_top = ui_components['save_buttons_top']
    
    save_download_btn_inner, save_default_btn_inner, load_btn_inner = save_buttons_inner
    save_download_btn_top, save_default_btn_top, load_btn_top = save_buttons_top
    
    # ===== 1) Кнопка запуску =====
    btn_inputs = (
        [text_input, file_input] +
        speed_components +
        voice_components +
        [save_option, ignore_speed_chk]
    )
    btn_outputs = [
        output_audio,
        part_slider,
        timer_text,
        start_time_text,
        end_time_text,
        est_end_time_text,
        remaining_time_text,
        parts_progress,
    ]
    
    btn_handler = create_btn_start_handler(pipeline_func)
    btn_start.click(
        fn=btn_handler,
        inputs=btn_inputs,
        outputs=btn_outputs,
        show_progress=False
    )
    
    # ===== 2) Експорт налаштувань (Download) =====
    export_handler = create_export_settings_handler(output_dir)
    
    save_download_btn_inner.click(
        fn=export_handler,
        inputs=voice_components + speed_components,
        outputs=save_download_btn_inner,
    )
    save_download_btn_top.click(
        fn=export_handler,
        inputs=voice_components + speed_components,
        outputs=save_download_btn_top,
    )
    
    # ===== 3) Збереження у папку за замовчуванням =====
    save_default_handler = create_save_to_default_handler(output_dir)
    
    save_default_btn_inner.click(
        fn=save_default_handler,
        inputs=voice_components + speed_components,
        outputs=[],
    )
    save_default_btn_top.click(
        fn=save_default_handler,
        inputs=voice_components + speed_components,
        outputs=[],
    )
    
    # ===== 4) Завантаження налаштувань =====
    load_handler = create_load_settings_handler()
    
    load_btn_inner.upload(
        fn=load_handler,
        inputs=[load_btn_inner] + voice_components + speed_components,
        outputs=voice_components + speed_components,
    )
    load_btn_top.upload(
        fn=load_handler,
        inputs=[load_btn_top] + voice_components + speed_components,
        outputs=voice_components + speed_components,
    )
    
    # ===== 5) Слайдер частин =====
    part_slider_handler = create_part_slider_handler(output_dir)
    
    part_slider.change(
        fn=part_slider_handler,
        inputs=[part_slider, autoplay_chk],
        outputs=[output_audio],
    )
