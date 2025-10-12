import os
import time
import re
import unicodedata
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, List, Sequence, Tuple

import gradio as gr
import numpy as np
import soundfile as sf

from app import synthesize, prompts_list
try:
    from transformers import AutoTokenizer
except Exception:
    AutoTokenizer = None

OUTPUT_DIR = "output_audio"
SPEAKER_MAX = 30
PROGRESS_POLL_INTERVAL = 1.0

class NoProgress:
    """Мінімальний об'єкт-заглушка для інтерфейсу progress."""

    def tqdm(self, iterable: Iterable):
        return iterable

def format_hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

# ---------- Нормалізація (НЕ чіпає '+') ----------
def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return s
    s = unicodedata.normalize("NFKC", s).replace("\ufeff", "")
    # уніфікація апострофів і тире
    s = (s.replace("’","'").replace("ʼ","'").replace("ʻ","'").replace("ʹ","'")
           .replace("—","-").replace("–","-").replace("−","-"))
    # прибрати невидимі керівні (Cf/Cc), зберегти \n \r \t і '+'
    out = []
    for ch in s:
        if ch == '+':
            out.append(ch); continue
        cat = unicodedata.category(ch)
        if cat in ("Cf","Cc") and ch not in ("\n","\r","\t"):
            continue
        out.append(ch)
    s = "".join(out)
    # NBSP -> пробіл, підчистити пробіли навколо переносів
    s = s.replace("\u00A0", " ")
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s

# ---------- Токено-безпечний спліт для PL-BERT (ліміт 512) ----------
# Додаткові пороги безпеки
CHAR_CAP = 1200        # жорстка стеля по символах для одного шматка
HARD_MAX_TOKENS = 280  # цільовий бюджет токенів на шматок (із запасом)
PLBERT_MAX = 512
PLBERT_SAFE = 480       # ще один запас безпеки перед 512
_tok = None
if AutoTokenizer is not None:
    try:
        _tok = AutoTokenizer.from_pretrained("albert-base-v2")
    except Exception:
        _tok = None

def _tok_len(t: str) -> int:
    if _tok is None:
        # СУПЕР-консервативний fallback: 1 символ ~ 1 токен + невеликий запас.
        # Це не дасть недооцінити і "пропхнути" >512 у модель.
        return len(t) + 32
    return len(_tok.encode(t, add_special_tokens=True))

