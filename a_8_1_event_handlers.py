"""
a_8_1_event_handlers.py
Обробники подій для кнопок, слайдерів, завантаження/експорту налаштувань.
"""

import os
import re
import time
import uuid
import gradio as gr
from typing import Callable


def create_btn_start_handler(pipeline_func: Callable) -> Callable:
    """
    Створює обробник для кнопки 'Розпочати'.
    
    Parameters:
        pipeline_func: функція батч_синтезу (з a_8_pipeline)
    
    Returns:
        Функція-обробник для click-события кнопки
    """
    def handler(text_input, file_input, *flat_values):
        # Перезавантажити конфіг sfx.yaml
        from a_3_sfx_engine import get_sfx_config
        try:
            sfx_cfg = get_sfx_config()
        except Exception as e:
            print(f"Warning: не вдалося перезавантажити sfx.yaml: {e}")
        
        # Розпакувати flat_values: 30 speed, 30 voice, save_option, ignore_speed
        speeds = list(flat_values[:30])
        voices = list(flat_values[30:60])
        save_option = flat_values[60] if len(flat_values) > 60 else None
        ignore_speed = bool(flat_values[61]) if len(flat_values) > 61 else False
        
        yield from pipeline_func(text_input, file_input, speeds, voices, save_option, ignore_speed)
    
    return handler


def create_export_settings_handler(output_dir: str) -> Callable:
    """
    Обробник експорту налаштувань голосів у файл для завантаження.
    
    Returns:
        Функція, що приймає (voice_components..., speed_components...)
        і повертає шлях до файлу
    """
    def handler(*flat_values):
        """
        flat_values: 30 dropdown (voices) + 30 sliders (speeds)
        """
        voices = list(flat_values[:30])
        speeds = list(flat_values[30:60])
        
        export_root = os.path.join(output_dir, "_exports")
        os.makedirs(export_root, exist_ok=True)
        
        fname = f"speakers_settings_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.txt"
        out_path = os.path.abspath(os.path.join(export_root, fname))
        
        lines = []
        for i in range(30):
            vname = str(voices[i]).strip()
            try:
                spd = float(speeds[i])
            except Exception:
                spd = 1.0
            spd_str = f"{spd:.2f}".replace(".", ",")
            lines.append(f"#g{i+1}:{vname} швидкість:{spd_str};")
        
        text = "\n".join(lines) + "\n"
        
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        
        return out_path
    
    return handler


def create_save_to_default_handler(output_dir: str) -> Callable:
    """
    Обробник збереження налаштувань у папку за замовчуванням.
    
    Returns:
        Функція, що приймає (voice_components..., speed_components...)
    """
    def handler(*flat_values):
        voices = list(flat_values[:30])
        speeds = list(flat_values[30:60])
        
        os.makedirs(output_dir, exist_ok=True)
        cfg_path = os.path.join(output_dir, "speakers_settings.txt")
        
        with open(cfg_path, "w", encoding="utf-8") as f:
            for i in range(1, 31):
                voice_name = str(voices[i-1]).strip()
                try:
                    speed_val = float(speeds[i-1])
                except Exception:
                    speed_val = 1.0
                speed_str = f"{speed_val:.2f}".replace(".", ",")
                f.write(f"#g{i}:{voice_name} швидкість:{speed_str};\n")
        
        gr.Info(f"✅ Налаштування збережено: {cfg_path}")
    
    return handler


def create_load_settings_handler() -> Callable:
    """
    Обробник завантаження налаштувань з файлу.
    
    Returns:
        Функція, що приймає (files, voice_components..., speed_components...)
        і повертає оновлені значення
    """
    def handler(files, *current_values):
        if not files:
            raise gr.Error("Не обрано файл налаштувань (.txt).")
        
        if isinstance(files, (list, tuple)):
            src = files[0]
        else:
            src = files
        
        file_path = str(src if isinstance(src, str) else 
                       (src.get("name") or src.get("path") if isinstance(src, dict) 
                        else getattr(src, "name", ""))) or None
        
        if not file_path:
            raise gr.Error("Не вдалося визначити шлях до файлу.")
        
        pat = re.compile(
            r'^#g([1-9]|[12]\d|30)\s*:\s*(.*?)\s*швидкість\s*:\s*([0-9]+(?:[.,][0-9]+)?)\s*;\s*$',
            re.IGNORECASE
        )
        
        voices_out = list(current_values[:30])
        speeds_out = list(current_values[30:60])
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            raise gr.Error(f"Не вдалося прочитати файл: {e}")
        
        for line in content.splitlines():
            m = pat.match(line.strip())
            if not m:
                continue
            
            idx = int(m.group(1)) - 1
            voice_name = m.group(2).strip()
            speed_raw = m.group(3).replace(",", ".")
            
            try:
                speed_val = float(speed_raw)
            except Exception:
                speed_val = speeds_out[idx] if 0 <= idx < len(speeds_out) else 1.0
            
            speed_val = max(0.7, min(1.3, speed_val))
            
            if 0 <= idx < 30:
                voices_out[idx] = voice_name
                speeds_out[idx] = speed_val
        
        return voices_out + speeds_out
    
    return handler


def create_part_slider_handler(output_dir: str) -> Callable:
    """
    Обробник зміни слайдера частин: завантажує відповідний audio файл.
    
    Returns:
        Функція, що приймає (part_idx, autoplay) і повертає gr.update
    """
    def handler(part_idx: int, autoplay: bool):
        try:
            i = int(part_idx)
        except Exception:
            gr.Warning("Некоректний номер частини")
            return gr.update()
        
        wav_path = os.path.join(output_dir, f"part_{i:03}.wav")
        if not os.path.exists(wav_path):
            gr.Error(f"Файл не знайдено: {wav_path}")
            return gr.update()
        
        return gr.update(value=wav_path, autoplay=bool(autoplay))
    
    return handler
