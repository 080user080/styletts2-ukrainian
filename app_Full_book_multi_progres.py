import os
import time
import threading
import gradio as gr
import soundfile as sf
from app_multi_novuj_vocoder import synthesize as synthesize_sync, prompts_list

OUTPUT_DIR = "output_audio"

# Dummy progress to bypass gr.Progress inside vocoder
class NoProgress:
    def tqdm(self, iterable):
        return iterable

# Розбиття тексту на частини
# Залишаємо максимальну довжину для частини

#GPT  49000
def split_to_parts(text, max_chars=10000):
    # Спочатку розбиваємо по подвійних ентерах
    paragraphs = text.split("\n\n")
    parts = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Якщо абзац коротший за max_chars — додаємо одразу
        if len(para) <= max_chars:
            parts.append(para)
        else:
            # Інакше розбиваємо абзац по розділових знаках
            buffer = ""
            for char in para:
                buffer += char
                if char in ".?!:;" and len(buffer) >= max_chars:
                    parts.append(buffer.strip())
                    buffer = ""
            if buffer.strip():
                parts.append(buffer.strip())

    return parts

# форматування часу в години:хвилини:секунди
def format_hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

# Функція для batch-озвучення з прогресом і виведенням номера частини

def batch_synthesize(file_path, speed, model_name, speaker, save_option):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global_start = time.time()
    first_part_start = None
    last_part_end = None

    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    parts = split_to_parts(text)
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
                sr, audio_np = synthesize_sync(
                    model_name, chunk, speed,
                    voice_name=(speaker or None),
                    progress=NoProgress()
                )
                result['sr'] = sr
                result['audio'] = audio_np
            except Exception as e:
                result['error'] = str(e)

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
            raise RuntimeError(f"Synthesis error: {result['error']}")

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
if __name__ == '__main__':
    demo.queue().launch()
