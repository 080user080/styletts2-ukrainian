"""
Розширений Gradio UI для TTS з підтримкою Multi Dialog, SFX та налаштувань спікерів.
Інтегрується у модульну систему через app_context.
"""

import os
import time
import re
import unicodedata
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Iterable, List, Sequence, Tuple
from datetime import datetime

import gradio as gr
import numpy as np
import soundfile as sf
import yaml
from scipy import signal
import math

# Константи
SPEAKER_MAX = 30
PROGRESS_POLL_INTERVAL = 1.0
DEFAULT_SPEED_CODE = 0.88
OUTPUT_DIR_BASE = "output_audio"

# Глобальні змінні (будуть ініціалізовані в initialize)
_app_context = None
_tts_engine = None
_logger = None
SFX_CONFIG = {}
DEFAULT_SPEED = DEFAULT_SPEED_CODE


def initialize(app_context: Dict[str, Any]) -> Dict[str, Any]:
    """Ініціалізація модуля розширеного Gradio UI"""
    global _app_context, _tts_engine, _logger, SFX_CONFIG, DEFAULT_SPEED
    
    _app_context = app_context
    _logger = app_context.get('logger')
    _tts_engine = app_context.get('tts_engine')
    
    if not _tts_engine:
        raise RuntimeError("TTS Engine не знайдено в app_context")
    
    # Завантажити конфіг SFX
    SFX_CONFIG = _load_sfx_config()
    DEFAULT_SPEED = float(SFX_CONFIG.get("default_speed", DEFAULT_SPEED_CODE))
    
    _logger.info("🎨 Розширений Gradio UI ініціалізовано")
    
    # Створити та повернути інтерфейс
    demo = create_advanced_interface()
    
    return {
        'demo': demo,
        'launch': lambda: demo.queue().launch()
    }


# ============================================================================
# УТИЛІТИ ТА ДОПОМІЖНІ ФУНКЦІЇ
# ============================================================================

def make_session_output_dir(base: str = OUTPUT_DIR_BASE) -> str:
    """Створює папку для поточної сесії з timestamp"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(base, ts)
    try:
        os.makedirs(out, exist_ok=True)
    except Exception:
        out = base
        os.makedirs(out, exist_ok=True)
    return out


OUTPUT_DIR = make_session_output_dir()


def _load_sfx_config(path: str = "sfx.yaml") -> dict:
    """Завантажує конфігурацію SFX з YAML"""
    cfg = {"normalize_dbfs": -16, "sounds": {}}
    candidates = [
        os.path.join(os.getcwd(), "sfx.yaml"),
        os.path.join(os.getcwd(), "sound", "sfx.yaml"),
    ]
    found = None
    for p in candidates:
        if os.path.exists(p):
            found = p
            break
    if not found:
        return cfg
    try:
        with open(found, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                cfg.update(data)
        cfg["_cfg_dir"] = os.path.dirname(found)
    except Exception:
        pass
    return cfg


def get_sfx_config() -> dict:
    """Динамічне читання sfx.yaml"""
    return _load_sfx_config()


def format_hms(seconds):
    """Форматує секунди у HH:MM:SS"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"


def normalize_text(s: str) -> str:
    """Нормалізує текст, зберігаючи '+'"""
    if not isinstance(s, str):
        return s
    s = unicodedata.normalize("NFKC", s).replace("\ufeff", "")
    s = (s.replace("'","'").replace("ʼ","'").replace("ʻ","'").replace("ʹ","'")
           .replace("—","-").replace("–","-").replace("−","-"))
    out = []
    for ch in s:
        if ch == '+':
            out.append(ch)
            continue
        cat = unicodedata.category(ch)
        if cat in ("Cf","Cc") and ch not in ("\n","\r","\t"):
            continue
        out.append(ch)
    s = "".join(out)
    s = s.replace("\u00A0", " ")
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s


# ============================================================================
# PARSER ПОДІЙ СЦЕНАРІЮ
# ============================================================================

