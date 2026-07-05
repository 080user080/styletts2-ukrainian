# GPT: Прибрано індивідуальні повідомлення; додане одне зведене в кінці.
# GPT: В повідомленні виправлено текст на "Обробка тривала  ГГ:ХХ:СС".
# Додати нові імпорти після існуючих
import concurrent.futures
from functools import partial

# Залишити всі інші імпорти без змін
import io
import os
import re
import math
import sys
import time
from datetime import datetime
from tkinter import Tk, filedialog, BooleanVar, IntVar, StringVar, DoubleVar, ttk, messagebox
import subprocess
import tempfile
import tkinter as tk
import threading

import numpy as np
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter, low_pass_filter
from tqdm import tqdm
from multiprocessing import Pool, cpu_count

DEFAULT_CHUNK_MS = 40 * 1000
DEFAULT_PAUSE_MS = 950

# НОВЕ: скільки батчів (читання+обробка+ffmpeg-експорт) виконувати одночасно.
# Кожен батч під час експорту запускає окремий процес ffmpeg (одне ядро), тож
# MAX_CONCURRENT_BATCHES одночасних батчів = стільки ж ядер зайнято кодуванням
# паралельно. На Ryzen 7 7700 (8 ядер/16 потоків) 4 — розумний баланс: лишає
# ядра ще й для потоків читання файлів. Можна підняти до 6-8, якщо диск і
# пам'ять тримають навантаження.
MAX_CONCURRENT_BATCHES = 4

# GPT: Додано параметри динамічних пауз за замовчуванням
DEFAULT_MIN_PAUSE = 290
DEFAULT_MAX_PAUSE = 1100
DEFAULT_MIN_AUDIO_DUR = 3 * 1000
DEFAULT_MAX_AUDIO_DUR = 120 * 1000

# GPT: Додано функцію генерації pink noise room tone
def generate_pink_noise(duration_ms, frame_rate, channels, gain_db=-50, lp_cutoff=2500):
    """Генерує Brown Noise (коричневий шум) для м'якого, низькочастотного фону"""
    sample_rate = frame_rate
    num_samples = int(sample_rate * duration_ms / 1000)
    
    # Генерація білого шуму
    white = np.random.normal(0, 1, num_samples * channels)
    
    # Перетворення білого шуму на коричневий шляхом інтеграції (накопичення)
    white = white.reshape((num_samples, channels))
    brown = np.apply_along_axis(np.cumsum, 0, white)

    # Нормалізація та застосування gain
    brown = brown / np.max(np.abs(brown))
    brown = brown * (10 ** (gain_db / 20))
    
    # Конвертація в AudioSegment
    brown_flat = brown.flatten()
    pink_int = np.int16(brown_flat * 32767)
    audio = AudioSegment(
        pink_int.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=channels
    )
    
    return audio.low_pass_filter(lp_cutoff)

AudioSegment.converter = "C:\\ffmpeg\\bin\\ffmpeg.exe"

def _format_hms(seconds):
    """Повертає рядок ГГ:ХХ:СС з округленням до секунд."""  # GPT
    s = int(round(seconds))
    hh = s // 3600
    mm = (s % 3600) // 60
    ss = s % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"

# НОВЕ: природне сортування за іменем файлу (щоб "file2.wav" йшов перед "file10.wav",
# а не після, як було б при звичайному текстовому сортуванні). Потрібно для того, щоб
# розбиття на батчі 1-1000 / 1001-2000 і т.д. відповідало реальному порядку файлів,
# незалежно від того, в якому порядку вони були обрані в діалозі вибору файлів.
def natural_sort_key(path):
    name = os.path.basename(path)
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r'(\d+)', name)]