def _split_sentence_safe(sent: str, max_tokens: int) -> list[str]:
    """Ділить наддовге речення по словах, не чіпаючи '+'."""
    parts, buf = [], []
    for tok in re.findall(r"\S+\s*|\s+", sent):
        buf.append(tok)
        if _tok_len("".join(buf)) > max_tokens:
            if len(buf) == 1:
                chunk = tok
                while _tok_len(chunk) > max_tokens:
                    cut = max(64, int(len(chunk) * 0.7))
                    parts.append(chunk[:cut])
                    chunk = chunk[cut:]
                buf = [chunk]
            else:
                last = buf.pop()
                parts.append("".join(buf).strip())
                buf = [last]
    if buf:
        parts.append("".join(buf).strip())
    out = [p for p in parts if p]
    # додаткова страховка: ріжемо дуже довгі шматки по комах/крапках із відступом
    safe = []
    for chunk in out:
        if len(chunk) <= CHAR_CAP and _tok_len(chunk) <= max_tokens:
            safe.append(chunk); continue
        frag = chunk
        # пробуємо різати по комах/крапках
        while len(frag) > 0 and (_tok_len(frag) > max_tokens or len(frag) > CHAR_CAP):
            m = re.search(r'(.{200,}?[,;:])\s+', frag, flags=re.DOTALL)
            cut = m.end() if m else min(len(frag), max(300, len(frag)//2))
            safe.append(frag[:cut].strip())
            frag = frag[cut:].lstrip()
        if frag:
            safe.append(frag)
    return safe

def split_to_parts(text: str, max_tokens: int = HARD_MAX_TOKENS) -> list[str]:
    """
    Розбиває так, щоб кожен шматок був ≤~280 токенів і ≤1200 символів.
    Поважає абзаци й речення. '+' зберігається.
    """
    text = normalize_text(text)
    chunks = []
    for para in re.split(r"\n{2,}", text.strip()):
        para = para.strip()
        if not para:
            continue
        # розбивка на речення; якщо немає крапок — отримаємо 1 довге речення
        sents = re.split(r"(?<=[\.\!\?…])\s+", para)
        buf = []
        for s in sents:
            cand = (" ".join(buf + [s])).strip() if buf else s.strip()
            if not cand:
                continue
            if _tok_len(cand) <= max_tokens and len(cand) <= CHAR_CAP:
                buf.append(s)
                continue
            # якщо саме речення довше бюджету — дробимо
            if _tok_len(s) > max_tokens or len(s) > CHAR_CAP:
                if buf:
                    chunks.append(" ".join(buf).strip()); buf = []
                chunks.extend(_split_sentence_safe(s, max_tokens))
            else:
                if buf:
                    chunks.append(" ".join(buf).strip())
                buf = [s]
        if buf:
            chunks.append(" ".join(buf).strip())
    # фінальна перевірка кожного шматка
    safe_final = []
    for c in chunks:
        if _tok_len(c) <= max_tokens and len(c) <= CHAR_CAP:
            safe_final.append(c)
        else:
            safe_final.extend(_split_sentence_safe(c, max_tokens))
    return [c for c in safe_final if c]

def parse_dialog_tags(text):
    text = normalize_text(text)
    lines = text.splitlines()
    current_tag = None
    parsed = []
    tag_re = re.compile(r'^#g([1-9]|[12][0-9]|30)\s*:\s*(.*)$', re.I)

    for ln in lines:
        ln = ln.rstrip()
        if not ln:
            continue
        m = tag_re.match(ln)
        if m:
            current_tag = int(m.group(1))
            tail = m.group(2).strip()
            if tail:
                for p in split_to_parts(tail):
                    parsed.append((current_tag, p))
            continue
        sp_idx = current_tag if current_tag is not None else 1
        for p in split_to_parts(ln):
            parsed.append((sp_idx, p))
    return parsed


def _safe_float(value, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_text_source(text_input: str | None, file_path: str | None) -> str:
    if text_input and text_input.strip():
        return text_input
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    raise RuntimeError("Немає тексту для озвучення")


def _should_use_single_voice(voice: str | None) -> bool:
    if not voice:
        return False
    vname_l = voice.lower()
    return ("філат" in vname_l) or ("filat" in vname_l)


def _needs_plbert_fallback(error_text: str) -> bool:
    return (
        "must match the existing size (512)" in error_text
        or "expanded size of the tensor" in error_text
    )


def _synthesize_chunk(chunk: str, voice: str | None, speed: float) -> Tuple[int, np.ndarray]:
    """Синтезує один шматок тексту з урахуванням усіх запасних стратегій."""

    use_single = _should_use_single_voice(voice)

    def run_for_parts(parts: Sequence[str]) -> Tuple[int, np.ndarray]:
        waves: List[np.ndarray] = []
        sr_local: int | None = None
        mode = "single" if use_single else "multi"
        voice_name = None if use_single else (voice or None)
        for part in parts:
            txt = normalize_text(part)
            sr_local, audio = synthesize(mode, txt, speed, voice_name=voice_name, progress=NoProgress())
            waves.append(audio)
        if sr_local is None:
            raise RuntimeError("Synthesis did not return sample rate")
        audio_np = waves[0] if len(waves) == 1 else np.concatenate(waves, axis=0)
        return sr_local, audio_np

    parts: List[str] = [chunk]
    if _tok_len(chunk) > PLBERT_SAFE or len(chunk) > CHAR_CAP:
        parts = split_to_parts(chunk, max_tokens=min(HARD_MAX_TOKENS, PLBERT_SAFE // 2))

    try:
        return run_for_parts(parts)
    except Exception:
        first_err = traceback.format_exc()
        if _needs_plbert_fallback(first_err):
            try:
                fallback_parts = split_to_parts(chunk, max_tokens=PLBERT_SAFE // 3)
                return run_for_parts(fallback_parts)
            except Exception:
                raise RuntimeError(f"Synthesis error:\n{traceback.format_exc()}") from None
        raise RuntimeError(f"Synthesis error:\n{first_err}") from None


def batch_synthesize_dialog(text_input, file_path, speeds_flat, voices_flat, save_option):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global_start = time.time()

    text = _read_text_source(text_input, file_path)

    parsed = parse_dialog_tags(text)
    total_parts = max(1, len(parsed))
    times_per_part = []

    voice_map = {i + 1: (voices_flat[i] if i < len(voices_flat) else None) for i in range(SPEAKER_MAX)}
    speed_map = {i + 1: (_safe_float(speeds_flat[i]) if i < len(speeds_flat) else 1.0) for i in range(SPEAKER_MAX)}

    start_time_str = time.strftime('%H:%M:%S', time.localtime(global_start))

    yield (None, gr.update(value=1, maximum=total_parts, interactive=False), "0 сек", start_time_str, "", "Розрахунок...", "", gr.update(value=0, maximum=total_parts, interactive=False))

    for idx, (tag_num, chunk) in enumerate(parsed, start=1):
        part_start = time.time()
        voice = voice_map.get(tag_num, None)
        spd = speed_map.get(tag_num, 1.0)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_synthesize_chunk, chunk, voice, spd)

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
                    rem_text = f"до закінчення залишилося {rem_min} хв {rem_sec} сек"

                yield (None, gr.update(value=idx, maximum=total_parts, interactive=False), elapsed_str, start_time_str, None, est_finish_str, rem_text, gr.update(value=max(idx-1, 0), maximum=total_parts, interactive=False))
                time.sleep(PROGRESS_POLL_INTERVAL)

            sr, audio_np = future.result()
        audio_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.wav")
        sf.write(audio_filename, audio_np, sr)

        if save_option == 'Зберегти всі частини озвученого тексту':
            txt_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as txt_file:
                txt_file.write(chunk)

        part_end = time.time()
        times_per_part.append(part_end - part_start)

        end_time_str = time.strftime('%H:%M:%S', time.localtime(part_end))
        elapsed_seconds = int(part_end - global_start)
        elapsed_total = f"{elapsed_seconds} сек --- {format_hms(elapsed_seconds)}"

        yield (audio_filename, gr.update(value=idx, maximum=total_parts, interactive=False), elapsed_total, start_time_str, end_time_str, None, "", gr.update(value=idx, maximum=total_parts, interactive=False))

    total_elapsed_secs = int(time.time() - global_start)
    total_formatted = format_hms(total_elapsed_secs)
    print(f"\033[92mЗатрачено часу: {total_formatted}\033[0m")
    yield (
        None,
        gr.update(value=total_parts, maximum=total_parts, interactive=True),
        f"Завершено за {total_elapsed_secs} сек",
        start_time_str,
        time.strftime('%H:%M:%S', time.localtime(time.time())),
        None,
        "",
        gr.update(value=total_parts, maximum=total_parts, interactive=False)
    )# UI
save_choices = ['Зберегти всі частини озвученого тексту', 'Без збереження']

with gr.Blocks(title="Batch TTS з Прогресом") as demo:
    with gr.Tabs():
        with gr.TabItem('Multi Dialog'):
            text_input_d = gr.Textbox(label='📋 Введіть текст або залиште порожнім і оберіть файл', lines=10, placeholder='Вставте текст тут...')
            file_input_d = gr.File(label='Або оберіть текстовий файл', type='filepath')
            speaker_choices = prompts_list

            # ===== Компоненти голосів і швидкостей (у порядку #g1..#g30) =====
            voice_components: list[gr.Dropdown] = []
            speed_components: list[gr.Slider] = []
            DEFAULT_VISIBLE = 3  # дефолт для автопідсвітлення після введення

            gr.Markdown("**Налаштування голосів**")

            # --- Допоміжний конструктор клітинки для одного спікера ---
            def _speaker_cell(i: int):
                # ВАЖЛИВО: робимо елементи видимими за замовчуванням, щоб акордеони не виглядали порожніми.
                # Подальша логіка автоприховування керується on_text_changed/on_file_changed.
                dd = gr.Dropdown(
                    label=f'Голос для #g{i}',
                    choices=speaker_choices,
                    value=speaker_choices[0],
                    visible=True
                )
                sv = gr.Slider(0.7, 1.3, value=0.88, label=f'Швидкість для #g{i}', visible=True)
                voice_components.append(dd)
                speed_components.append(sv)

            # ===== ГРУПА 1: #g1–#g3 (акордеон відкритий) =====
            with gr.Accordion("Спікери #g1–#g3", open=True) as acc_1_3:
                with gr.Row():
                    for i in (1, 2, 3):
                        with gr.Column():
                            _speaker_cell(i)

            # ===== ГРУПА 2: #g4–#g12 (акордеон закритий) =====
            with gr.Accordion("Спікери #g4–#g12", open=False) as acc_4_12:
                # Ряд 1: #g4 #g5 #g6
                with gr.Row():
                    for i in (4, 5, 6):
                        with gr.Column():
                            _speaker_cell(i)
                # Ряд 2: #g7 #g8 #g9
                with gr.Row():
                    for i in (7, 8, 9):
                        with gr.Column():
                            _speaker_cell(i)
                # Ряд 3: #g10 #g11 #g12
                with gr.Row():
                    for i in (10, 11, 12):
                        with gr.Column():
                            _speaker_cell(i)

            # ===== ГРУПА 3: Додаткові голоси (акордеон закритий) =====
            with gr.Accordion("Додаткові голоси", open=False) as acc_more:
                # --- Підгрупа: #g13–#g21 ---
                with gr.Accordion("Спікери #g13–#g21", open=False) as acc_13_21:
                    with gr.Row():
                        for i in (13, 14, 15):
                            with gr.Column():
                                _speaker_cell(i)
                    with gr.Row():
                        for i in (16, 17, 18):
                            with gr.Column():
                                _speaker_cell(i)
                    with gr.Row():
                        for i in (19, 20, 21):
                            with gr.Column():
                                _speaker_cell(i)
                # --- Підгрупа: #g22–#g30 ---
                with gr.Accordion("Спікери #g22–#g30", open=False) as acc_22_30:
                    with gr.Row():
                        for i in (22, 23, 24):
                            with gr.Column():
                                _speaker_cell(i)
                    with gr.Row():
                        for i in (25, 26, 27):
                            with gr.Column():
                                _speaker_cell(i)
                    with gr.Row():
                        for i in (28, 29, 30):
                            with gr.Column():
                                _speaker_cell(i)

                # --- Опції збереження під спойлером усередині «Додаткові голоси» ---
                with gr.Accordion("Опції збереження", open=False) as acc_opts:
                    save_option_d = gr.Radio(choices=save_choices, label='Опції збереження', value=save_choices[1])
                    with gr.Row():
                        # 1) Зберегти як файл (Download)
                        save_settings_download_btn = gr.DownloadButton("💾 Зберегти налаштування мовців")
                        # 2) Зберегти у папку за замовчуванням
                        save_settings_default_btn = gr.Button("📁 Зберегти у папку за замовчуванням")
                        # 3) Завантажити з файлу
                        load_settings_btn = gr.UploadButton(
                            "📂 Завантажити налаштування (.txt)",
                            file_types=[".txt"],
                            file_count="single"
                        )

            # --- Автовизначення кількості спікерів із тексту + автокерування видимістю та відкриттям акордеонів ---
            _g_tag_re = re.compile(r'#g\s*([1-9]|[12]\d|30)\b', re.IGNORECASE)

            def _max_g_tag_from_text(s: str | None) -> int:
                if not s:
                    return DEFAULT_VISIBLE
                m = [int(x) for x in _g_tag_re.findall(s)]
                if not m:
                    return DEFAULT_VISIBLE
                return max(1, min(30, max(m)))

            def _visibility_updates(n: int):
                # 30 dropdown + 30 sliders
                updates = []
                for i in range(1, 31):
                    show = (i <= n)
                    updates.append(gr.update(visible=show))  # dropdown
                for i in range(1, 31):
                    show = (i <= n)
                    updates.append(gr.update(visible=show))  # slider
                # Відкривати лише ті акордеони, де є видимі елементи
                acc_updates = [
                    gr.update(open=(n >= 1)),   # acc_1_3
                    gr.update(open=(n >= 4)),   # acc_4_12
                    gr.update(open=(n >= 13)),  # acc_more
                    gr.update(open=(n >= 13)),  # acc_13_21
                    gr.update(open=(n >= 22)),  # acc_22_30
                    gr.update(open=False),      # acc_opts залишається закритим
                ]
                return updates + acc_updates

            def on_text_changed(txt):
                n = _max_g_tag_from_text(txt)
                return _visibility_updates(n)

            def on_file_changed(path_like):
                p = None
                if isinstance(path_like, str):
                    p = path_like
                elif isinstance(path_like, dict):
                    p = path_like.get("name") or path_like.get("path")
                if not p or not os.path.exists(p):
                    return _visibility_updates(DEFAULT_VISIBLE)
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        txt = f.read()
                except Exception:
                    txt = ""
                n = _max_g_tag_from_text(txt)
                return _visibility_updates(n)

            # Події: підлаштовуємо видимість та відкриття акордеонів під максимум #gN
            text_input_d.change(
                fn=on_text_changed,
                inputs=[text_input_d],
                outputs=(voice_components + speed_components + [acc_1_3, acc_4_12, acc_more, acc_13_21, acc_22_30, acc_opts])
            )
            file_input_d.change(
                fn=on_file_changed,
                inputs=[file_input_d],
                outputs=(voice_components + speed_components + [acc_1_3, acc_4_12, acc_more, acc_13_21, acc_22_30, acc_opts])
            )
            # Кнопка запуску
            btn_d = gr.Button('▶ Розпочати')
            with gr.Accordion('🔊 Поточна частина', open=False):
                autoplay_chk_d = gr.Checkbox(label='Автовідтворення при зміні частини', value=False)
                output_audio_d = gr.Audio(label='🔊 Поточна частина', type='filepath', autoplay=False)
                part_slider_d = gr.Slider(label='Частина тексту', minimum=1, maximum=1, step=1, value=1, interactive=False)
            with gr.Row():
                timer_text_d = gr.Textbox(label="⏱️ Відлік часу (сек)", value="0", interactive=False)
                start_time_text_d = gr.Textbox(label="Початок озвучення", interactive=False)
                end_time_text_d = gr.Textbox(label="Закінчення озвучення попередньої частини", interactive=False)
            with gr.Row():
                parts_progress_d = gr.Slider(label='Частин для озвучення', minimum=0, maximum=1, step=1, value=0, interactive=False)
            with gr.Row():
                est_end_time_text_d = gr.Textbox(label="Прогноз закінчення", interactive=False)
                remaining_time_text_d = gr.Textbox(label="Час до закінчення", interactive=False)

            # ПОВЕРНЕНІ КНОПКИ ЗБЕРЕЖЕННЯ/ЗАВАНТАЖЕННЯ (видимі зверху, поза спойлером)
            with gr.Row():
                save_settings_download_btn_top = gr.DownloadButton("💾 Зберегти налаштування мовців")
                save_settings_default_btn_top = gr.Button("📁 Зберегти у папку за замовчуванням")
                load_settings_btn_top = gr.UploadButton(
                    "📂 Завантажити налаштування (.txt)",
                    file_types=[".txt"],
                    file_count="single"
                )

            # Порядок inputs для кнопки старту: текст, файл, 30 швидкостей, 30 голосів, опція збереження
            btn_inputs = [text_input_d, file_input_d] + speed_components + voice_components + [save_option_d]

            btn_outputs = [
                output_audio_d,
                part_slider_d,
                timer_text_d,
                start_time_text_d,
                end_time_text_d,
                est_end_time_text_d,
                remaining_time_text_d,
                parts_progress_d,
            ]


            # --- 1) ЕКСПОРТ У ФАЙЛ ДЛЯ ЗАВАНТАЖЕННЯ (стабільно, без кешу та «старих» значень) ---
            def export_speaker_settings_for_download(*flat_values):
                """
                Генерує текст конфігурації з поточних значень UI і повертає
                шлях до НОВОГО файлу. Кожен клік → нове ім'я (без кешу).
                ВАЖЛИВО: порядок inputs має бути [voice_components ...] + [speed_components ...]
                """
                # 1) Поточні значення: спочатку 30 dropdown (voices), потім 30 слайдерів (speeds)
                voices = list(flat_values[:30])
                speeds = list(flat_values[30:60])

                # 2) Зібрати текст конфігурації
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

                # 3) Унікальне ім'я файлу у підтеці _exports (Windows-friendly)
                export_root = os.path.join(OUTPUT_DIR, "_exports")
                os.makedirs(export_root, exist_ok=True)
                fname = f"speakers_settings_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.txt"
                out_path = os.path.abspath(os.path.join(export_root, fname))

                # 4) Записати файл і повернути його шлях — DownloadButton одразу віддасть цей файл
                with open(out_path, "w", encoding="utf-8") as fh:
                    fh.write(text)
                return out_path

            save_settings_download_btn.click(
                fn=export_speaker_settings_for_download,
                inputs=voice_components + speed_components,
                outputs=save_settings_download_btn,
            )
            # дублюємо для верхньої кнопки
            save_settings_download_btn_top.click(
                fn=export_speaker_settings_for_download,
                inputs=voice_components + speed_components,
                outputs=save_settings_download_btn_top,
            )

            # --- 2) ЗБЕРЕЖЕННЯ У ПАПКУ ЗА ЗАМОВЧУВАННЯМ (OUTPUT_DIR) ---
            def save_speaker_settings_to_default(*flat_values):
                voices = list(flat_values[:30])
                speeds = list(flat_values[30:60])
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                cfg_path = os.path.join(OUTPUT_DIR, "speakers_settings.txt")
                with open(cfg_path, "w", encoding="utf-8") as f:
                    for i in range(1, 31):
                        voice_name = str(voices[i-1]).strip()
                        try:
                            speed_val = float(speeds[i-1])
                        except Exception:
                            speed_val = 1.0
                        speed_str = f"{speed_val:.2f}".replace(".", ",")
                        f.write(f"#g{i}:{voice_name} швидкість:{speed_str};\n")
                # Інформувати користувача
                gr.Info(f"✅ Налаштування збережено: {cfg_path}")

            save_settings_default_btn.click(
                fn=save_speaker_settings_to_default,
                inputs=voice_components + speed_components,
                outputs=[],
            )
            save_settings_default_btn_top.click(
                fn=save_speaker_settings_to_default,
                inputs=voice_components + speed_components,
                outputs=[],
            )

            # --- 3) ЗАВАНТАЖЕННЯ НАЛАШТУВАНЬ З ФАЙЛУ (.txt) ---
            def load_speaker_settings_uploaded(files, *current_values):
                """
                Імпортує значення у Dropdown/Slider згідно файлу у форматі:
                #gN:Назва голосу швидкість:0,88;
                Застосовує значення без перезавантаження сторінки.
                """
                if not files:
                    raise gr.Error("Не обрано файл налаштувань (.txt).")
                # UploadButton може повертати рядок-шлях, dict або список
                if isinstance(files, (list, tuple)):
                    src = files[0]
                else:
                    src = files  # одиночний шлях/об'єкт
                file_path = str(src if isinstance(src, str) else (src.get("name") or src.get("path") if isinstance(src, dict) else getattr(src, "name", ""))) or None
                if not file_path: raise gr.Error("Не вдалося визначити шлях до завантаженого файлу.")

                pat = re.compile(
                    r'^#g([1-9]|[12]\d|30)\s*:\s*(.*?)\s*швидкість\s*:\s*([0-9]+(?:[.,][0-9]+)?)\s*;\s*$',
                    re.IGNORECASE
                )
                # Поточні значення як дефолти
                voices_out = list(current_values[:30])
                speeds_out = list(current_values[30:60])

                for line in open(file_path, "r", encoding="utf-8").read().splitlines():
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
                    # кліп до меж повзунка
                    speed_val = max(0.7, min(1.3, speed_val))
                    if 0 <= idx < 30:
                        voices_out[idx] = voice_name
                        speeds_out[idx] = speed_val
                # Повертаємо у порядку outputs: спочатку всі dropdown, потім всі слайдери
                return voices_out + speeds_out

            # Обробник завантаження: оновлюємо лише значення dropdown/slider без перезавантаження сторінки
            load_settings_btn.upload(
                fn=load_speaker_settings_uploaded,
                inputs=[load_settings_btn] + voice_components + speed_components,
                outputs=voice_components + speed_components,
            )
            load_settings_btn_top.upload(
                fn=load_speaker_settings_uploaded,
                inputs=[load_settings_btn_top] + voice_components + speed_components,
                outputs=voice_components + speed_components,
            )

            def _btn_d_handler(text_input, file_input, *flat_values):
                speeds = list(flat_values[:30])
                voices = list(flat_values[30:60])
                save_option = flat_values[60]
                yield from batch_synthesize_dialog(text_input, file_input, speeds, voices, save_option)
            btn_d.click(
                fn=_btn_d_handler,
                inputs=btn_inputs,
                outputs=btn_outputs,
                show_progress=False
            )

            # === Інтерактивність слайдера «Частина тексту» після завершення ===
            def _on_part_slider_change(part_idx: int, autoplay: bool):
                try:
                    i = int(part_idx)
                except Exception:
                    gr.Warning("Некоректний номер частини")
                    return gr.update()
                wav_path = os.path.join(OUTPUT_DIR, f"part_{i:03}.wav")
                if not os.path.exists(wav_path):
                    gr.Error(f"Файл не знайдено: {wav_path}")
                    return gr.update()
                # Повертаємо оновлення аудіо. Якщо підтримується, встановимо autoplay
                return gr.update(value=wav_path, autoplay=bool(autoplay))

            part_slider_d.change(
                fn=_on_part_slider_change,
                inputs=[part_slider_d, autoplay_chk_d],
                outputs=[output_audio_d],
            )

if __name__ == '__main__':
    demo.queue().launch()