def parse_script_events(text: str, voices_flat: List[str]) -> List[dict]:
    """
    Парсить сценарій у список подій (voice/sfx).
    
    Формат:
    - #gN[_slow|_fast|_slowNN|_fastNN]: текст -> voice подія
    - #<sfx_id> -> sfx подія
    """
    events: List[dict] = []
    if not isinstance(text, str):
        return events
    
    lines = normalize_text(text).splitlines()
    voice_pat = re.compile(r"^#g\s*([1-9]|[12][0-9]|30)(?:_((?:slow|fast)(?:\d{1,3})?))?\s*:??\s+(.*)$", re.IGNORECASE)
    sfx_pat = re.compile(r'^#([A-Za-z0-9_]+)\s*$', re.IGNORECASE)
    
    for line_no, raw_ln in enumerate(lines, start=1):
        ln = raw_ln.strip()
        if not ln:
            continue
        
        # Voice подія
        m_voice = voice_pat.match(ln)
        if m_voice:
            g_str, suffix, text_body = m_voice.groups()
            g_num = int(g_str)
            suffix = suffix.lower() if suffix else ""
            if not text_body.strip():
                raise RuntimeError(f"Порожній текст після тега #g{g_num} на рядку {line_no}")
            if g_num < 1 or g_num > SPEAKER_MAX:
                raise RuntimeError(f"Неприпустимий номер спікера: {g_num} на рядку {line_no}")
            events.append({"type": "voice", "g": g_num, "suffix": suffix, "text": text_body})
            continue
        
        # SFX подія
        m_sfx = sfx_pat.match(ln)
        if m_sfx:
            sfx_id = m_sfx.group(1)
            if sfx_id not in SFX_CONFIG.get('sounds', {}):
                raise RuntimeError(f"SFX '{sfx_id}' не знайдено у sfx.yaml (рядок {line_no})")
            events.append({"type": "sfx", "id": sfx_id, "params": {}})
            continue
        
        # Коментар
        if ln.startswith('#'):
            continue
        
        # Звичайний текст -> g1
        events.append({"type": "voice", "g": 1, "suffix": "", "text": ln})
    
    return events


# ============================================================================
# ОБЧИСЛЕННЯ ШВИДКОСТІ
# ============================================================================

def _compute_speed_effective(g_num: int, suffix: str, speeds_flat: List[float], ignore_speed: bool) -> float:
    """Обчислює ефективну швидкість для voice події"""
    if ignore_speed:
        return DEFAULT_SPEED
    
    suf = suffix.lower() if suffix else ""
    
    if suf == 'slow':
        return 0.80
    if suf == 'fast':
        return 1.20
    if suf.startswith('slow') and len(suf) > 4:
        try:
            return float(suf[4:]) / 100.0
        except Exception:
            pass
    if suf.startswith('fast') and len(suf) > 4:
        try:
            return float(suf[4:]) / 100.0
        except Exception:
            pass
    
    if 1 <= g_num <= len(speeds_flat):
        try:
            return float(speeds_flat[g_num - 1])
        except Exception:
            pass
    
    return DEFAULT_SPEED


# ============================================================================
# СИНТЕЗ ТА ОБРОБКА АУДІО
# ============================================================================

def _synthesize_chunk(chunk: str, voice: str | None, speed: float) -> Tuple[int, np.ndarray]:
    """Синтезує один шматок тексту через TTS Engine"""
    global _tts_engine
    
    if not _tts_engine:
        raise RuntimeError("TTS Engine не ініціалізовано")
    
    # Викликаємо метод синтезу з TTS Engine
    result = _tts_engine.synthesize(
        text=chunk,
        voice=voice,
        speed=speed
    )
    
    return result['sample_rate'], result['audio']