# ЯКІР: Додати нові функції після _format_hms
# ВИПРАВЛЕНО: раніше тут писався повний WAV на диск у тимчасовий файл, а потім ffmpeg
# читав його назад із диска — для великого об'єднаного аудіо це подвійний прохід
# через диск (запис + читання) на кожен батч, і саме це, а не сама математика
# кодування, було вузьким місцем (звідси й 7-18% CPU — ffmpeg на одному ядрі +
# накладні витрати на I/O). Тепер WAV пишеться в оперативну пам'ять (io.BytesIO),
# і ці байти передаються в ffmpeg напряму через stdin (pipe) — диск взагалі не
# використовується для проміжних даних.
def export_mp3_fast(segment, out_path):
    """Експорт у mp3 без проміжного файлу на диску: WAV формується в RAM, ffmpeg отримує
    його через stdin (pipe)."""
    try:
        wav_buffer = io.BytesIO()
        segment.export(wav_buffer, format='wav')
        wav_bytes = wav_buffer.getvalue()
        wav_buffer.close()

        # -threads 0 прибрано: libmp3lame однопотоковий, цей параметр для аудіокодеків
        # нічого не дає (працює лише для відео), тож він тільки вводив в оману.
        cmd = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "-i", "pipe:0",
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            "-y",  # Перезаписуємо якщо файл існує
            out_path
        ]

        subprocess.run(cmd, input=wav_bytes, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    except Exception as e:
        print(f"❌ Помилка експорту: {e}")
        # Резервний варіант (теж без диска — через pydub напряму)
        segment.export(out_path, format='mp3', bitrate='320k')

def calculate_optimal_chunk_size(duration_ms):
    """Динамічний розрахунок розміру чанку для оптимізації швидкості"""
    if duration_ms < 180000:    # < 3 хвилини
        return 20000            # 20 сек
    elif duration_ms < 600000:  # 3-10 хвилин  
        return 35000            # 35 сек
    else:                       # > 10 хвилин
        return 50000            # 50 сек

def process_files_parallel(file_data_list, options):
    """Паралельна обробка всіх файлів за допомогою потоків"""
    results = []
    
    def process_single_file(file_data):
        return process_file(file_data[0], file_data[1], options)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(15, len(file_data_list))) as executor:
        futures = [executor.submit(process_single_file, fd) for fd in file_data_list]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    return results

def process_chunk(args):
    (index, raw_data, sample_width, frame_rate, channels,
     do_normalize, do_hp, hp_cutoff, do_lp, lp_cutoff) = args

    chunk = AudioSegment(
        data=raw_data,
        sample_width=sample_width,
        frame_rate=frame_rate,
        channels=channels
    )

    if do_normalize:
        try:
            chunk = normalize(chunk)
        except Exception:
            pass

    if do_hp:
        try:
            chunk = high_pass_filter(chunk, cutoff=hp_cutoff)
        except Exception:
            pass
    if do_lp:
        try:
            chunk = low_pass_filter(chunk, cutoff=lp_cutoff)
        except Exception:
            pass

    return index, chunk.raw_data

# GPT: Винесена функція, яка повертає AudioSegment і тривалість обробки (elapsed)
def process_file_to_segment(wav_path, options, progress_callback=None): # Додано progress_callback
    base_name = os.path.splitext(os.path.basename(wav_path))[0]

    start_time = time.time()  # GPT: початок обробки цього файлу
    print(f"\n🔊 Обробка файлу: {wav_path}")
    print(f"🕒 Початок: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")

    try:
        audio = AudioSegment.from_wav(wav_path)
    except Exception as e:
        print(f"❌ Помилка завантаження файлу {wav_path}: {e}")
        return AudioSegment.empty(), 0

    duration_ms = len(audio)
    if duration_ms == 0:
        print(f"⚠️ Попередження: файл {wav_path} має нульову тривалість")
        return AudioSegment.empty(), 0

    # ПРОСТА ОБРОБКА БЕЗ ЧАНКІВ - це швидше для невеликих файлів
    if options['normalize']:
        try:
            audio = normalize(audio)
        except Exception:
            pass

    if options['high_pass']:
        try:
            audio = high_pass_filter(audio, cutoff=options['hp_cutoff'])
        except Exception:
            pass

    if options['low_pass']:
        try:
            audio = low_pass_filter(audio, cutoff=options['lp_cutoff'])
        except Exception:
            pass

    end_time = time.time()
    elapsed = end_time - start_time
    print(f"⏱ Обробка тривала {elapsed:.2f} секунд")
    return audio, elapsed

