import time
import logging
import os
import soundfile as sf
import numpy as np
from typing import Dict, Any, Callable, List, Tuple
import gradio as gr
from p_357_ui_utils import (
    save_audio_part, 
    calculate_remaining_time, 
    read_input_text
)

class UIEventHandlers:
    """Обробники подій для UI."""
    
    def __init__(self, 
                 tts_engine: Any,
                 dialog_parser: Any,
                 sfx_handler: Any,
                 logger: logging.Logger = None):
        self.tts_engine = tts_engine
        self.dialog_parser = dialog_parser
        self.sfx_handler = sfx_handler
        self.logger = logger or logging.getLogger("UIHandlers")
    
    def synthesize_batch(self, *args) -> Tuple:
        """Обробляє пакетний синтез."""
        try:
            # Розпакування аргументів
            text_input = args[0]
            file_input = args[1]
            speeds_flat = list(args[2:32])      # 30 швидкостей
            voices_flat = list(args[32:62])     # 30 голосів
            save_option = args[62] if len(args) > 62 else "Без збереження"
            ignore_speed = bool(args[63]) if len(args) > 63 else False
            
            # Перевіряємо, чи file_input не є директорією
            if file_input and isinstance(file_input, str):
                if os.path.isdir(file_input):
                    raise ValueError(f"Вказаний шлях '{file_input}' є директорією, а не файлом")
            
            # Читання тексту
            text = read_input_text(text_input, file_input)
            
            # Парсинг подій
            events = self.dialog_parser.parse_script_events(text, voices_flat)
            total_parts = len(events)
            
            # Створюємо папку для збереження
            output_dir = os.path.join(os.getcwd(), "output_audio", f"session_{int(time.time())}")
            os.makedirs(output_dir, exist_ok=True)
            
            start_time = time.time()
            times_per_part = []
            
            # Обробка кожної події
            for idx, event in enumerate(events, start=1):
                try:
                    # Синтез
                    audio, sr = self._process_single_event(idx, event, voices_flat, speeds_flat, ignore_speed)
                    
                    # Збереження тільки якщо вибрано опцію
                    if save_option == "Зберегти всі частини":
                        audio_path = save_audio_part(audio, sr, idx, output_dir)
                    else:
                        # Якщо не зберігаємо, створюємо тимчасовий файл
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                            # Конвертація до float32
                            if isinstance(audio, np.ndarray):
                                if audio.dtype != np.float32:
                                    audio = audio.astype(np.float32)
                            else:
                                audio = np.array(audio, dtype=np.float32)
                            
                            sf.write(tmp.name, audio, sr)
                            audio_path = tmp.name
                    
                    # Оновлення прогресу
                    part_time = time.time()
                    times_per_part.append(part_time - start_time)
                    
                    yield self._create_progress_update(
                        idx, total_parts, start_time, times_per_part, audio_path
                    )
                    
                except Exception as e:
                    self.logger.error(f"Помилка обробки частини {idx}: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            
            # Фінальний update
            total_elapsed = int(time.time() - start_time)
            yield (
                None,
                gr.update(value=total_parts, maximum=total_parts, interactive=True),
                f"Завершено за {total_elapsed} сек",
                "Готово!",
                gr.update(value=total_parts, maximum=total_parts, interactive=False),
                f"Файли збережено в: {os.path.basename(output_dir)}"
            )
        
        except Exception as e:
            self.logger.error(f"Помилка синтезу: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def export_settings(self, voices: List[str], speeds: List[float]) -> str:
        """Експортує налаштування."""
        import tempfile
        import time
        
        timestamp = int(time.time())
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(f"Налаштування TTS спікерів (експорт {time.strftime('%Y-%m-%d %H:%M:%S')})\n")
            f.write("=" * 50 + "\n\n")
            for i, voice in enumerate(voices[:30]):
                speed = speeds[i] if i < len(speeds) else 0.88
                f.write(f"#g{i+1}: {voice} (швидкість: {speed:.2f})\n")
            return f.name
    
    def _process_single_event(self, idx, event, voices_flat, speeds_flat, ignore_speed):
        """Обробляє одну подію."""
        if event.get('type') == 'voice':
            g_num = event.get('g')
            text_body = event.get('text', '')
            voice_name = voices_flat[g_num - 1] if g_num <= len(voices_flat) else None
            
            speed = self.dialog_parser.compute_speed_effective(
                g_num, event.get('suffix', ''), speeds_flat, ignore_speed
            )
            
            # ВАЖЛИВО: Не передаємо output_path до двигуна!
            result = self.tts_engine.synthesize(
                text=text_body,
                speaker_id=g_num,
                speed=speed,
                voice=voice_name
            )
            return result['audio'], result['sample_rate']
        
        elif event.get('type') == 'sfx':
            sfx_id = event.get('id')
            sr, audio = self.sfx_handler.load_and_process_sfx(sfx_id)
            return audio, sr
    
    def _create_progress_update(self, idx, total, start_time, times_per_part, audio_path):
        """Створює об'єкт прогресу."""
        elapsed = int(time.time() - start_time)
        
        if times_per_part and idx > 0:
            remaining = calculate_remaining_time(start_time, times_per_part, total)
        else:
            remaining = "Розрахунок..."
        
        return (
            audio_path,
            gr.update(value=idx, maximum=total),
            f"{elapsed} сек",
            remaining,
            gr.update(value=idx, maximum=total),
            f"Частина {idx} з {total}"
        )

def prepare_config_models():
    """Конфігурація не потрібна."""
    return {}