def _load_and_process_sfx(sfx_id: str, target_sr: int) -> Tuple[int, np.ndarray]:
    """Завантажує та обробляє SFX файл"""
    cfg_all = get_sfx_config()
    cfg = cfg_all.get('sounds', {}).get(sfx_id)
    if not cfg:
        raise RuntimeError(f"SFX конфігурація відсутня для '{sfx_id}'")
    
    src_file = cfg.get('file')
    if not src_file:
        raise RuntimeError(f"Файл для SFX '{sfx_id}' не вказаний")
    
    # Пошук файлу
    possible_paths = [
        src_file,
        os.path.join(os.getcwd(), src_file),
        os.path.join(OUTPUT_DIR, src_file),
    ]
    cfg_dir = cfg_all.get("_cfg_dir")
    if cfg_dir:
        possible_paths.append(os.path.join(cfg_dir, src_file))
        possible_paths.append(os.path.join(cfg_dir, "sound", src_file))
    
    audio_path = None
    for p in possible_paths:
        if p and os.path.exists(p):
            audio_path = p
            break
    
    if not audio_path:
        raise RuntimeError(f"Файл SFX '{src_file}' не знайдено (id: '{sfx_id}')")
    
    # Читання аудіо
    data, sr = sf.read(audio_path)
    data = np.asarray(data, dtype=np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1)
    
    # Ресемпл
    if sr != target_sr:
        duration = data.shape[0] / sr
        target_len = int(round(duration * target_sr))
        if target_len <= 0:
            target_len = 1
        data = signal.resample(data, target_len)
        sr = target_sr
    
    # Нормалізація
    normalize_dbfs = cfg_all.get('normalize_dbfs')
    if cfg.get('normalize') is False:
        normalize_dbfs = None
    
    rms = math.sqrt(np.mean(data ** 2)) if data.size else 0.0
    if rms > 0:
        current_dbfs = 20 * math.log10(rms)
    else:
        current_dbfs = -float('inf')
    
    total_gain_db = float(cfg.get('gain_db', 0.0))
    if normalize_dbfs is not None and current_dbfs > -float('inf'):
        total_gain_db += (float(normalize_dbfs) - current_dbfs)
    
    gain_factor = 10.0 ** (total_gain_db / 20.0)
    data = data * gain_factor
    
    # Fade in/out
    fade_ms = 30
    fade_len = int(sr * fade_ms / 1000.0)
    fade_len = max(fade_len, 1)
    
    if data.size >= fade_len:
        ramp_in = np.linspace(0.0, 1.0, fade_len, dtype=data.dtype)
        data[:fade_len] *= ramp_in
        ramp_out = np.linspace(1.0, 0.0, fade_len, dtype=data.dtype)
        data[-fade_len:] *= ramp_out
    
    return sr, data


# ============================================================================
# BATCH СИНТЕЗ З ПОДІЯМИ
# ============================================================================