# ВИПРАВЛЕНО: попередня версія робила combined = combined + gap + segments[i] у циклі —
# кожен "+" в pydub копіює вже накопичений буфер заново, тобто на 1000 файлах це O(n^2)
# (з кожним кроком копіюється дедалі більший шматок пам'яті). Через це процес був повільним,
# але майже не навантажував CPU — то було просто повільне послідовне копіювання пам'яті.
# Нова версія збирає сирі байти (raw_data) у список і склеює їх ОДИН РАЗ в кінці через b''.join() — O(n).
def combine_audio_segments_optimized(segments, pause_duration_func=None, room_tone_func=None):
    """Ефективне об'єднання аудіо-сегментів через одноразове склеювання сирих байтів (O(n))"""
    if not segments:
        return AudioSegment.empty()

    if len(segments) == 1:
        return segments[0]

    sample_width = segments[0].sample_width
    frame_rate = segments[0].frame_rate
    channels = segments[0].channels

    raw_parts = [segments[0].raw_data]

    for i in range(1, len(segments)):
        pause_duration = pause_duration_func(len(segments[i - 1])) if pause_duration_func else 0
        if pause_duration and pause_duration > 0:
            gap = room_tone_func(pause_duration) if room_tone_func else AudioSegment.silent(
                duration=pause_duration, frame_rate=frame_rate
            )
            raw_parts.append(gap.raw_data)
        raw_parts.append(segments[i].raw_data)

    combined_raw = b''.join(raw_parts)

    return AudioSegment(
        data=combined_raw,
        sample_width=sample_width,
        frame_rate=frame_rate,
        channels=channels
    )


# НОВЕ: паралельне читання/обробка WAV-файлів (потоками — I/O звільняє GIL, тож на NVMe
# це реально дає приріст, бо диск легко тримає багато одночасних запитів читання).
# Порядок результатів зберігається (важливо для правильного порядку об'єднання).
def read_and_process_files_parallel(paths, options, progress_callback=None, max_workers=16):
    """Паралельно завантажує і обробляє (normalize/hp/lp якщо увімкнено) список WAV-файлів,
    зберігаючи вихідний порядок."""
    results = [None] * len(paths)

    def worker(idx, path):
        try:
            seg, _elapsed = process_file_to_segment(path, options)
        except Exception as e:
            print(f"❌ Помилка при обробці файлу {path}: {e}")
            seg = AudioSegment.empty()
        return idx, seg

    workers = min(max_workers, max(1, len(paths)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker, i, p) for i, p in enumerate(paths)]
        for future in concurrent.futures.as_completed(futures):
            idx, seg = future.result()
            results[idx] = seg
            if progress_callback:
                progress_callback()

    return results

# GPT: існуюча функція експорту (трохи спрощена)
def export_mp3(segment, out_path):
    buffer = io.BytesIO()
    segment.export(buffer, format='mp3', bitrate='320k')
    with open(out_path, 'wb') as f:
        f.write(buffer.getvalue())
    buffer.close()

# GPT: Оновлена версія — не показує діалог; повертає saved paths і час експорту
def process_file(wav_path, output_dir, options):
    start_all = time.time()  # GPT: початок для цього файлу (включно з експортом)
    base_name = os.path.splitext(os.path.basename(wav_path))[0]
    final_audio, proc_elapsed = process_file_to_segment(wav_path, options)
    
    # Перевіряємо, чи отримали ми непорожній аудіо
    if len(final_audio) == 0:
        print(f"⚠️ Попередження: файл {wav_path} не оброблено (нульова тривалість)")
        return [], 0
    
    out_path = os.path.join(output_dir, f"{base_name}.mp3")
    # ЯКІР: Замінити на швидкий експорт
    export_mp3_fast(final_audio, out_path)
    end_all = time.time()
    total_elapsed = end_all - start_all  # GPT: тривалість від початку обробки цього файлу до завершення експорту
    print(f"✅ Збережено: {out_path}")
    return [out_path], total_elapsed  # GPT: повертаємо список збережених файлів та час (сек)

