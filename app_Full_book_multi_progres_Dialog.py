import os
import time
import threading
import re
import unicodedata
import traceback
import gradio as gr
import soundfile as sf
from app_multi_novuj_vocoder import synthesize as synthesize_sync, prompts_list
try:
    from transformers import AutoTokenizer
except Exception:
    AutoTokenizer = None

OUTPUT_DIR = "output_audio"

# Dummy progress to bypass gr.Progress inside vocoder
class NoProgress:
    def tqdm(self, iterable):
        return iterable

# Безпечна нормалізація. «+» (наголос) НЕ чіпаємо.
def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return s
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\ufeff", "")  # BOM
    # апострофи
    s = s.replace("’", "'").replace("ʼ", "'").replace("ʻ", "'").replace("ʹ", "'")
    # тире
    s = s.replace("—", "-").replace("–", "-").replace("−", "-")
    # невидимі керівні
    s = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069]", "", s)
    # нестандартні пробіли
    s = re.sub(r"[ \t\f\v\u00a0]+", " ", s)
    # пробіли перед розділовими
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"([(\[]) +", r"\1", s)
    s = re.sub(r" +([)\]])", r"\1", s)
    return s

# ---------- Токено-орієнтований спліт під ліміт PL-BERT 512 ----------
if AutoTokenizer is not None:
    try:
        _tok = AutoTokenizer.from_pretrained("albert-base-v2")
    except Exception:
        _tok = None
else:
    _tok = None

def _tok_len(t: str) -> int:
    if _tok is None:
        # запасний оцінювач: приблизно слова*1.3 + знаки
        words = len(re.findall(r"\w+|\+", t, flags=re.UNICODE))
        punct = len(re.findall(r"[^\w\s]", t, flags=re.UNICODE))
        return int(words * 1.3 + punct) + 2  # запас на спецтокени
    return len(_tok.encode(t, add_special_tokens=True))

def _split_sentence_safe(sent: str, max_tokens: int) -> list[str]:
    """Ділить наддовге речення по словах, не чіпаючи '+'."""
    parts, buf = [], []
    for tok in re.findall(r"\S+\s*|\s+", sent):
        buf.append(tok)
        if _tok_len("".join(buf)) > max_tokens:
            if len(buf) == 1:
                # якщо один токен теж завеликий — ріжемо по символах
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
    return [p for p in parts if p]

def split_to_parts(text: str, max_tokens: int = 480) -> list[str]:
    """
    Розбиває текст так, щоб кожен шматок був ≤ ~max_tokens для PL-BERT (ліміт 512 з запасом).
    Поважає абзаци та речення. '+' зберігається.
    """
    text = normalize_text(text)
    chunks: list[str] = []
    # 1) абзаци
    for para in re.split(r"\n{2,}", text.strip()):
        para = para.strip()
        if not para:
            continue
        # 2) речення
        sents = re.split(r"(?<=[\.\!\?…])\s+", para)
        buf = []
        for s in sents:
            cand = (" ".join(buf + [s])).strip() if buf else s.strip()
            if not cand:
                continue
            if _tok_len(cand) <= max_tokens:
                buf.append(s)
                continue
            # якщо саме речення довше бюджету — дробимо безпечно
            if _tok_len(s) > max_tokens:
                if buf:
                    chunks.append(" ".join(buf).strip())
                    buf = []
                chunks.extend(_split_sentence_safe(s, max_tokens))
            else:
                if buf:
                    chunks.append(" ".join(buf).strip())
                buf = [s]
        if buf:
            chunks.append(" ".join(buf).strip())
    return [c for c in chunks if c]

# форматування часу в години:хвилини:секунди
def format_hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