def batch_synthesize_dialog_events(
    text_input: str | None,
    file_path: str | None,
    speeds_flat: list,
    voices_flat: list,
    save_option,
    ignore_speed: bool = False,
) -> Iterable:
    """Основна функція пакетного синтезу з підтримкою подій"""
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global_start = time.time()
    
    # Читання тексту
    if text_input and text_input.strip():
        text = text_input
    elif file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        raise RuntimeError("Немає тексту для озвучення")
    
    start_time_str = time.strftime('%H:%M:%S', time.localtime(global_start))
    
    # Парсинг подій
    try:
        events = parse_script_events(text, voices_flat)
    except Exception as e:
        if _logger:
            _logger.error(f"Помилка парсингу: {e}")
        raise
    
    total_parts = max(1, len(events))
    times_per_part: List[float] = []
    warnings: List[str] = []
    base_sr: int | None = None
    
    voice_map = {i + 1: (voices_flat[i] if i < len(voices_flat) else None) for i in range(SPEAKER_MAX)}
    
    # Початковий yield
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
    
    # Обробка подій
    for idx, event in enumerate(events, start=1):
        part_start = time.time()
        
        if event.get('type') == 'voice':
            g_num = event.get('g')
            suffix = event.get('suffix', '')
            text_body = event.get('text', '')
            voice_name = voice_map.get(g_num, None)
            speed_eff = _compute_speed_effective(g_num, suffix, speeds_flat, ignore_speed)
            
            if not ignore_speed and (speed_eff < 0.7 or speed_eff > 1.3):
                warnings.append(f'Швидкість поза межами для #g{g_num}: {speed_eff:.2f}')
            if not voice_name:
                warnings.append(f'Голос не вказано для #g{g_num}')
            
            call_func = _synthesize_chunk
            call_args = (text_body, voice_name, speed_eff)
            extra_info = {
                "type": "voice",
                "g": g_num,
                "voice_name": voice_name,
                "speed_eff": speed_eff,
                "text_body": text_body,
            }
        
        elif event.get('type') == 'sfx':
            sfx_id = event.get('id')
            target_sr = base_sr if base_sr else 24000
            call_func = _load_and_process_sfx
            call_args = (sfx_id, target_sr)
            cfg = SFX_CONFIG.get('sounds', {}).get(sfx_id, {})
            extra_info = {
                "type": "sfx",
                "sfx_id": sfx_id,
                "file": cfg.get('file'),
            }
        else:
            warnings.append(f"Невідомий тип події: {event}")
            continue
        
        # Виконання з прогресом
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call_func, *call_args)
            
            while not future.done():
                now = time.time()
                elapsed = int(now - global_start)
                elapsed_str = f"{elapsed} сек --- {format_hms(elapsed)}"
                est_finish_str = 'Розрахунок...'
                rem_text = 'Розрахунок...'
                
                if times_per_part:
                    avg_time = sum(times_per_part) / len(times_per_part)
                    est_total_time = avg_time * total_parts
                    est_finish_str = time.strftime('%H:%M:%S', time.localtime(global_start + est_total_time))
                    rem_secs = int(global_start + est_total_time - now)
                    rem_min, rem_sec = divmod(max(rem_secs, 0), 60)
                    rem_text = f"залишилось {rem_min} хв {rem_sec} сек"
                
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
                if _logger:
                    _logger.error(f'Помилка обробки частини {idx}: {e}')
                raise
        
        if extra_info["type"] == "voice" and base_sr is None:
            base_sr = sr
        
        # Збереження
        audio_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.wav")
        sf.write(audio_filename, audio_np, sr)
        
        if save_option == 'Зберегти всі частини' and extra_info["type"] == "voice":
            txt_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(extra_info["text_body"])
        
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
    
    if warnings and _logger:
        for w in warnings:
            _logger.warning(w)
    
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


# ============================================================================
# СТВОРЕННЯ GRADIO ІНТЕРФЕЙСУ
# ============================================================================