def build_gui():
    root = Tk()
    root.title("Batch WAV → MP3 — TTS Processing")

    wav_paths_var = []
    output_dir_var = StringVar(value='')

    # GPT: За замовчуванням вимкнені — normalize, high-pass, low-pass
    normalize_var = BooleanVar(value=False)  # GPT
    hp_var = BooleanVar(value=False)         # GPT
    lp_var = BooleanVar(value=False)         # GPT
    hp_cutoff_var = IntVar(value=100)
    lp_cutoff_var = IntVar(value=7000)
    # GPT: Додано змінні для динамічних пауз
    dynamic_pauses_var = BooleanVar(value=True)
    min_pause_var = IntVar(value=DEFAULT_MIN_PAUSE)
    max_pause_var = IntVar(value=DEFAULT_MAX_PAUSE)
    min_audio_dur_var = IntVar(value=DEFAULT_MIN_AUDIO_DUR/1000)
    max_audio_dur_var = IntVar(value=DEFAULT_MAX_AUDIO_DUR/1000)

    # GPT: Додано змінну для room tone
    room_tone_var = BooleanVar(value=True)

    chunk_ms_var = IntVar(value=DEFAULT_CHUNK_MS)
    pause_ms_var = IntVar(value=DEFAULT_PAUSE_MS)  # GPT: пауза між з'єднаними файлами

    combine_var = BooleanVar(value=True)  # GPT: За замовчуванням увімкнено об'єднання

    # НОВЕ: розбиття великої кількості обраних файлів на батчі (групи по N файлів),
    # кожна група — окремий об'єднаний mp3. Дозволяє обрати всі 3500+ файлів одразу,
    # без ручного повторного вибору по 1000.
    # За замовчуванням увімкнено, розмір батчу — 500 файлів.
    batch_var = BooleanVar(value=True)
    batch_size_var = IntVar(value=500)

    frame_top = ttk.Frame(root, padding=8)
    frame_top.grid(row=0, column=0, sticky='ew')

    def select_wavs():
        paths = filedialog.askopenfilenames(title='Оберіть WAV файли', filetypes=[('WAV', '*.wav')])
        if paths:
            wav_paths_var.clear()
            wav_paths_var.extend(list(paths))
            lbl_files.config(text=f"Обрано {len(wav_paths_var)} файлів")

    def select_outdir():
        d = filedialog.askdirectory(title='Оберіть папку для збереження MP3')
        if d:
            output_dir_var.set(d)
            lbl_outdir.config(text=d)

    btn_select = ttk.Button(frame_top, text='Оберіть WAV файли', command=select_wavs)
    btn_select.grid(row=0, column=0, padx=4, pady=4)
    lbl_files = ttk.Label(frame_top, text='Файли не обрано')
    lbl_files.grid(row=0, column=1, padx=4)

    btn_out = ttk.Button(frame_top, text='Оберіть папку для збереження', command=select_outdir)
    btn_out.grid(row=1, column=0, padx=4, pady=4)
    lbl_outdir = ttk.Label(frame_top, text='Папку не обрано')
    lbl_outdir.grid(row=1, column=1, padx=4)

    frame_opts = ttk.LabelFrame(root, text='Опції обробки фрагментів', padding=8)
    frame_opts.grid(row=1, column=0, sticky='ew', padx=8, pady=6)

    chk_norm = ttk.Checkbutton(frame_opts, text='Нормалізація гучності', variable=normalize_var)
    chk_norm.grid(row=0, column=0, sticky='w')

    chk_hp = ttk.Checkbutton(frame_opts, text='High-pass (обрізати <)', variable=hp_var)
    chk_hp.grid(row=1, column=0, sticky='w')
    ttk.Label(frame_opts, text='cutoff (Hz):').grid(row=1, column=1, sticky='e')
    ttk.Entry(frame_opts, textvariable=hp_cutoff_var, width=8).grid(row=1, column=2, sticky='w')

    chk_lp = ttk.Checkbutton(frame_opts, text='Low-pass (обрізати >)', variable=lp_var)
    chk_lp.grid(row=2, column=0, sticky='w')
    ttk.Label(frame_opts, text='cutoff (Hz):').grid(row=2, column=1, sticky='e')
    ttk.Entry(frame_opts, textvariable=lp_cutoff_var, width=8).grid(row=2, column=2, sticky='w')

    ttk.Label(frame_opts, text='Розмір фрагмента (мс):').grid(row=3, column=0, sticky='w')
    ttk.Entry(frame_opts, textvariable=chunk_ms_var, width=12).grid(row=3, column=1, sticky='w')

    frame_sil = ttk.LabelFrame(root, text="Параметри паузи при з'єднанні (тільки для інформування)", padding=8)
    frame_sil.grid(row=2, column=0, sticky='ew', padx=8, pady=6)

    ttk.Label(frame_sil, text='Довжина паузи між частинами (мс):').grid(row=0, column=0, sticky='w')
    ttk.Entry(frame_sil, textvariable=pause_ms_var, width=8).grid(row=0, column=1, sticky='w')

    frame_join = ttk.LabelFrame(root, text="Обробка вибраних файлів", padding=8)
    frame_join.grid(row=3, column=0, sticky='ew', padx=8, pady=6)

    # GPT: чекбокс для об'єднання всіх вибраних у 1 MP3 (текст "Обєднати" без апострофа)
    chk_combine = ttk.Checkbutton(frame_join, text='Обєднати всі вибрані WAV в один MP3', variable=combine_var)
    chk_combine.grid(row=0, column=0, sticky='w')

    lbl_note = ttk.Label(frame_join, text='(Якщо не обрано — 1 вхідний → 1 MP3)', foreground='gray')
    lbl_note.grid(row=1, column=0, sticky='w')

    # НОВЕ: розбиття на батчі — актуально коли обрано об'єднання, але файлів дуже багато
    # (напр. 3500+) і потрібно кілька окремих mp3 замість одного величезного.
    chk_batch = ttk.Checkbutton(frame_join, text='Розділити на батчі по N файлів', variable=batch_var)
    chk_batch.grid(row=2, column=0, sticky='w', pady=(6, 0))
    ttk.Label(frame_join, text='Файлів у батчі:').grid(row=3, column=0, sticky='w')
    ent_batch_size = ttk.Entry(frame_join, textvariable=batch_size_var, width=8)
    ent_batch_size.grid(row=3, column=1, sticky='w', padx=4)
    lbl_batch_note = ttk.Label(
        frame_join,
        text='(Файли сортуються за іменем; кожен батч → свій mp3, напр. files_0001-1000.mp3)',
        foreground='gray'
    )
    lbl_batch_note.grid(row=4, column=0, columnspan=2, sticky='w')
    # GPT: Додано фрейм для динамічних пауз
    frame_dynamic_pauses = ttk.LabelFrame(root, text="Динамічні паузи між файлами", padding=8)
    frame_dynamic_pauses.grid(row=4, column=0, sticky='ew', padx=8, pady=6)

    chk_dynamic = ttk.Checkbutton(frame_dynamic_pauses, text='Увімкнути динамічні паузи', variable=dynamic_pauses_var)
    chk_dynamic.grid(row=0, column=0, columnspan=2, sticky='w')

    ttk.Label(frame_dynamic_pauses, text='Мін. пауза (мс):').grid(row=1, column=0, sticky='w')
    ent_min_pause = ttk.Entry(frame_dynamic_pauses, textvariable=min_pause_var, width=8)
    ent_min_pause.grid(row=1, column=1, sticky='w', padx=4)

    ttk.Label(frame_dynamic_pauses, text='Макс. пауза (мс):').grid(row=1, column=2, sticky='w')
    ent_max_pause = ttk.Entry(frame_dynamic_pauses, textvariable=max_pause_var, width=8)
    ent_max_pause.grid(row=1, column=3, sticky='w', padx=4)

    ttk.Label(frame_dynamic_pauses, text='Мін. трив. аудіо (сек):').grid(row=2, column=0, sticky='w')
    ent_min_dur = ttk.Entry(frame_dynamic_pauses, textvariable=min_audio_dur_var, width=8)
    ent_min_dur.grid(row=2, column=1, sticky='w', padx=4)

    ttk.Label(frame_dynamic_pauses, text='Макс. трив. аудіо (сек):').grid(row=2, column=2, sticky='w')
    ent_max_dur = ttk.Entry(frame_dynamic_pauses, textvariable=max_audio_dur_var, width=8)
    ent_max_dur.grid(row=2, column=3, sticky='w', padx=4)

    # GPT: Додано чекбокс для room tone
    frame_room_tone = ttk.LabelFrame(root, text="Room Tone - антишум", padding=8)
    frame_room_tone.grid(row=5, column=0, sticky='ew', padx=8, pady=6)
    chk_room_tone = ttk.Checkbutton(frame_room_tone, text='Room Tone – антишум у транспорті', variable=room_tone_var)
    chk_room_tone.grid(row=0, column=0, sticky='w')
    
    # GPT: Додано регулятор гучності шуму
    ttk.Label(frame_room_tone, text='Гучність шуму (dB):').grid(row=1, column=0, sticky='w')
    room_tone_gain_var = DoubleVar(value=-42.0)
    ent_room_tone_gain = ttk.Entry(frame_room_tone, textvariable=room_tone_gain_var, width=8)
    ent_room_tone_gain.grid(row=1, column=1, sticky='w', padx=4)

    frame_bottom = ttk.Frame(root, padding=8)
    frame_bottom.grid(row=6, column=0, sticky='ew')  # GPT: Змінено row з 5 на 6 через додавання room tone
    progress = ttk.Progressbar(frame_bottom, mode='determinate')
    progress.grid(row=0, column=0, columnspan=3, sticky='ew', pady=6)
    
    # Додаємо елемент, щоб показати статус
    lbl_status = ttk.Label(frame_bottom, text="Готовий до роботи.")
    lbl_status.grid(row=2, column=0, columnspan=3, sticky='w')

    # Головна функція, яка запускається по кліку
    def start_processing():
        btn_start.config(state=tk.DISABLED)
        lbl_status.config(text="Обробка почалася...")
        if not wav_paths_var:
            messagebox.showerror('Помилка', 'Файли не обрано')
            btn_start.config(state=tk.NORMAL)
            return

        if not output_dir_var.get():
            messagebox.showerror('Помилка', 'Папку для збереження не обрано')
            btn_start.config(state=tk.NORMAL)
            return

        # GPT: Якщо обрано combine і вибрано більше одного файлу — об'єднуємо
        if combine_var.get() and len(wav_paths_var) > 1:
            # GPT: Валідація параметрів динамічних пауз
            if dynamic_pauses_var.get():
                if min_pause_var.get() < 30:
                    messagebox.showerror('Помилка', 'Мінімальна пауза не може бути менше 30мс')
                    btn_start.config(state=tk.NORMAL)
                    return
                if max_pause_var.get() <= min_pause_var.get():
                    messagebox.showerror('Помилка', 'Максимальна пауза повинна бути більше мінімальної')
                    btn_start.config(state=tk.NORMAL)
                    return
                if min_audio_dur_var.get() * 1000 >= max_audio_dur_var.get() * 1000:
                    messagebox.showerror('Помилка', 'Максимальна тривалість аудіо повинна бути більше мінімальної')
                    btn_start.config(state=tk.NORMAL)
                    return
                if min_audio_dur_var.get() < 0 or max_audio_dur_var.get() < 0:
                    messagebox.showerror('Помилка', 'Тривалості аудіо не можуть бути від\'ємними')
                    btn_start.config(state=tk.NORMAL)
                    return

            # НОВЕ: валідація розміру батчу
            if batch_var.get() and batch_size_var.get() <= 0:
                messagebox.showerror('Помилка', 'Кількість файлів у батчі повинна бути більше 0')
                btn_start.config(state=tk.NORMAL)
                return

            # GPT: Функція для розрахунку динамічної паузи
            def calculate_dynamic_pause(audio_duration_ms):
                min_pause = max(30, min_pause_var.get())  # Мінімум 30мс
                max_pause = max_pause_var.get()
                min_dur = min_audio_dur_var.get() * 1000  # Конвертуємо секунди в мс
                max_dur = max_audio_dur_var.get() * 1000  # Конвертуємо секунди в мс
                
                if audio_duration_ms <= min_dur:
                    return min_pause
                elif audio_duration_ms >= max_dur:
                    return max_pause
                else:
                    ratio = (audio_duration_ms - min_dur) / (max_dur - min_dur)
                    pause_duration = min_pause + ratio * (max_pause - min_pause)
                    return int(round(pause_duration / 10) * 10)  # Округлення до 10 мс

        # GPT: Функція, що виконується в окремому потоці (для уникнення зависання GUI)
        def start_processing_thread():
            overall_start = time.time()  # GPT: початок для цього файлу (включно з експортом)
            saved_paths = []

            # GPT: Логіка об'єднання (Combine Mode)
            if combine_var.get() and len(wav_paths_var) > 1:
                # НОВЕ: сортуємо файли за іменем — гарантує, що батчі 1-1000, 1001-2000
                # і т.д. відповідають реальному порядку файлів, незалежно від порядку
                # вибору в діалозі.
                sorted_paths = sorted(wav_paths_var, key=natural_sort_key)
                total_files = len(sorted_paths)

                # НОВЕ: якщо батчі вимкнено — один батч на всі файли (стара поведінка,
                # один combined mp3 на виході).
                if batch_var.get() and batch_size_var.get() > 0:
                    batch_size = batch_size_var.get()
                else:
                    batch_size = total_files

                batches = [sorted_paths[i:i + batch_size] for i in range(0, total_files, batch_size)]
                pad_width = len(str(total_files))

                # Прогрес: один крок на кожен файл (читання) + один крок на кожен батч (експорт)
                total_steps = total_files + len(batches)
                root.after(0, lambda: progress.config(maximum=total_steps, value=0))

                def update_progress(step=1):
                    # Функція для безпечного оновлення прогрес-бару з іншого потоку
                    root.after(0, lambda: progress.step(step))

                file_options = {
                    'normalize': normalize_var.get(),
                    'high_pass': hp_var.get(),
                    'low_pass': lp_var.get(),
                    'hp_cutoff': hp_cutoff_var.get(),
                    'lp_cutoff': lp_cutoff_var.get(),
                    'chunk_ms': chunk_ms_var.get(),
                    'pause_ms': pause_ms_var.get(),
                }

                def get_pause_duration(prev_duration):
                    pause_duration = pause_ms_var.get()
                    if dynamic_pauses_var.get():
                        pause_duration = calculate_dynamic_pause(prev_duration)
                    return max(30, pause_duration)

                def get_gap(pause_duration, seg_rate, seg_channels):
                    if room_tone_var.get():
                        return generate_pink_noise(pause_duration, seg_rate, seg_channels, gain_db=room_tone_gain_var.get())
                    else:
                        return AudioSegment.silent(duration=pause_duration, frame_rate=seg_rate)

                # НОВЕ: якщо батчів декілька і виконуються паралельно, кожен свій
                # ThreadPoolExecutor(16) для читання файлів створював би забагато потоків
                # одночасно (4 батчі x 16 = 64). Ділимо бюджет потоків на кількість
                # паралельних батчів, щоб сумарно залишалось приблизно стільки ж потоків
                # читання, скільки було в однобатчевому режимі.
                reader_workers = max(2, 16 // min(MAX_CONCURRENT_BATCHES, len(batches)))

                # НОВЕ: підготовка одного батчу — читання файлів (паралельно потоками) +
                # об'єднання в один AudioSegment.
                def prepare_batch(batch_paths):
                    parts = read_and_process_files_parallel(
                        batch_paths, file_options, progress_callback=update_progress, max_workers=reader_workers
                    )
                    parts = [p for p in parts if len(p) > 0]
                    if not parts:
                        return None

                    seg_rate = parts[0].frame_rate
                    seg_channels = parts[0].channels

                    return combine_audio_segments_optimized(
                        parts,
                        get_pause_duration if dynamic_pauses_var.get() else None,
                        (lambda pd: get_gap(pd, seg_rate, seg_channels)) if room_tone_var.get() else None
                    )

                # НОВЕ: повна обробка одного батчу від початку до кінця (читання → об'єднання →
                # експорт ffmpeg). Кілька таких викликів виконуються одночасно в окремих
                # потоках — тому й одночасно з'являться кілька процесів ffmpeg.exe, а не по черзі.
                def process_one_batch(index, batch_paths):
                    try:
                        combined = prepare_batch(batch_paths)
                        if combined is None or len(combined) == 0:
                            print(f"⚠️ Батч {index + 1}: жоден файл не вдалося обробити, пропускаю")
                            update_progress()
                            return index, None

                        start_idx = index * batch_size + 1
                        end_idx = min((index + 1) * batch_size, total_files)
                        out_name = f"files_{start_idx:0{pad_width}d}-{end_idx:0{pad_width}d}.mp3"
                        out_path = os.path.join(output_dir_var.get(), out_name)

                        export_mp3_fast(combined, out_path)  # запускає ffmpeg; звільняє GIL на час його роботи
                        update_progress()  # крок за експорт цього батчу
                        print(f"✅ Збережено батч {index + 1}/{len(batches)}: {out_path}")
                        return index, out_path
                    except Exception as e:
                        print(f"❌ Помилка в батчі {index + 1}: {e}")
                        update_progress()
                        return index, None

                try:
                    # НОВЕ: справжній паралелізм — до MAX_CONCURRENT_BATCHES батчів
                    # обробляються одночасно (кожен зі своїм читанням і своїм ffmpeg).
                    concurrency = min(MAX_CONCURRENT_BATCHES, len(batches))
                    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as batch_executor:
                        futures = [
                            batch_executor.submit(process_one_batch, i, bp)
                            for i, bp in enumerate(batches)
                        ]
                        results = [f.result() for f in concurrent.futures.as_completed(futures)]

                    # Повертаємо порядок батчів (as_completed завершує їх не по черзі)
                    results.sort(key=lambda r: r[0])
                    saved_paths = [p for _, p in results if p]

                    overall_end = time.time()
                    total_elapsed = overall_end - overall_start
                    # GPT: одне зведене повідомлення з переліком збережених файлів і тривалістю
                    files_list = "\n".join(saved_paths) if saved_paths else "(нема збережених файлів)"

                    # Оновлення GUI після завершення
                    root.after(0, lambda: lbl_status.config(text=f"Готово. Тривалість: {_format_hms(total_elapsed)}"))
                    root.after(0, lambda: messagebox.showinfo('Готово', f'Збережено:\n{files_list}\n\nОбробка тривала  {_format_hms(total_elapsed)}'))

                except Exception as e:
                    root.after(0, lambda e=e: messagebox.showerror('Під час об\'єднання сталася помилка', str(e)))
                finally:
                    # Завжди відновлюємо кнопку після завершення/помилки
                    root.after(0, lambda: btn_start.config(state=tk.NORMAL))
                    root.after(0, lambda: progress.config(value=progress.cget('maximum'))) # Завершуємо прогрес

            # GPT: Стандартна обробка: кожен файл у свій MP3 (з GUI оновленням)
            else:
                overall_start = time.time()  # GPT: початок для всієї операції
                root.after(0, lambda: progress.config(maximum=len(wav_paths_var), value=0))
                saved_all = []
                try:
                    # ЯКІР: ЗАМІНИТИ послідовну обробку на паралельну
                    file_data_list = [(p, output_dir_var.get()) for p in wav_paths_var]
                    options = {
                        'normalize': normalize_var.get(),
                        'high_pass': hp_var.get(),
                        'low_pass': lp_var.get(),
                        'hp_cutoff': hp_cutoff_var.get(),
                        'lp_cutoff': lp_cutoff_var.get(),
                        'chunk_ms': chunk_ms_var.get(),
                        'pause_ms': pause_ms_var.get(),
                    }
                    
                    results = process_files_parallel(file_data_list, options)
                    for saved, elapsed in results:
                        saved_all.extend(saved)
                        root.after(0, lambda: progress.step(1))
                        
                    overall_end = time.time()
                    total_elapsed = overall_end - overall_start
                    files_list = "\n".join(saved_all) if saved_all else "(нема збережених файлів)"
                    # GPT: одне зведене повідомлення наприкінці
                    root.after(0, lambda: lbl_status.config(text=f"Готово. Тривалість: {_format_hms(total_elapsed)}"))
                    root.after(0, lambda: messagebox.showinfo('Готово', f'Збережено:\n{files_list}\n\nОбробка тривала  {_format_hms(total_elapsed)}'))
                    
                except Exception as e:
                    root.after(0, lambda e=e: messagebox.showerror('Помилка', str(e)))
                finally:
                    root.after(0, lambda: btn_start.config(state=tk.NORMAL))
                    root.after(0, lambda: progress.config(value=progress.cget('maximum'))) # Завершуємо прогрес

        # Запускаємо обробку в окремому потоці
        threading.Thread(target=start_processing_thread).start()

    btn_start = ttk.Button(frame_bottom, text='Почати обробку', command=start_processing)
    btn_start.grid(row=1, column=0, pady=6)

    root.columnconfigure(0, weight=1)
    root.mainloop()

if __name__ == '__main__':
    build_gui()