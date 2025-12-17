"""
a_8_pipeline.py
Оркестрація: батч-синтез усіх подій (voice + sfx) з прогресом для UI.
"""

import os
import time
import re
import gradio as gr
from typing import Iterable, List
from concurrent.futures import ThreadPoolExecutor

from a_2_synthesis import _synthesize_chunk
from a_3_sfx_engine import _load_and_process_sfx, get_sfx_config
from a_5_speaker_logic import parse_script_events, _compute_speed_effective
from a_4_progress_logic import estimate_remaining, get_elapsed_str
from a_7_utils import format_hms, _read_text_source
import soundfile as sf


SPEAKER_MAX = 30
PROGRESS_POLL_INTERVAL = 1.0


def batch_synthesize_dialog_events(
    text_input: str | None,
    file_path: str | None,
    speeds_flat: list,
    voices_flat: list,
    save_option: str,
    ignore_speed: bool = False,
    output_dir: str = "output_audio"
) -> Iterable:
    """
    Основний батч-синтез: обробляє сценарій з подіями (voice/sfx).
    На кожну подію створює part_{idx:03}.wav, за потребою part_{idx:03}.txt.
    
    Parameters:
        text_input: Текст з поля (може бути None)
        file_path: Шлях до файлу (може бути None)
        speeds_flat: 30 значень слайдерів швидкості
        voices_flat: 30 значень dropdown голосів
        save_option: Опція збереження текстових частин
        ignore_speed: Ігнорувати швидкість та суфікси, використовувати DEFAULT_SPEED
        output_dir: Директорія для вивідних файлів
    
    Yields:
        Кортежі для оновлення UI Gradio:
        (audio_file, part_slider_update, timer_text, start_time, end_time,
         est_finish, remaining_time, progress_update)
    """
    os.makedirs(output_dir, exist_ok=True)
    global_start = time.time()
    
    # Прочитати текст
    text = _read_text_source(text_input, file_path)
    
    # Час старту для консолі
    start_time_str = time.strftime('%H:%M:%S', time.localtime(global_start))
    print(f'Start: {start_time_str}')
    
    # Парсинг подій
    try:
        events = parse_script_events(text, voices_flat, max_speakers=SPEAKER_MAX)
    except Exception as e:
        print(f'Error while parsing script: {e}')
        raise
    
    total_parts = max(1, len(events))
    times_per_part: List[float] = []
    warnings: List[str] = []
    base_sr: int | None = None
    
    # Словник голосів по g-номеру
    voice_map = {i + 1: (voices_flat[i] if i < len(voices_flat) else None) for i in range(SPEAKER_MAX)}
    
    # Отримати конфіг DEFAULT_SPEED
    sfx_cfg = get_sfx_config()
    default_speed = float(sfx_cfg.get("default_speed", 0.88))
    
    # Початкове оновлення UI
    yield (
        None,
        gr.update(value=1, maximum=total_parts, interactive=False),
        "0 сек",
        start_time_str,
        "",
        "Розрахунок...",
        "",
        gr.update(value=0, maximum=total_parts, interactive=False),
    )
    
    # Обробити всі події
    for idx, event in enumerate(events, start=1):
        part_start = time.time()
        
        # Визначити тип та параметри
        if event.get('type') == 'voice':
            g_num = event.get('g')
            suffix = event.get('suffix', '')
            text_body = event.get('text', '')
            voice_name = voice_map.get(g_num, None)
            
            # Обчислити ефективну швидкість
            speed_eff = _compute_speed_effective(
                g_num, suffix, speeds_flat, ignore_speed, default_speed
            )
            
            # Попередження
            if not ignore_speed and (speed_eff < 0.7 or speed_eff > 1.3):
                warnings.append(f'Вихід за межи слайдера для #g{g_num}: {speed_eff:.2f}')
            if not voice_name:
                warnings.append(f'Не вказано голос для #g{g_num}')
            
            call_func = _synthesize_chunk
            call_args = (text_body, voice_name, speed_eff)
            extra_info = {
                "type": "voice",
                "g": g_num,
                "voice_name": voice_name,
                "speed_eff": speed_eff,
                "text_len": len(text_body),
                "text_body": text_body,
            }
        
        elif event.get('type') == 'sfx':
            sfx_id = event.get('id')
            target_sr = base_sr if base_sr else int(sfx_cfg.get('default_sr', 24000))
            
            call_func = _load_and_process_sfx
            call_args = (sfx_id, target_sr)
            cfg = sfx_cfg.get('sounds', {}).get(sfx_id, {})
            extra_info = {
                "type": "sfx",
                "sfx_id": sfx_id,
                "file": cfg.get('file'),
                "gain_db": cfg.get('gain_db', 0.0),
            }
        
        else:
            warnings.append(f"Невідомий тип події: {event}")
            continue
        
        # Виконати у потоці з відповідю прогресу
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call_func, *call_args)
            
            while not future.done():
                now = time.time()
                elapsed_str = get_elapsed_str(global_start)
                est_finish_str, rem_text = estimate_remaining(
                    idx, total_parts, times_per_part, global_start
                )
                
                yield (
                    None,
                    gr.update(value=idx, maximum=total_parts, interactive=False),
                    elapsed_str,
                    start_time_str,
                    None,
                    est_finish_str,
                    rem_text,
                    gr.update(value=max(idx - 1, 0), maximum=total_parts, interactive=False),
                )
                time.sleep(PROGRESS_POLL_INTERVAL)
            
            try:
                sr, audio_np = future.result()
            except Exception as e:
                print(f'Error processing part {idx}: {e}')
                raise
        
        # Запам'ятати базову частоту для SFX
        if extra_info["type"] == "voice" and base_sr is None:
            base_sr = sr
        
        # Записати аудіо
        audio_filename = os.path.join(output_dir, f"part_{idx:03}.wav")
        sf.write(audio_filename, audio_np, sr)
        
        # Записати текст якщо потрібно
        if save_option == 'Зберегти всі частини озвученого тексту' and extra_info["type"] == "voice":
            txt_filename = os.path.join(output_dir, f"part_{idx:03}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as txt_file:
                txt_file.write(extra_info["text_body"])
        
        # Логування
        if extra_info["type"] == "voice":
            print(f'Part {idx}: type=voice, g={extra_info["g"]}, '
                  f'voice={extra_info["voice_name"]}, '
                  f'speed={extra_info["speed_eff"]:.2f}, '
                  f'text_len={extra_info["text_len"]}, '
                  f'path={audio_filename}')
        else:
            print(f'#{extra_info["sfx_id"]} --- file "{extra_info["file"]}" '
                  f'-- {os.path.basename(audio_filename)}')
        
        # Оновити прогрес
        part_end = time.time()
        times_per_part.append(part_end - part_start)
        end_time_str = time.strftime('%H:%M:%S', time.localtime(part_end))
        elapsed_seconds = int(part_end - global_start)
        elapsed_total = f"{elapsed_seconds} сек --- {format_hms(elapsed_seconds)}"
        
        yield (
            audio_filename,
            gr.update(value=idx, maximum=total_parts, interactive=False),
            elapsed_total,
            start_time_str,
            end_time_str,
            None,
            "",
            gr.update(value=idx, maximum=total_parts, interactive=False),
        )
    
    # Завершення
    total_elapsed_secs = int(time.time() - global_start)
    total_formatted = format_hms(total_elapsed_secs)
    finish_time_str = time.strftime('%H:%M:%S', time.localtime(time.time()))
    
    print(f'Finished: {finish_time_str}, duration: {total_formatted}, parts: {len(events)}')
    if warnings:
        print('Warnings:')
        for w in warnings:
            print(f'  - {w}')
    print(f"\033[92mЗатрачено часу: {total_formatted}\033[0m")
    
    yield (
        None,
        gr.update(value=total_parts, maximum=total_parts, interactive=True),
        f"Завершено за {total_elapsed_secs} сек",
        start_time_str,
        finish_time_str,
        None,
        "",
        gr.update(value=total_parts, maximum=total_parts, interactive=False),
    )