# GPT: парсинг діалогу у список (speaker_index, text)
# Правила:
# - за замовчуванням перший рядок — Спікер1, другий — Спікер2, далі по черзі
# - якщо перший ненульовий рядок — директива "Спікер2" або "Speaker2" (із можливими ':' або '-' після),
#   то порядок початку міняється (починаємо зі Спікер2)
# - порожні рядки імовірно ігноруються
# - якщо рядок дуже довгий, він додатково розбивається через split_to_parts
def parse_dialog(text):  # GPT
    text = normalize_text(text)  # НЕ прибирає «+»
    lines = [ln for ln in re.split(r'\r?\n', text) if ln.strip()]
    parsed = []

    # Перевіряємо директиву на початку (Спікер2 або Speaker2 чи Спікер1)
    start_index = 0
    if lines:
        m = re.match(r'^\s*(?:Спікер\s*2|Speaker\s*2)\s*[:\-–—]?\s*$', lines[0], re.I)
        if m:
            start_index = 1
            lines = lines[1:]
        else:
            m2 = re.match(r'^\s*(?:Спікер\s*1|Speaker\s*1)\s*[:\-–—]?\s*$', lines[0], re.I)
            if m2:
                start_index = 0
                lines = lines[1:]

    # Логіка парсингу:
    # - Якщо рядок починається з тире/дефісу (—, -, – тощо) — вважаємо його діалогом і
    #   чергуємо спікерів (з урахуванням start_index).
    # - Якщо рядок не починається з тире — це наратив/опис і він завжди читається Спікером1 (index 0).
    # - Видаляємо провідні тире/пробіли у діалогових рядках перед передачею в split_to_parts.

    dialog_line_index = 0  # лічильник діалогових рядків (враховує лише ті, що з тире)
    for ln in lines:
        raw = ln.strip()
        if not raw:
            continue

        # Чи є на початку рядка позначка діалогу (тире або дефіс)
        if re.match(r'^[\-–—\u2012\u2013\u2014\s]*[\-–—\u2012\u2013\u2014]\s*', raw):
            # це діалог — чергуємо між спікерами
            speaker_idx = (start_index + dialog_line_index) % 2
            dialog_line_index += 1
            # Видаляємо провідні тире/пробіли
            content = re.sub(r'^[\-–—\u2012\u2013\u2014\s]+', '', raw)
        else:
            # наратив/опис — завжди Спікер1
            speaker_idx = 0
            content = raw

        # Розбиваємо довгі рядки на частини
        parts = split_to_parts(content)  # токен-безпечний спліт
        for p in parts:
            parsed.append((speaker_idx, p))

    return parsed

# Функція для batch-озвучення з прогресом і виведенням номера частини (існуюча)

