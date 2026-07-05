"""
a_8_pipeline.py
Оркестрація: батч-синтез усіх подій (voice + sfx + pause) з прогресом для UI.
Включає кешування ідентичних аудіо для оптимізації.
"""

import os
import time
import re
import hashlib
import shutil
import gradio as gr
from typing import Iterable, List, Tuple
from concurrent.futures import ThreadPoolExecutor

from a_2_synthesis import _synthesize_chunk
from a_3_sfx_engine import _load_and_process_sfx, get_sfx_config, generate_pause
from a_5_speaker_logic import parse_script_events, _compute_speed_effective
from a_4_progress_logic import estimate_remaining, get_elapsed_str
from a_7_utils import format_hms, _read_text_source
import soundfile as sf
import numpy as np


SPEAKER_MAX = 30
PROGRESS_POLL_INTERVAL = 1.0


def _make_cache_key(voice_name: str | None, text_body: str, speed_eff: float) -> str:
    """
    Створює унікальний ключ для кешування на основі голосу, тексту та швидкості.
    """
    voice_str = str(voice_name or "default").lower().strip()
    text_str = text_body.strip()
    speed_str = f"{speed_eff:.4f}"
    combined = f"{voice_str}|{text_str}|{speed_str}"
    return hashlib.md5(combined.encode('utf-8')).hexdigest()


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
    Основний батч-синтез: обробляє сценарій з подіями (voice / sfx / pause).
    На кожну подію створює part_{idx:03}.wav, за потребою part_{idx:03}.txt.

    ОПТИМІЗАЦІЯ: Ідентичні тексти (voice+text+speed) синтезуються лише один раз,
    потім аудіо копіюється для всіх повторень.

    Yields:
        Кортежі для оновлення UI Gradio.
    """
    os.makedirs(output_dir, exist_ok=True)
    global_start = time.time()

    text = _read_text_source(text_input, file_path)
    start_time_str = time.strftime('%H:%M:%S', time.localtime(global_start))
    print(f'Start: {start_time_str}')

    try:
        events = parse_script_events(text, voices_flat, max_speakers=SPEAKER_MAX)
    except Exception as e:
        print(f'Error while parsing script: {e}')
        raise

    total_parts = max(1, len(events))
    times_per_part: List[float] = []
    warnings: List[str] = []
    base_sr: int | None = None

    voice_map = {i + 1: (voices_flat[i] if i < len(voices_flat) else None) for i in range(SPEAKER_MAX)}

    sfx_cfg = get_sfx_config()
    default_speed = float(sfx_cfg.get("default_speed", 0.88))
    default_sr = int(sfx_cfg.get('default_sr', 24000))

    audio_cache = {}
    cache_hits = 0
    cache_misses = 0

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

    for idx, event in enumerate(events, start=1):
        part_start = time.time()
        event_type = event.get('type')

        # ── ПАУЗА ────────────────────────────────────────────────────────────
        if event_type == 'pause':
            duration = event['duration']
            sr = base_sr if base_sr else default_sr
            audio_np = generate_pause(duration, sr)

            audio_filename = os.path.join(output_dir, f"part_{idx:03}.wav")
            sf.write(audio_filename, audio_np, sr)

            print(f"⏸ Part {idx}: pause {duration} с → {os.path.basename(audio_filename)}")

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
            continue

        # ── VOICE ─────────────────────────────────────────────────────────────
        elif event_type == 'voice':
            g_num = event.get('g')
            suffix = event.get('suffix', '')
            text_body = event.get('text', '')
            voice_name = voice_map.get(g_num, None)

            speed_eff = _compute_speed_effective(
                g_num, suffix, speeds_flat, ignore_speed, default_speed
            )

            if not ignore_speed and (speed_eff < 0.7 or speed_eff > 1.3):
                warnings.append(f'Вихід за межі слайдера для #g{g_num}: {speed_eff:.2f}')
            if not voice_name:
                warnings.append(f'Не вказано голос для #g{g_num}')

            cache_key = _make_cache_key(voice_name, text_body, speed_eff)

            if cache_key in audio_cache:
                sr, audio_np = audio_cache[cache_key]
                cache_hits += 1
                print(f"💾 КЕШ ХІТ #{cache_hits}: Part {idx} (g{g_num})")
            else:
                cache_misses += 1
                print(f"🔊 Генерація аудіо #{cache_misses}: Part {idx} (g{g_num})")

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_synthesize_chunk, text_body, voice_name, speed_eff)

                    while not future.done():
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
                        audio_cache[cache_key] = (sr, audio_np)
                    except Exception as e:
                        print(f'Error processing part {idx}: {e}')
                        raise

            if base_sr is None:
                base_sr = sr

            extra_info = {
                "type": "voice",
                "g": g_num,
                "voice_name": voice_name,
                "speed_eff": speed_eff,
                "text_len": len(text_body),
                "text_body": text_body,
                "cached": cache_key in audio_cache and idx > 1,
            }

        # ── SFX ───────────────────────────────────────────────────────────────
        elif event_type == 'sfx':
            sfx_id = event.get('id')
            target_sr = base_sr if base_sr else default_sr

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_load_and_process_sfx, sfx_id, target_sr)

                while not future.done():
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

        # ── Запис аудіо (voice / sfx) ─────────────────────────────────────────
        audio_filename = os.path.join(output_dir, f"part_{idx:03}.wav")
        sf.write(audio_filename, audio_np, sr)

        if save_option == 'Зберегти всі частини озвученого тексту' and extra_info["type"] == "voice":
            txt_filename = os.path.join(output_dir, f"part_{idx:03}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as txt_file:
                txt_file.write(extra_info["text_body"])

        if extra_info["type"] == "voice":
            cached_marker = "💾 [CACHED]" if extra_info.get("cached", False) else "🔊 [NEW]"
            print(f'{cached_marker} Part {idx}: type=voice, g={extra_info["g"]}, '
                  f'voice={extra_info["voice_name"]}, '
                  f'speed={extra_info["speed_eff"]:.2f}, '
                  f'text_len={extra_info["text_len"]}, '
                  f'path={audio_filename}')
        else:
            print(f'#{extra_info["sfx_id"]} --- file "{extra_info["file"]}" '
                  f'-- {os.path.basename(audio_filename)}')

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

    # ── Завершення ────────────────────────────────────────────────────────────
    total_elapsed_secs = int(time.time() - global_start)
    total_formatted = format_hms(total_elapsed_secs)
    finish_time_str = time.strftime('%H:%M:%S', time.localtime(time.time()))

    print(f'Finished: {finish_time_str}, duration: {total_formatted}, parts: {len(events)}')
    print(f'📊 Статистика кешу: Хітів={cache_hits}, Пропусків={cache_misses}, '
          f'Економія={cache_hits}/{cache_hits + cache_misses} '
          f'({100 * cache_hits / max(1, cache_hits + cache_misses):.1f}%)')

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
