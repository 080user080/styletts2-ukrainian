import os
import time
import threading
import re
import unicodedata
import traceback
import tempfile
import uuid
import gradio as gr
import numpy as np
import soundfile as sf
from app import synthesize, prompts_list
try:
    from transformers import AutoTokenizer
except Exception:
    AutoTokenizer = None

OUTPUT_DIR = "output_audio"

class NoProgress:
    def tqdm(self, iterable):
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


def batch_synthesize_dialog(text_input, file_path, speeds_flat, voices_flat, save_option):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global_start = time.time()

    if (text_input or '').strip():
        text = text_input
    elif file_path:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        raise RuntimeError('Немає тексту для озвучення')

    parsed = parse_dialog_tags(text)
    total_parts = max(1, len(parsed))
    times_per_part = []

    voice_map = {i+1: (voices_flat[i] if i < len(voices_flat) else None) for i in range(30)}
    speed_map = {i+1: (float(speeds_flat[i]) if i < len(speeds_flat) else 1.0) for i in range(30)}

    start_time_str = time.strftime('%H:%M:%S', time.localtime(global_start))

    yield (None, gr.update(value=1, maximum=total_parts), "0 сек", start_time_str, "", "Розрахунок...", "")

    for idx, (tag_num, chunk) in enumerate(parsed, start=1):
        part_start = time.time()
        voice = voice_map.get(tag_num, None)
        spd = speed_map.get(tag_num, 1.0)
        # Робимо визначення Філатова нечутливим до регістру/варіантів написання
        vname_l = (voice or "").lower()
        # ВАЖЛИВО: усі варіації *filatov*/«філатов» мають іти через single-модель,
        # навіть якщо такий пункт є у списку голосів (prompts_list).
        # Інакше multi-параметри дають спотворений звук/тишу.
        use_single = ('філат' in vname_l) or ('filat' in vname_l)
        result = {}

        def run_synth():
            try:
                # ДОДАТКОВИЙ ЗАХИСТ: якщо оцінка > PLBERT_SAFE або дуже довгий текст — дробимо ще раз.
                parts = [chunk]
                if _tok_len(chunk) > PLBERT_SAFE or len(chunk) > CHAR_CAP:
                    parts = split_to_parts(chunk, max_tokens=min(HARD_MAX_TOKENS, PLBERT_SAFE // 2))

                waves = []
                sr_local = None
                for part in parts:
                    txt = normalize_text(part)  # зберігає '+'
                    if use_single:
                        # single = Філатов, voice_name не потрібен
                        sr_local, a = synthesize('single', txt, spd, voice_name=None, progress=NoProgress())
                    else:
                        sr_local, a = synthesize('multi', txt, spd, voice_name=(voice or None), progress=NoProgress())
                    waves.append(a)

                # об’єднати, якщо було дрібнення
                audio_np_local = waves[0] if len(waves) == 1 else np.concatenate(waves, axis=0)
                result['sr'] = sr_local
                result['audio'] = audio_np_local
            except Exception:
                # Якщо все ж впали на 512 — дрібнимо агресивно і пробуємо ще раз.
                err = traceback.format_exc()
                if 'must match the existing size (512)' in err or 'expanded size of the tensor' in err:
                    try:
                        parts = split_to_parts(chunk, max_tokens=PLBERT_SAFE // 3)
                        waves = []
                        sr_local = None
                        for part in parts:
                            txt = normalize_text(part)
                            mode = 'single' if use_single else 'multi'
                            sr_local, a = synthesize(
                                mode, txt, spd,
                                voice_name=(None if use_single else (voice or None)),
                                progress=NoProgress()
                            )
                            waves.append(a)
                        result['sr'] = sr_local
                        result['audio'] = np.concatenate(waves, axis=0)
                    except Exception:
                        result['error'] = traceback.format_exc()
        th = threading.Thread(target=run_synth)
        th.start()

        while th.is_alive():
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
                rem_min, rem_sec = divmod(max(rem_secs,0), 60)
                rem_text = f"до закінчення залишилося {rem_min} хв {rem_sec} сек"

            yield (None, gr.update(value=idx, maximum=total_parts), elapsed_str, start_time_str, None, est_finish_str, rem_text)
            time.sleep(1)

        th.join()
        if 'error' in result:
            raise RuntimeError(f"Synthesis error:\n{result['error']}")

        sr = result['sr']
        audio_np = result['audio']
        audio_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.wav")
        sf.write(audio_filename, audio_np, sr)

        if save_option == 'Зберегти всі частини озвученого тексту':
            txt_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as txt_file:
                txt_file.write(chunk)

        part_end = time.time()
        times_per_part.append(part_end - part_start)

        end_time_str = time.strftime('%H:%M:%S', time.localtime(part_end))
        elapsed_total = f"{int(part_end - global_start)} сек"

        yield (audio_filename, gr.update(value=idx, maximum=total_parts), elapsed_total, start_time_str, end_time_str, None, "")

    total_elapsed_secs = int(time.time() - global_start)
    total_formatted = format_hms(total_elapsed_secs)
    print(f"\033[92mЗатрачено часу: {total_formatted}\033[0m")
    yield (None, gr.update(value=total_parts, maximum=total_parts), f"Завершено за {total_elapsed_secs} сек", start_time_str, time.strftime('%H:%M:%S', time.localtime(time.time())), None, "")


# UI
save_choices = ['Зберегти всі частини озвученого тексту', 'Без збереження']

with gr.Blocks(title="Batch TTS з Прогресом") as demo:
    with gr.Tabs():
        with gr.TabItem('Multi Dialog'):
            text_input_d = gr.Textbox(label='📋 Введіть текст або залиште порожнім і оберіть файл', lines=10, placeholder='Вставте текст тут...')
            file_input_d = gr.File(label='Або оберіть текстовий файл', type='filepath')

            speaker_choices = prompts_list

            voice_components = []
            speed_components = []

            gr.Markdown("**Налаштування голосів для тегів #g1..#g30**")

            for i in range(3):
                with gr.Row():
                    dd = gr.Dropdown(label=f'Голос для #g{i+1}', choices=speaker_choices, value=speaker_choices[0])
                    sv = gr.Slider(0.7, 1.3, value=0.88, label=f'Швидкість для #g{i+1}')
                voice_components.append(dd)
                speed_components.append(sv)

            with gr.Accordion("Розгорнути інші голоси (#g4..#g30)", open=False):
                for i in range(3, 30):
                    with gr.Row():
                        dd = gr.Dropdown(label=f'Голос для #g{i+1}', choices=speaker_choices, value=speaker_choices[0])
                        sv = gr.Slider(0.7, 1.3, value=0.88, label=f'Швидкість для #g{i+1}')
                    voice_components.append(dd)
                    speed_components.append(sv)

            save_option_d = gr.Radio(choices=save_choices, label='Опції збереження', value=save_choices[1])
            btn_d = gr.Button('▶ Розпочати')
            output_audio_d = gr.Audio(label='🔊 Поточна частина', type='filepath')
            part_slider_d = gr.Slider(label='Частина тексту', minimum=1, maximum=1, step=1, value=1, interactive=False)
            with gr.Row():
                timer_text_d = gr.Textbox(label="⏱️ Відлік часу (сек)", value="0", interactive=False)
                start_time_text_d = gr.Textbox(label="Початок озвучення", interactive=False)
                end_time_text_d = gr.Textbox(label="Закінчення озвучення попередньої частини", interactive=False)
            with gr.Row():
                est_end_time_text_d = gr.Textbox(label="Прогноз закінчення", interactive=False)
                remaining_time_text_d = gr.Textbox(label="Час до закінчення", interactive=False)

            # --- ТРИ КНОПКИ ДЛЯ КОНФІГУРАЦІЇ МОВЦІВ ---
            with gr.Row():
                # 1) Кнопка: сформувати файл і викликати "Save as" у браузері
                save_settings_download_btn = gr.DownloadButton("💾 Зберегти налаштування мовців")
                # 2) Зберегти у папку за замовчуванням (OUTPUT_DIR)
                save_settings_default_btn = gr.Button("📁 Зберегти у папку за замовчуванням")
                # 3) Завантажити налаштування з файлу (.txt)
                load_settings_btn = gr.UploadButton(
                    "📂 Завантажити налаштування (.txt)",
                    file_types=[".txt"],
                    file_count="single"
                )

            btn_inputs = [text_input_d, file_input_d]
            for s in speed_components:
                btn_inputs.append(s)
            for v in voice_components:
                btn_inputs.append(v)
            btn_inputs.append(save_option_d)

            btn_outputs = [
                output_audio_d,
                part_slider_d,
                timer_text_d,
                start_time_text_d,
                end_time_text_d,
                est_end_time_text_d,
                remaining_time_text_d,
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

if __name__ == '__main__':
    demo.queue().launch()