def batch_synthesize(file_path, speed, model_name, speaker, save_option):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global_start = time.time()
    first_part_start = None
    last_part_end = None

    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    parts = split_to_parts(text)  # токен-безпечний спліт
    total_parts = len(parts)
    times_per_part = []

    for idx, chunk in enumerate(parts, start=1):
        part_start = time.time()
        if first_part_start is None:
            first_part_start = part_start

        # підготовка для відображення
        start_str = time.strftime('%H:%M:%S', time.localtime(first_part_start))
        prev_end_str = time.strftime('%H:%M:%S', time.localtime(last_part_end)) if last_part_end else '---'

        result = {}
        def run_synth():
            try:
                chunk_norm = normalize_text(chunk)  # «+» зберігаємо
                sr, audio_np = synthesize_sync(
                    model_name, chunk_norm, speed,
                    voice_name=(speaker or None),
                    progress=NoProgress()
                )
                result['sr'] = sr
                result['audio'] = audio_np
            except Exception:
                result['error'] = traceback.format_exc()

        synth_thread = threading.Thread(target=run_synth)
        synth_thread.start()

        # оновлення таймера і прогнозу під час синтезу
        while synth_thread.is_alive():
            now = time.time()
            elapsed = int(now - global_start)
            elapsed_str = f"{elapsed} сек --- {format_hms(elapsed)}"  # <-- зміна тут
            if times_per_part:
                avg_time = sum(times_per_part) / len(times_per_part)
                est_total_time = avg_time * total_parts
                est_finish_ts = global_start + est_total_time
                est_finish_str = time.strftime('%H:%M:%S', time.localtime(est_finish_ts))
                rem_secs = int(est_finish_ts - now)
                rem_min, rem_sec = divmod(rem_secs, 60)
                rem_text = f"до закінчення залишилося {rem_min} хв {rem_sec} сек"
            else:
                est_finish_str = 'Розрахунок...'
                rem_text = 'Розрахунок...'

            yield (
                None,
                gr.update(value=idx, maximum=total_parts),
                elapsed_str,  # <-- заміна
                #f"{elapsed} сек", # старе значення
                start_str,
                prev_end_str,
                est_finish_str,
                rem_text
            )
            time.sleep(1)

        synth_thread.join()
        if 'error' in result:
            raise RuntimeError(f"Synthesis error:\n{result['error']}")

        # збереження результату
        sr = result['sr']
        audio_np = result['audio']
        audio_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.wav")
        sf.write(audio_filename, audio_np, sr)
        if save_option == 'Зберегти всі частини озвученого тексту':
            txt_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as txt_file:
                txt_file.write(chunk)

        # фінальні дані після завершення частини
        part_end = time.time()
        last_part_end = part_end
        end_prev_str = time.strftime('%H:%M:%S', time.localtime(part_end))
        times_per_part.append(part_end - part_start)

        now = part_end
        elapsed = int(now - global_start)
        avg_time = sum(times_per_part) / len(times_per_part)
        est_total_time = avg_time * total_parts
        est_finish_ts = global_start + est_total_time
        est_finish_str = time.strftime('%H:%M:%S', time.localtime(est_finish_ts))
        rem_secs = int(est_finish_ts - now)
        rem_min, rem_sec = divmod(rem_secs, 60)
        rem_text = f"до закінчення залишилося {rem_min} хв {rem_sec} сек"

        yield (
            audio_filename,
            gr.update(value=idx, maximum=total_parts),
            f"{elapsed} сек",
            start_str,
            end_prev_str,
            est_finish_str,
            rem_text
        )

    # завершення всіх частин
    global_end = time.time()
    mins, secs = divmod(global_end - global_start, 60)
    print(f"✅ ЗАВЕРШЕНО об {time.strftime('%H:%M:%S', time.localtime(global_end))}")
    print(f"⏱️ Загальний час виконання: {int(mins)} хв {int(secs)} сек")


