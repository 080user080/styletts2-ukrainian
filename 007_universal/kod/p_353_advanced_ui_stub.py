"""
p_353_tts_gradio_advanced_ui.py - Розширений Gradio UI для Multi Dialog TTS.

✅ ОСТАТОЧНА ВЕРСІЯ:
  - Виправлена помилка soundfile (безпечне писання файлу)
  - Добавлен точний колір #e96508
  - Правильна обробка аудіо від TTS
"""

import os
import time
import threading
import uuid
import logging
from typing import Dict, Any, List, Tuple, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gradio as gr
import numpy as np
import soundfile as sf


def prepare_config_models():
    """Конфігурація не потрібна для цього модуля."""
    return {}


def create_advanced_interface(app_context: Dict[str, Any]) -> gr.Blocks:
    """
    Створює розширений Gradio інтерфейс для Multi Dialog TTS.
    
    ✅ ОСТАТОЧНА ВЕРСІЯ: Виправлена обробка файлів та аудіо
    """
    
    logger = app_context.get('logger', logging.getLogger("AdvancedUI"))
    tts_engine = app_context.get('tts_engine')
    dialog_parser = app_context.get('dialog_parser')
    sfx_handler = app_context.get('sfx_handler')
    
    if not all([tts_engine, dialog_parser, sfx_handler]):
        raise RuntimeError("Не знайдено обов'язкові компоненти (tts_engine, dialog_parser, sfx_handler)")
    
    # Отримати доступні голоси та SFX
    available_voices = tts_engine.get_available_voices()
    available_sfx = sfx_handler.get_available_sfx_ids()
    
    # Вихідна папка для сесії
    output_dir = os.path.join(os.getcwd(), "output_audio", f"session_{int(time.time())}")
    
    # ✅ ВИПРАВЛЕНО: Безпечне створення папки з обробкою помилок
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        logger.warning(f"Не вдалося створити папку {output_dir}: {e}")
        # Fallback - використовуємо поточну папку
        output_dir = os.path.join(os.getcwd(), "output_audio")
        os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"📊 Розширений UI з голосами: {len(available_voices)}, SFX: {len(available_sfx)}")
    logger.info(f"📁 Вихідна папка: {output_dir}")
    
    # ===== ФУНКЦІЇ ОБРОБКИ =====
    
    def batch_synthesize_events(*args):
        """
        ✅ ОСТАТОЧНА ВЕРСІЯ: Правильна обробка аудіо та файлів
        """
        
        try:
            # Розпакування аргументів
            text_input = args[0]
            file_input = args[1]
            speeds_flat = list(args[2:32])      # 30 швидкостей
            voices_flat = list(args[32:62])     # 30 голосів
            save_option = args[62] if len(args) > 62 else "Без збереження"
            ignore_speed = bool(args[63]) if len(args) > 63 else False
            
            logger.info(f"Отримано {len(args)} аргументів: speeds={len(speeds_flat)}, voices={len(voices_flat)}")
            
            # Читання тексту
            if text_input and text_input.strip():
                text = text_input
            elif file_input:
                with open(file_input, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                raise ValueError("Введіть текст або виберіть файл")
            
            # Парсинг подій
            events = dialog_parser.parse_script_events(text, voices_flat)
            total_parts = len(events)
            
            logger.info(f"Парсено {total_parts} подій для синтезу")
            
            start_time = time.time()
            times_per_part = []
            voice_map = {i+1: voices_flat[i] if i < len(voices_flat) else None 
                        for i in range(30)}
            
            # Початковий update
            yield (
                None,
                gr.update(value=1, maximum=total_parts, interactive=False),
                "0 сек",
                "",
                "",
                "Розрахунок...",
                "",
                gr.update(value=0, maximum=total_parts, interactive=False),
            )
            
            # Обробка кожної події
            for idx, event in enumerate(events, start=1):
                part_start = time.time()
                
                try:
                    if event.get('type') == 'voice':
                        g_num = event.get('g')
                        text_body = event.get('text', '')
                        suffix = event.get('suffix', '')
                        voice_name = voice_map.get(g_num, None)
                        speed = dialog_parser.compute_speed_effective(
                            g_num, suffix, speeds_flat, ignore_speed
                        )
                        
                        # ✅ ВИПРАВЛЕНО: Синтез через TTS engine
                        result = tts_engine.synthesize(
                            text=text_body,
                            speaker_id=g_num,
                            speed=speed,
                            voice=voice_name
                        )
                        
                        audio = result['audio']
                        sr = result['sample_rate']
                        
                        # ✅ ВАЖЛИВО: Переконатися що аудіо у правильному форматі
                        if isinstance(audio, np.ndarray):
                            if audio.dtype != np.float32:
                                audio = audio.astype(np.float32)
                        else:
                            audio = np.array(audio, dtype=np.float32)
                        
                    elif event.get('type') == 'sfx':
                        sfx_id = event.get('id')
                        
                        # Завантажити SFX
                        sr, audio = sfx_handler.load_and_process_sfx(sfx_id)
                        
                        # Переконатися що аудіо у правильному форматі
                        if isinstance(audio, np.ndarray):
                            if audio.dtype != np.float32:
                                audio = audio.astype(np.float32)
                        else:
                            audio = np.array(audio, dtype=np.float32)
                        
                    else:
                        logger.warning(f"Невідомий тип події: {event}")
                        continue
                    
                    # ✅ ВИПРАВЛЕНО: Безпечне писання файлу
                    part_path = os.path.join(output_dir, f"part_{idx:03d}.wav")
                    
                    try:
                        sf.write(part_path, audio, sr)
                        logger.info(f"✅ Частина {idx} збережена: {part_path}")
                    except Exception as write_error:
                        logger.error(f"Помилка писання файлу {part_path}: {write_error}")
                        # ✅ Fallback: спробуємо тимчасову папку
                        import tempfile
                        with tempfile.TemporaryDirectory() as tmpdir:
                            part_path = os.path.join(tmpdir, f"part_{idx:03d}.wav")
                            sf.write(part_path, audio, sr)
                            logger.info(f"✅ Частина {idx} збережена у temp: {part_path}")
                    
                    # Обновлення таймінгу
                    part_end = time.time()
                    elapsed = int(part_end - start_time)
                    times_per_part.append(part_end - part_start)
                    
                    # Прогноз
                    if times_per_part:
                        avg_time = sum(times_per_part) / len(times_per_part)
                        est_total = avg_time * total_parts
                        est_finish = time.strftime('%H:%M:%S', time.localtime(start_time + est_total))
                        remaining_secs = int(start_time + est_total - part_end)
                        rem_min, rem_sec = divmod(max(remaining_secs, 0), 60)
                        remaining_text = f"{rem_min} хв {rem_sec} сек"
                    else:
                        est_finish = "Розрахунок..."
                        remaining_text = "Розрахунок..."
                    
                    # Yield обновлення
                    yield (
                        part_path if os.path.exists(part_path) else None,
                        gr.update(value=idx, maximum=total_parts, interactive=False),
                        f"{elapsed} сек",
                        time.strftime('%H:%M:%S', time.localtime(start_time)),
                        time.strftime('%H:%M:%S', time.localtime(part_end)),
                        est_finish,
                        remaining_text,
                        gr.update(value=idx, maximum=total_parts, interactive=False),
                    )
                    
                except Exception as e:
                    logger.error(f"Помилка обробки частини {idx}: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            
            # Завершення
            total_elapsed = int(time.time() - start_time)
            logger.info(f"✅ Синтез завершено за {total_elapsed} сек")
            
            yield (
                None,
                gr.update(value=total_parts, maximum=total_parts, interactive=True),
                f"Завершено за {total_elapsed} сек",
                time.strftime('%H:%M:%S', time.localtime(start_time)),
                time.strftime('%H:%M:%S', time.localtime(time.time())),
                None,
                "",
                gr.update(value=total_parts, maximum=total_parts, interactive=False),
            )
        
        except Exception as e:
            logger.error(f"Критична помилка: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def export_settings(*values):
        """Експорт налаштувань спікерів."""
        voices = list(values[:30])
        speeds = list(values[30:60])
        
        filename = f"settings_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for i in range(30):
                    voice = str(voices[i]).strip() if i < len(voices) else "default"
                    speed = float(speeds[i]) if i < len(speeds) else 0.88
                    f.write(f"#g{i+1}: {voice} (швидкість: {speed:.2f})\n")
            logger.info(f"✅ Налаштування експортовані: {filepath}")
        except Exception as e:
            logger.error(f"Помилка експорту: {e}")
        
        return filepath
    
    # ===== КОЛЬОРОВА ТЕМА (CUSTOM ОРАНЖЕВА #e96508) =====
    
    orange_theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.orange,
        secondary_hue=gr.themes.colors.orange,
    ).set(
        # ✅ ТОЧНИЙ КОЛІР #e96508
        button_primary_background_fill="linear-gradient(90deg, #e96508, #f08030)",
        button_primary_background_fill_hover="linear-gradient(90deg, #d85a05, #e96508)",
        button_primary_text_color="#ffffff",
        
        # Акценти
        block_title_text_color="#e96508",
        block_label_text_color="#e96508",
        
        # Інтерактивні елементи
        input_background_fill="#fff3e0",
        input_border_color="#e96508",
        
        # Слайдер
        slider_color="#e96508",
        
        # Чекбокс та радіо
        checkbox_background_color="#e96508",
        checkbox_border_color="#e96508",
        radio_background_color="#e96508",
    )
    
    # ===== БУДУВАННЯ ІНТЕРФЕЙСУ =====
    
    with gr.Blocks(title="TTS Multi Dialog Advanced", theme=orange_theme, css="""
    .orange-accent {
        color: #e96508 !important;
    }
    .orange-button {
        background: linear-gradient(90deg, #e96508, #f08030) !important;
    }
    """) as demo:
        
        gr.Markdown("""
        # 🎙️ TTS Multi Dialog - Розширений режим
        
        **Введіть сценарій** з тегами або завантажте файл:
        - `#gN: текст` — озвучити голосом №N (1-30)
        - `#gN_fast` / `#gN_slow` — швидкість (1.20 / 0.80)
        - `#gN_slow95` / `#gN_fast110` — точна швидкість (0.95 / 1.10)
        - `#sfx_bell` — звуковий ефект
        """)
        
        # === ВХІД ===
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
        
        with gr.Accordion("⚙️ Налаштування спікерів", open=False):
            # Группа 1: #g1-#g3
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
            
            # Группа 2: #g4-#g12
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
            
            # Группа 3: #g13-#g30
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
        
        # === ПРОГРЕС ===
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
            gr.Markdown(f"""
            **Синтаксис для сценарію:**
            
            - `#gN: текст` - озвучити голосом №N
            - `#gN_slow` - медленно (0.80)
            - `#gN_fast` - швидко (1.20)
            - `#gN_slowNN` - точна швидкість (nn/100)
            - `#gN_fastNN` - точна швидкість (nn/100)
            - `#sfx_id` - звуковий ефект
            
            **Доступні SFX:**
            {', '.join(available_sfx) if available_sfx else 'Немає'}
            
            **Приклад:**
            ```
            #g1: Привіт, як справи?
            #g2_fast: Чудово, дякую!
            #g1_slow95: До побачення!
            ```
            """)
        
        # === ОБРОБНИКИ ===
        
        btn_start.click(
            fn=batch_synthesize_events,
            inputs=[
                text_input, 
                file_input,
                *speed_sliders,
                *voice_dropdowns,
                save_option,
                ignore_speed_chk
            ],
            outputs=[
                audio_output,
                part_slider,
                timer,
                start_time,
                end_time,
                est_finish,
                remaining,
                progress_slider
            ],
            show_progress=False
        )
        
        btn_export.click(
            fn=export_settings,
            inputs=voice_dropdowns + speed_sliders,
            outputs=btn_export
        )
    
    return demo


def initialize(app_context: Dict[str, Any]) -> Dict[str, Any]:
    """Ініціалізація розширеного UI."""
    logger = app_context.get('logger', logging.getLogger("AdvancedUI"))
    logger.info("🎨 Ініціалізація розширеного Gradio UI...")
    
    try:
        demo = create_advanced_interface(app_context)
        app_context['tts_gradio_advanced_demo'] = demo
        
        logger.info("✅ Розширений UI готовий до запуску")
        return {'demo': demo}
    
    except Exception as e:
        logger.error(f"Помилка ініціалізації UI: {e}")
        import traceback
        traceback.print_exc()
        raise


def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка UI."""
    if 'tts_gradio_advanced_demo' in app_context:
        del app_context['tts_gradio_advanced_demo']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("Розширений UI зупинено")