def create_advanced_interface():
    """Створює розширений Gradio інтерфейс"""
    
    # Отримати список голосів з TTS Engine
    speaker_choices = _tts_engine.get_available_voices() if _tts_engine else ["default"]
    
    with gr.Blocks(title="TTS Multi Dialog Advanced") as demo:
        gr.Markdown("# 🎙️ TTS Multi Dialog - Розширений режим")
        
        with gr.Row():
            text_input = gr.Textbox(
                label='📋 Текст для озвучення',
                lines=10,
                placeholder='#g1: Привіт!\n#g2_fast: Як справи?\n#sfx_bell\n#g1_slow: До побачення!'
            )
        
        with gr.Row():
            file_input = gr.File(label='📂 Або завантажте файл', type='filepath')
        
        # Компоненти для 30 спікерів
        voice_components = []
        speed_components = []
        
        with gr.Accordion("⚙️ Налаштування спікерів #g1-#g3", open=True):
            with gr.Row():
                for i in range(1, 4):
                    with gr.Column():
                        voice_components.append(
                            gr.Dropdown(
                                label=f'Голос #g{i}',
                                choices=speaker_choices,
                                value=speaker_choices[0]
                            )
                        )
                        speed_components.append(
                            gr.Slider(0.7, 1.3, value=0.88, label=f'Швидкість #g{i}')
                        )
        
        with gr.Accordion("⚙️ Додаткові спікери #g4-#g30", open=False):
            for row_start in range(4, 31, 3):
                with gr.Row():
                    for i in range(row_start, min(row_start + 3, 31)):
                        with gr.Column():
                            voice_components.append(
                                gr.Dropdown(
                                    label=f'Голос #g{i}',
                                    choices=speaker_choices,
                                    value=speaker_choices[0],
                                    visible=False
                                )
                            )
                            speed_components.append(
                                gr.Slider(0.7, 1.3, value=0.88, label=f'Швидкість #g{i}', visible=False)
                            )
        
        with gr.Row():
            ignore_speed_chk = gr.Checkbox(label='Ігнорувати швидкість', value=False)
            save_option = gr.Radio(
                choices=['Зберегти всі частини', 'Без збереження'],
                label='Опції збереження',
                value='Без збереження'
            )
        
        btn_start = gr.Button('▶️ Розпочати', variant='primary')
        
        # Прогрес
        with gr.Row():
            output_audio = gr.Audio(label='🔊 Поточна частина', type='filepath')
            part_slider = gr.Slider(label='Частина', minimum=1, maximum=1, step=1, value=1)
        
        with gr.Row():
            timer_text = gr.Textbox(label="⏱️ Час", value="0", interactive=False)
            start_time_text = gr.Textbox(label="Початок", interactive=False)
            end_time_text = gr.Textbox(label="Кінець", interactive=False)
        
        with gr.Row():
            parts_progress = gr.Slider(label='Прогрес', minimum=0, maximum=1, step=1, value=0)
            est_end_time_text = gr.Textbox(label="Прогноз", interactive=False)
            remaining_time_text = gr.Textbox(label="Залишилось", interactive=False)
        
        # Синтаксис
        with gr.Accordion("📖 Синтаксис тегів", open=False):
            gr.Markdown("""
            **Формат команд:**
            - `#gN: текст` — озвучити голосом №N (1-30)
            - `#gN_slow` / `#gN_fast` — повільно (0.80) / швидко (1.20)
            - `#gN_slow95` / `#gN_fast110` — точна швидкість (0.95 / 1.10)
            - `#<sfx_id>` — вставити звуковий ефект із sfx.yaml
            
            **Приклад:**
            ```
            #g1: Привіт, як справи?
            #g2_fast: Чудово, дякую!
            #sfx_bell
            #g1_slow95: До зустрічі!
            ```
            """)
        
        # Обробник запуску
        def on_start(text_input, file_input, *flat_values):
            global SFX_CONFIG, DEFAULT_SPEED
            try:
                SFX_CONFIG = get_sfx_config()
                DEFAULT_SPEED = float(SFX_CONFIG.get("default_speed", DEFAULT_SPEED_CODE))
            except Exception as e:
                if _logger:
                    _logger.warning(f"Не вдалось перезавантажити sfx.yaml: {e}")
            
            speeds = list(flat_values[:30])
            voices = list(flat_values[30:60])
            save_opt = flat_values[60] if len(flat_values) > 60 else None
            ignore_speed = bool(flat_values[61]) if len(flat_values) > 61 else False
            
            yield from batch_synthesize_dialog_events(
                text_input, file_input, speeds, voices, save_opt, ignore_speed
            )
        
        btn_start.click(
            fn=on_start,
            inputs=[text_input, file_input] + speed_components + voice_components + [save_option, ignore_speed_chk],
            outputs=[
                output_audio, part_slider, timer_text, start_time_text,
                end_time_text, est_end_time_text, remaining_time_text, parts_progress
            ],
            show_progress=False
        )
    
    return demo


# Експорт для модульної системи
__all__ = ['initialize']