# GPT: Функція для Multi Dialog
def batch_synthesize_dialog(text_input, file_path, speed1, speed2, model_name, speaker1, speaker2, save_option):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global_start = time.time()
    first_part_start = None
    last_part_end = None

    # Отримуємо текст з поля або файлу
    if (text_input or '').strip():
        text = text_input
    elif file_path:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        raise RuntimeError('Немає тексту для озвучення')

    parsed = parse_dialog(text)  # список (speaker_idx, text_chunk)
    total_parts = len(parsed)
    times_per_part = []

    for idx, (sp_idx, chunk) in enumerate(parsed, start=1):
        part_start = time.time()
        if first_part_start is None:
            first_part_start = part_start

        # Визначаємо голос і швидкість для поточної частини
        voice = speaker1 if sp_idx == 0 else speaker2
        spd = speed1 if sp_idx == 0 else speed2

        # підготовка для відображення
        start_str = time.strftime('%H:%M:%S', time.localtime(first_part_start))
        prev_end_str = time.strftime('%H:%M:%S', time.localtime(last_part_end)) if last_part_end else '---'

        result = {}
        def run_synth():
            try:
                chunk_norm = normalize_text(chunk)  # «+» зберігаємо
                sr, audio_np = synthesize_sync(
                    model_name, chunk_norm, spd,
                    voice_name=(voice or None),
                    progress=NoProgress()
                )
                result['sr'] = sr
                result['audio'] = audio_np
            except Exception:
                result['error'] = traceback.format_exc()

        synth_thread = threading.Thread(target=run_synth)
        synth_thread.start()

        # оновлення таймера і прогнозу під час синтезу
        while synth_thread.is_alive():
            now = time.time()
            elapsed = int(now - global_start)
            elapsed_str = f"{elapsed} сек --- {format_hms(elapsed)}"
            if times_per_part:
                avg_time = sum(times_per_part) / len(times_per_part)
                est_total_time = avg_time * total_parts
                est_finish_ts = global_start + est_total_time
                est_finish_str = time.strftime('%H:%M:%S', time.localtime(est_finish_ts))
                rem_secs = int(est_finish_ts - now)
                rem_min, rem_sec = divmod(rem_secs, 60)
                rem_text = f"до закінчення залишилося {rem_min} хв {rem_sec} сек"
            else:
                est_finish_str = 'Розрахунок...'
                rem_text = 'Розрахунок...'

            yield (
                None,
                gr.update(value=idx, maximum=total_parts),
                elapsed_str,
                start_str,
                prev_end_str,
                est_finish_str,
                rem_text
            )
            time.sleep(1)

        synth_thread.join()
        if 'error' in result:
            raise RuntimeError(f"Synthesis error:\n{result['error']}")

        # збереження результату
        sr = result['sr']
        audio_np = result['audio']
        audio_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.wav")
        sf.write(audio_filename, audio_np, sr)
        if save_option == 'Зберегти всі частини озвученого тексту':
            txt_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as txt_file:
                txt_file.write(chunk)

        # фінальні дані після завершення частини
        part_end = time.time()
        last_part_end = part_end
        end_prev_str = time.strftime('%H:%M:%S', time.localtime(part_end))
        times_per_part.append(part_end - part_start)

        now = part_end
        elapsed = int(now - global_start)
        avg_time = sum(times_per_part) / len(times_per_part)
        est_total_time = avg_time * total_parts
        est_finish_ts = global_start + est_total_time
        est_finish_str = time.strftime('%H:%M:%S', time.localtime(est_finish_ts))
        rem_secs = int(est_finish_ts - now)
        rem_min, rem_sec = divmod(rem_secs, 60)
        rem_text = f"до закінчення залишилося {rem_min} хв {rem_sec} сек"

        yield (
            audio_filename,
            gr.update(value=idx, maximum=total_parts),
            f"{elapsed} сек",
            start_str,
            end_prev_str,
            est_finish_str,
            rem_text
        )

    # завершення всіх частин
    global_end = time.time()
    mins, secs = divmod(global_end - global_start, 60)
    print(f"✅ ЗАВЕРШЕНО об {time.strftime('%H:%M:%S', time.localtime(global_end))}")
    print(f"⏱️ Загальний час виконання: {int(mins)} хв {int(secs)} сек")

# Gradio UI
save_choices = ['Зберегти всі частини озвученого тексту', 'Без збереження']

