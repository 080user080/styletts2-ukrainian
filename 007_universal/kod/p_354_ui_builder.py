# p_354_ui_builder.py
"""
Конструктор розширеного UI для Multi Dialog TTS.
Побудова розмітки та створення всіх UI компонентів.
"""

import gradio as gr
from typing import Dict, Any, List, Tuple
import logging
import os

def create_advanced_interface(app_context: Dict[str, Any], theme: gr.Theme) -> gr.Blocks:
    """
    Створює розширений Gradio інтерфейс для Multi Dialog TTS.
    
    Args:
        app_context: Контекст додатку з компонентами
        theme: Тема для інтерфейсу
        
    Returns:
        Об'єкт gr.Blocks з готовим інтерфейсом
    """
    logger = app_context.get('logger', logging.getLogger("UI_Builder"))
    logger.info("🛠️  Побудова інтерфейсу розширеного UI...")
    
    # Отримання необхідних компонентів
    tts_engine = app_context.get('tts_engine')
    dialog_parser = app_context.get('dialog_parser')
    sfx_handler = app_context.get('sfx_handler')
    
    # Перевірка наявності компонентів
    if not all([tts_engine, dialog_parser, sfx_handler]):
        raise RuntimeError("Не знайдено обов'язкові компоненти (tts_engine, dialog_parser, sfx_handler)")
    
    # Отримання доступних голосів та SFX
    available_voices = tts_engine.get_available_voices()
    available_sfx = sfx_handler.get_available_sfx_ids()
    
    # Створення папки для сесії
    import time
    output_dir = os.path.join(os.getcwd(), "output_audio", f"session_{int(time.time())}")
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"📊 UI з голосами: {len(available_voices)}, SFX: {len(available_sfx)}")
    
    # ===== СТВОРЕННЯ КОМПОНЕНТІВ ІНТЕРФЕЙСУ =====
    
    # Імпорт обробників подій
    from p_355_ui_handlers import create_batch_synthesize_handler, create_export_settings_handler
    
    # Створення обробників з контекстом
    batch_synthesize_handler = create_batch_synthesize_handler(app_context, output_dir)
    export_settings_handler = create_export_settings_handler(app_context, output_dir)
    
    # ===== ПОБУДОВА ІНТЕРФЕЙСУ =====
    
    with gr.Blocks(
        title="TTS Multi Dialog Advanced", 
        theme=theme, 
        css="""
        .orange-accent { color: #b54d04 !important; }
        .orange-button { background: linear-gradient(90deg, #b54d04, #f08030) !important; }
        """
    ) as demo:
        
        # === ЗАГОЛОВОК ===
        gr.Markdown("""
        # 🎙️ TTS Multi Dialog - Розширений режим
        
        **Введіть сценарій** з тегами або завантажте файл:
        - `#gN: текст` — озвучити голосом №N (1-30)
        - `#gN_fast` / `#gN_slow` — швидкість (1.20 / 0.80)
        - `#gN_slow95` / `#gN_fast110` — точна швидкість (0.95 / 1.10)
        - `#sfx_bell` — звуковий ефект
        """)
        
        # === ВХІДНІ ДАНІ ===
        with gr.Row():
            with gr.Column(scale=2):
                text_input = gr.Textbox(
                    label="📋 Сценарій (або залиште порожнім і оберіть файл)",
                    lines=10,
                    placeholder="#g1: Привіт!\n#g2_fast: Як справи?\n#g1_slow95: До побачення!"
                )
            
            with gr.Column(scale=1):
                file_input = gr.File(label="📂 Або файл .txt", type='filepath')
        
        # === СПІКЕРИ (акордеони) ===
        voice_dropdowns = []
        speed_sliders = []
        
        # Група 1: #g1-#g3
        with gr.Accordion("⚙️ Налаштування спікерів", open=False):
            with gr.Accordion("Спікери #g1-#g3", open=True):
                with gr.Row():
                    for i in range(1, 4):
                        with gr.Column():
                            voice_dropdowns.append(
                                gr.Dropdown(
                                    label=f"🎙️ Голос #g{i}",
                                    choices=available_voices,
                                    value=available_voices[0] if available_voices else "default"
                                )
                            )
                            speed_sliders.append(
                                gr.Slider(0.7, 1.3, value=0.88, label=f"⏱️ Швидкість #g{i}", step=0.01)
                            )
            
            # Група 2: #g4-#g12
            with gr.Accordion("Спікери #g4-#g12", open=False):
                for row_start in range(4, 13, 3):
                    with gr.Row():
                        for i in range(row_start, min(row_start + 3, 13)):
                            with gr.Column():
                                voice_dropdowns.append(
                                    gr.Dropdown(
                                        label=f"🎙️ Голос #g{i}",
                                        choices=available_voices,
                                        value=available_voices[0] if available_voices else "default"
                                    )
                                )
                                speed_sliders.append(
                                    gr.Slider(0.7, 1.3, value=0.88, label=f"⏱️ Швидкість #g{i}", step=0.01)
                                )
            
            # Група 3: #g13-#g30
            with gr.Accordion("Спікери #g13-#g30", open=False):
                for row_start in range(13, 31, 3):
                    with gr.Row():
                        for i in range(row_start, min(row_start + 3, 31)):
                            with gr.Column():
                                voice_dropdowns.append(
                                    gr.Dropdown(
                                        label=f"🎙️ Голос #g{i}",
                                        choices=available_voices,
                                        value=available_voices[0] if available_voices else "default"
                                    )
                                )
                                speed_sliders.append(
                                    gr.Slider(0.7, 1.3, value=0.88, label=f"⏱️ Швидкість #g{i}", step=0.01)
                                )
        
        # === ОПЦІЇ ===
        with gr.Row():
            with gr.Column():
                save_option = gr.Radio(
                    ["Зберегти всі частини", "Без збереження"],
                    label="💾 Збереження",
                    value="Без збереження"
                )
            
            with gr.Column():
                ignore_speed_chk = gr.Checkbox(
                    label="⚡ Ігнорувати швидкість (для всіх використовувати 0.88)",
                    value=False
                )
        
        # === КНОПКИ ===
        with gr.Row():
            btn_start = gr.Button("▶️ Розпочати синтез", variant="primary", scale=2)
            btn_export = gr.Button("💾 Експорт налаштувань", scale=1)
        
        # === ПАНЕЛЬ РЕЗУЛЬТАТІВ ===
        with gr.Accordion("🔊 Результати синтезу", open=True):
            with gr.Row():
                audio_output = gr.Audio(label="🔊 Поточна частина", type='filepath')
                part_slider = gr.Slider(
                    label="📍 Номер частини",
                    minimum=1, maximum=1, step=1, value=1
                )
            
            with gr.Row():
                timer = gr.Textbox(label="⏱️ Час синтезу", value="0", interactive=False)
                start_time = gr.Textbox(label="🔔 Початок", interactive=False)
                end_time = gr.Textbox(label="🏁 Кінець", interactive=False)
            
            with gr.Row():
                est_finish = gr.Textbox(label="📊 Прогноз завершення", interactive=False)
                remaining = gr.Textbox(label="⏳ Залишилось", interactive=False)
            
            progress_slider = gr.Slider(
                label="📈 Прогрес синтезу",
                minimum=0, maximum=1, step=1, value=0, interactive=False
            )
        
        # === ДОВІДКА ===
        with gr.Accordion("📖 Синтаксис тегів", open=False):
            sfx_list = ', '.join(available_sfx) if available_sfx else 'Немає'
            gr.Markdown(f"""
            **Синтаксис для сценарію:**
            
            - `#gN: текст` - озвучити голосом №N
            - `#gN_slow` - медленно (0.80)
            - `#gN_fast` - швидко (1.20)
            - `#gN_slowNN` - точна швидкість (nn/100)
            - `#gN_fastNN` - точна швидкість (nn/100)
            - `#sfx_id` - звуковий ефект
            
            **Доступні SFX:**
            {sfx_list}
            
            **Приклад:**
            ```
            #g1: Привіт, як справи?
            #g2_fast: Чудово, дякую!
            #g1_slow95: До побачення!
            ```
            """)
        
        # === ПРИВ'ЯЗКА ОБРОБНИКІВ ===
        
        # Список всіх входів для обробника синтезу
        all_inputs = [
            text_input, 
            file_input,
            *speed_sliders,      # 30 швидкостей
            *voice_dropdowns,    # 30 голосів
            save_option,
            ignore_speed_chk
        ]
        
        # Вихідні дані обробника
        outputs = [
            audio_output,
            part_slider,
            timer,
            start_time,
            end_time,
            est_finish,
            remaining,
            progress_slider
        ]
        
        # Прив'язка кнопки старту
        btn_start.click(
            fn=batch_synthesize_handler,
            inputs=all_inputs,
            outputs=outputs,
            show_progress=False
        )
        
        # Прив'язка кнопки експорту
        btn_export.click(
            fn=export_settings_handler,
            inputs=voice_dropdowns + speed_sliders,
            outputs=btn_export
        )
    
    logger.info("✅ Інтерфейс побудовано успішно")
    return demo