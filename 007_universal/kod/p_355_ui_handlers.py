import time
import logging
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
            
            # Читання тексту
            text = read_input_text(text_input, file_input)
            
            # Парсинг подій
            events = self.dialog_parser.parse_script_events(text, voices_flat)
            total_parts = len(events)
            
            start_time = time.time()
            times_per_part = []
            
            # Обробка кожної події
            for idx, event in enumerate(events, start=1):
                # Синтез
                audio, sr = self._process_single_event(idx, event, voices_flat, speeds_flat, ignore_speed)
                
                # Збереження
                audio_path = save_audio_part(audio, sr, idx, "/tmp")
                
                # Оновлення прогресу
                part_time = time.time()
                times_per_part.append(part_time - start_time)
                
                yield self._create_progress_update(
                    idx, total_parts, start_time, times_per_part, audio_path
                )
        
        except Exception as e:
            self.logger.error(f"Помилка синтезу: {e}")
            raise
    
    def export_settings(self, voices: List[str], speeds: List[float]) -> str:
        """Експортує налаштування."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
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
        remaining = calculate_remaining_time(start_time, times_per_part, total)
        
        return (
            audio_path,
            gr.update(value=idx, maximum=total),
            f"{elapsed} сек",
            remaining,
            gr.update(value=idx, maximum=total)
        )

def prepare_config_models():
    """Конфігурація не потрібна."""
    return {}