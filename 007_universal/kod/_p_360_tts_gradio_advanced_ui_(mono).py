"""
p_353_tts_gradio_advanced_ui.py - Розширений Gradio UI для Multi Dialog TTS.
Компактна версія, що об'єднує всю функціональність в одному файлі.
"""

import os
import time
import logging
import tempfile
from typing import Dict, Any, List
import numpy as np
import soundfile as sf
import gradio as gr

def prepare_config_models():
    """Конфігурація не потрібна для цього модуля."""
    return {}

class AdvancedUI:
    """Компактний клас для розширеного UI Multi Dialog TTS."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.logger = app_context.get('logger', logging.getLogger("AdvancedUI"))
        self.tts_engine = app_context.get('tts_engine')
        self.dialog_parser = app_context.get('dialog_parser')
        self.sfx_handler = app_context.get('sfx_handler')
        
        if not all([self.tts_engine, self.dialog_parser, self.sfx_handler]):
            raise RuntimeError("Не знайдено обов'язкові компоненти")
        
        self.available_voices = self.tts_engine.get_available_voices()
        self.available_sfx = self.sfx_handler.get_available_sfx_ids()
        
        # Створення вихідної папки для сесії
        self.output_dir = os.path.join(os.getcwd(), "output_audio", f"session_{int(time.time())}")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.logger.info(f"📊 Розширений UI з голосами: {len(self.available_voices)}, SFX: {len(self.available_sfx)}")
    
    # ===== ОСНОВНІ ФУНКЦІЇ ОБРОБКИ =====
    
    def batch_synthesize_events(self, *args):
        """Основна функція обробки пакетного синтезу."""
        try:
            # Розпакування аргументів
            text_input, file_input = args[0], args[1]
            speeds_flat = list(args[2:32])      # 30 швидкостей
            voices_flat = list(args[32:62])     # 30 голосів
            save_option = args[62] if len(args) > 62 else "Без збереження"
            ignore_speed = bool(args[63]) if len(args) > 63 else False
            
            # Читання тексту
            text = self._read_input_text(text_input, file_input)
            
            # Парсинг подій
            events = self.dialog_parser.parse_script_events(text, voices_flat)
            total_parts = len(events)
            
            start_time = time.time()
            times_per_part = []
            voice_map = {i+1: voices_flat[i] if i < len(voices_flat) else None 
                        for i in range(30)}
            
            # Початковий update
            yield self._create_progress_update(0, total_parts, start_time, [], "")
            
            # Обробка кожної події
            for idx, event in enumerate(events, start=1):
                try:
                    part_path = self._process_event(idx, event, voice_map, speeds_flat, ignore_speed)
                    
                    # Оновлення прогресу
                    part_time = time.time()
                    times_per_part.append(part_time - start_time)
                    remaining = self._calculate_remaining_time(start_time, times_per_part, total_parts, part_time)
                    
                    yield self._create_progress_update(
                        idx, total_parts, start_time, times_per_part, remaining, part_path
                    )
                    
                except Exception as e:
                    self.logger.error(f"Помилка обробки частини {idx}: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            
            # Завершення
            total_elapsed = int(time.time() - start_time)
            yield self._create_final_update(total_parts, start_time, total_elapsed)
            
        except Exception as e:
            self.logger.error(f"Критична помилка: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def export_settings(self, *values):
        """Експорт налаштувань спікерів."""
        voices = list(values[:30])
        speeds = list(values[30:60])
        
        filename = f"settings_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for i in range(30):
                    voice = str(voices[i]).strip() if i < len(voices) else "default"
                    speed = float(speeds[i]) if i < len(speeds) else 0.88
                    f.write(f"#g{i+1}: {voice} (швидкість: {speed:.2f})\n")
            self.logger.info(f"✅ Налаштування експортовані: {filepath}")
        except Exception as e:
            self.logger.error(f"Помилка експорту: {e}")
        
        return filepath
    
    # ===== ДОПОМІЖНІ ФУНКЦІЇ =====
    
    def _read_input_text(self, text_input, file_input):
        """Читає текст з вводу або файлу."""
        if text_input and text_input.strip():
            return text_input
        elif file_input:
            with open(file_input, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise ValueError("Введіть текст або виберіть файл")
    
    def _process_event(self, idx, event, voice_map, speeds_flat, ignore_speed):
        """Обробляє одну подію (voice або sfx)."""
        if event.get('type') == 'voice':
            return self._process_voice_event(idx, event, voice_map, speeds_flat, ignore_speed)
        elif event.get('type') == 'sfx':
            return self._process_sfx_event(idx, event)
        else:
            self.logger.warning(f"Невідомий тип події: {event}")
            return None
    
    def _process_voice_event(self, idx, event, voice_map, speeds_flat, ignore_speed):
        """Обробляє голосову подію."""
        g_num = event.get('g')
        text_body = event.get('text', '')
        suffix = event.get('suffix', '')
        voice_name = voice_map.get(g_num, None)
        
        speed = self.dialog_parser.compute_speed_effective(
            g_num, suffix, speeds_flat, ignore_speed
        )
        
        # Синтез через TTS engine
        result = self.tts_engine.synthesize(
            text=text_body,
            speaker_id=g_num,
            speed=speed,
            voice=voice_name
        )
        
        audio, sr = result['audio'], result['sample_rate']
        return self._save_audio_part(idx, audio, sr)
    
    def _process_sfx_event(self, idx, event):
        """Обробляє SFX подію."""
        sfx_id = event.get('id')
        sr, audio = self.sfx_handler.load_and_process_sfx(sfx_id)
        return self._save_audio_part(idx, audio, sr)
    
    def _save_audio_part(self, idx, audio, sr):
        """Безпечно зберігає аудіо частину."""
        # Конвертація до float32
        if isinstance(audio, np.ndarray):
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
        else:
            audio = np.array(audio, dtype=np.float32)
        
        # Збереження
        part_path = os.path.join(self.output_dir, f"part_{idx:03d}.wav")
        try:
            sf.write(part_path, audio, sr)
            return part_path
        except Exception:
            # Fallback до тимчасової папки
            with tempfile.TemporaryDirectory() as tmpdir:
                part_path = os.path.join(tmpdir, f"part_{idx:03d}.wav")
                sf.write(part_path, audio, sr)
                return part_path
    
    def _calculate_remaining_time(self, start_time, times_per_part, total_parts, current_time):
        """Розраховує залишений час."""
        if times_per_part:
            avg_time = sum(times_per_part) / len(times_per_part)
            est_total = avg_time * total_parts
            remaining_secs = int(start_time + est_total - current_time)
            rem_min, rem_sec = divmod(max(remaining_secs, 0), 60)
            return f"{rem_min} хв {rem_sec} сек"
        return "Розрахунок..."
    
    def _create_progress_update(self, idx, total, start_time, times_per_part, remaining_text, audio_path=None):
        """Створює об'єкт оновлення прогресу."""
        elapsed = int(time.time() - start_time) if idx > 0 else 0
        
        if times_per_part and idx > 0:
            avg_time = sum(times_per_part) / len(times_per_part)
            est_total = avg_time * total
            est_finish = time.strftime('%H:%M:%S', time.localtime(start_time + est_total))
        else:
            est_finish = "Розрахунок..."
        
        return (
            audio_path,
            gr.update(value=idx, maximum=total, interactive=False),
            f"{elapsed} сек",
            time.strftime('%H:%M:%S', time.localtime(start_time)),
            time.strftime('%H:%M:%S', time.localtime(time.time())),
            est_finish,
            remaining_text,
            gr.update(value=idx, maximum=total, interactive=False),
        )
    
    def _create_final_update(self, total_parts, start_time, total_elapsed):
        """Створює фінальне оновлення."""
        return (
            None,
            gr.update(value=total_parts, maximum=total_parts, interactive=True),
            f"Завершено за {total_elapsed} сек",
            time.strftime('%H:%M:%S', time.localtime(start_time)),
            time.strftime('%H:%M:%S', time.localtime(time.time())),
            None,
            "",
            gr.update(value=total_parts, maximum=total_parts, interactive=False),
        )
    
    # ===== ПОБУДОВА ІНТЕРФЕЙСУ =====
    
    def create_interface(self):
        """Створює інтерфейс Gradio."""
        orange_theme = gr.themes.Soft(
            primary_hue=gr.themes.colors.orange,
            secondary_hue=gr.themes.colors.orange,
        ).set(
            # Точний колір ##b54d04
            button_primary_background_fill="linear-gradient(90deg, ##b54d04, #f08030)",
            button_primary_background_fill_hover="linear-gradient(90deg, #d85a05, ##b54d04)",
            button_primary_text_color="#ffffff",
            block_title_text_color="##b54d04",
            block_label_text_color="##b54d04",
            input_background_fill="#fff3e0",
            input_border_color="##b54d04",
            slider_color="##b54d04",
            checkbox_background_color="##b54d04",
            checkbox_border_color="##b54d04",
            
        )
        
        with gr.Blocks(title="TTS Multi Dialog Advanced", theme=orange_theme, css="""
        .orange-accent { color: ##b54d04 !important; }
        .orange-button { background: linear-gradient(90deg, ##b54d04, #f08030) !important; }
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
            voice_dropdowns, speed_sliders = self._create_speaker_accordions()
            
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
                audio_output, part_slider, timer, start_time_box, end_time, est_finish, remaining, progress_slider = self._create_progress_panel()
            
            # === ДОВІДКА ===
            self._create_help_accordion()
            
            # === ОБРОБНИКИ ===
            self._setup_handlers(btn_start, btn_export, text_input, file_input, 
                               voice_dropdowns, speed_sliders, save_option, ignore_speed_chk,
                               audio_output, part_slider, timer, start_time_box, 
                               end_time, est_finish, remaining, progress_slider)
        
        return demo
    
    def _create_speaker_accordions(self):
        """Створює акордеони для налаштування спікерів."""
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
                                    choices=self.available_voices,
                                    value=self.available_voices[0] if self.available_voices else "default"
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
                                        choices=self.available_voices,
                                        value=self.available_voices[0] if self.available_voices else "default"
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
                                        choices=self.available_voices,
                                        value=self.available_voices[0] if self.available_voices else "default"
                                    )
                                )
                                speed_sliders.append(
                                    gr.Slider(0.7, 1.3, value=0.88, label=f"⏱️ Швидкість #g{i}", step=0.01)
                                )
        
        return voice_dropdowns, speed_sliders
    
    def _create_progress_panel(self):
        """Створює панель прогресу."""
        with gr.Row():
            audio_output = gr.Audio(label="🔊 Поточна частина", type='filepath')
            part_slider = gr.Slider(
                label="📍 Номер частини",
                minimum=1, maximum=1, step=1, value=1
            )
        
        with gr.Row():
            timer = gr.Textbox(label="⏱️ Час синтезу", value="0", interactive=False)
            start_time_box = gr.Textbox(label="🔔 Початок", interactive=False)
            end_time = gr.Textbox(label="🏁 Кінець", interactive=False)
        
        with gr.Row():
            est_finish = gr.Textbox(label="📊 Прогноз завершення", interactive=False)
            remaining = gr.Textbox(label="⏳ Залишилось", interactive=False)
        
        progress_slider = gr.Slider(
            label="📈 Прогрес синтезу",
            minimum=0, maximum=1, step=1, value=0, interactive=False
        )
        
        return audio_output, part_slider, timer, start_time_box, end_time, est_finish, remaining, progress_slider
    
    def _create_help_accordion(self):
        """Створює акордеон з довідкою."""
        with gr.Accordion("📖 Синтаксис тегів", open=False):
            sfx_list = ', '.join(self.available_sfx) if self.available_sfx else 'Немає'
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
    
    def _setup_handlers(self, btn_start, btn_export, text_input, file_input,
                       voice_dropdowns, speed_sliders, save_option, ignore_speed_chk,
                       audio_output, part_slider, timer, start_time_box,
                       end_time, est_finish, remaining, progress_slider):
        """Налаштовує обробники подій."""
        # Всі вхідні дані для синтезу
        all_inputs = [
            text_input, 
            file_input,
            *speed_sliders,
            *voice_dropdowns,
            save_option,
            ignore_speed_chk
        ]
        
        # Вихідні дані
        outputs = [
            audio_output,
            part_slider,
            timer,
            start_time_box,
            end_time,
            est_finish,
            remaining,
            progress_slider
        ]
        
        # Прив'язка обробників
        btn_start.click(
            fn=self.batch_synthesize_events,
            inputs=all_inputs,
            outputs=outputs,
            show_progress=False
        )
        
        btn_export.click(
            fn=self.export_settings,
            inputs=voice_dropdowns + speed_sliders,
            outputs=btn_export
        )

def create_advanced_interface(app_context: Dict[str, Any]) -> gr.Blocks:
    """
    Створює розширений Gradio інтерфейс для Multi Dialog TTS.
    """
    ui = AdvancedUI(app_context)
    return ui.create_interface()

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