with gr.Blocks(title="Batch TTS з Прогресом") as demo:
    with gr.Tabs():
        with gr.TabItem('Single speaker'):
            file_input = gr.File(label='📄 Оберіть текстовий файл', type='filepath')
            speed = gr.Slider(0.7, 1.3, value=0.88, label='🚀 Швидкість')
            model_name = gr.Text(value='single', visible=False)
            speaker_dummy = gr.Text(value='', visible=False)
            save_option = gr.Radio(choices=save_choices, label='Опції збереження', value=save_choices[1])
            btn = gr.Button('▶ Розпочати озвучення')
            output_audio = gr.Audio(label='🔊 Поточна частина', type='filepath')
            part_slider = gr.Slider(label='Частина тексту', minimum=1, maximum=1, step=1, value=1, interactive=False)
            with gr.Row():
                timer_text = gr.Textbox(label="⏱️ Відлік часу (сек)", value="0", interactive=False)
                start_time_text = gr.Textbox(label="Початок озвучення", interactive=False)
                end_time_text = gr.Textbox(label="Закінчення озвучення попередньої частини", interactive=False)
            with gr.Row():
                est_end_time_text = gr.Textbox(label="Прогноз закінчення", interactive=False)
                remaining_time_text = gr.Textbox(label="Час до закінчення", interactive=False)
            btn.click(
                fn=batch_synthesize,
                inputs=[file_input, speed, model_name, speaker_dummy, save_option],
                outputs=[output_audio, part_slider, timer_text, start_time_text, end_time_text, est_end_time_text, remaining_time_text],
                show_progress=False
            )
        with gr.TabItem('Multi speaker'):
            file_input_m = gr.File(label='📄 Оберіть текстовий файл', type='filepath')
            speed_m = gr.Slider(0.7, 1.3, value=0.88, label='🚀 Швидкість')
            speaker = gr.Dropdown(label="Голос:", choices=prompts_list, value=prompts_list[0])
            model_name_m = gr.Text(value='multi', visible=False)
            save_option_m = gr.Radio(choices=save_choices, label='Опції збереження', value=save_choices[1])
            btn_m = gr.Button('▶ Розпочати озвучення')
            output_audio_m = gr.Audio(label='🔊 Поточна частина', type='filepath')
            part_slider_m = gr.Slider(label='Частина тексту', minimum=1, maximum=1, step=1, value=1, interactive=False)
            with gr.Row():
                timer_text_m = gr.Textbox(label="⏱️ Відлік часу (сек)", value="0", interactive=False)
                start_time_text_m = gr.Textbox(label="Початок озвучення", interactive=False)
                end_time_text_m = gr.Textbox(label="Закінчення озвучення попередньої частини", interactive=False)
            with gr.Row():
                est_end_time_text_m = gr.Textbox(label="Прогноз закінчення", interactive=False)
                remaining_time_text_m = gr.Textbox(label="Час до закінчення", interactive=False)
            btn_m.click(
                fn=batch_synthesize,
                inputs=[file_input_m, speed_m, model_name_m, speaker, save_option_m],
                outputs=[output_audio_m, part_slider_m, timer_text_m, start_time_text_m, end_time_text_m, est_end_time_text_m, remaining_time_text_m],
                show_progress=False
            )
        # GPT: Додаємо вкладку Multi Dialog
        with gr.TabItem('Multi Dialog'):
            text_input_d = gr.Textbox(label='📋 Введіть діалог або залиште порожнім і оберіть файл', lines=10, placeholder='Вставте діалог тут...')
            file_input_d = gr.File(label='Або оберіть текстовий файл', type='filepath')
            with gr.Row():
                speaker1 = gr.Dropdown(label='Спікер 1 (голос)', choices=prompts_list, value=prompts_list[0])
                speaker2 = gr.Dropdown(label='Спікер 2 (голос)', choices=prompts_list, value=prompts_list[0])
            with gr.Row():
                speed1 = gr.Slider(0.7, 1.3, value=0.88, label='🚀 Швидкість спікера 1')
                speed2 = gr.Slider(0.7, 1.3, value=0.88, label='🚀 Швидкість спікера 2')
            model_name_d = gr.Text(value='multi', visible=False)
            save_option_d = gr.Radio(choices=save_choices, label='Опції збереження', value=save_choices[1])
            btn_d = gr.Button('▶ Розпочати діалог')
            output_audio_d = gr.Audio(label='🔊 Поточна частина', type='filepath')
            part_slider_d = gr.Slider(label='Частина тексту', minimum=1, maximum=1, step=1, value=1, interactive=False)
            with gr.Row():
                timer_text_d = gr.Textbox(label="⏱️ Відлік часу (сек)", value="0", interactive=False)
                start_time_text_d = gr.Textbox(label="Початок озвучення", interactive=False)
                end_time_text_d = gr.Textbox(label="Закінчення озвучення попередньої частини", interactive=False)
            with gr.Row():
                est_end_time_text_d = gr.Textbox(label="Прогноз закінчення", interactive=False)
                remaining_time_text_d = gr.Textbox(label="Час до закінчення", interactive=False)

            btn_d.click(
                fn=batch_synthesize_dialog,
                inputs=[text_input_d, file_input_d, speed1, speed2, model_name_d, speaker1, speaker2, save_option_d],
                outputs=[output_audio_d, part_slider_d, timer_text_d, start_time_text_d, end_time_text_d, est_end_time_text_d, remaining_time_text_d],
                show_progress=False
            )
if __name__ == '__main__':
    demo.queue().launch()
