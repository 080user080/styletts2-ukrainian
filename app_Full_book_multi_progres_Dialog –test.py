import os
import time
import threading
import re
import gradio as gr
import soundfile as sf
# Припускаємо, що у вас є файл app.py з цими функціями
# from app import synthesize, prompts_list

# --- Заглушки для тестування, якщо app.py відсутній ---
def synthesize(mode, text, speed, voice_name=None, progress=None):
    """Функція-заглушка для synthesize."""
    print(f"Synthesizing: mode={mode}, voice={voice_name or 'default'}, speed={speed}, text='{text[:30]}...'")
    import numpy as np
    sample_rate = 24000
    duration = max(1, len(text) // 10) # Приблизна тривалість
    audio_np = np.random.randn(sample_rate * duration).astype(np.float32)
    time.sleep(duration * 0.5) # Імітація обробки
    return sample_rate, audio_np

prompts_list = [f"voice_{i:02d}" for i in range(1, 11)]
# --- Кінець заглушок ---


OUTPUT_DIR = "output_audio"

class NoProgress:
    """Клас для імітації tqdm без виведення в консоль."""
    def tqdm(self, iterable):
        return iterable


def format_hms(seconds):
    """Форматує секунди в HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"


def split_to_parts(text, max_chars=4900):
    """Розділяє великий текст на менші частини для синтезу."""
    paragraphs = text.split("\n\n")
    parts = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            parts.append(para)
        else:
            buffer = ""
            sentences = re.split(r'(?<=[.?!:;])\s+', para)
            for sentence in sentences:
                if len(buffer) + len(sentence) < max_chars:
                    buffer += sentence + " "
                else:
                    if buffer:
                        parts.append(buffer.strip())
                    buffer = sentence + " "
            if buffer:
                parts.append(buffer.strip())
    return parts


def parse_dialog_tags(text):
    """Парсить текст з тегами #gN: для розподілу реплік по голосах."""
    lines = text.splitlines()
    current_tag = 1 # За замовчуванням #g1
    parsed = []  # Список кортежів (номер_тегу, текст)

    tag_re = re.compile(r'^#g([1-9]|[12][0-9]|30)\s*:\s*(.*)$', re.I)

    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        m = tag_re.match(ln)
        if m:
            tag_num = int(m.group(1))
            remaining_text = m.group(2).strip()
            current_tag = tag_num
            # Якщо після тегу є текст, він також додається до озвучення
            if remaining_text:
                parts = split_to_parts(remaining_text)
                for p in parts:
                    parsed.append((current_tag, p))
        else:
            # Рядок без тегу належить поточному спікеру
            parts = split_to_parts(ln)
            for p in parts:
                parsed.append((current_tag, p))
    return parsed


def batch_synthesize_dialog(text_input, file_path, speeds_flat, voices_flat, save_option):
    """Основна функція для синтезу діалогів з кількома голосами."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    global_start = time.time()

    if (text_input or '').strip():
        text = text_input
    elif file_path:
        with open(file_path.name, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        raise gr.Error('Немає тексту для озвучення! Введіть його у текстове поле або завантажте файл.')

    parsed = parse_dialog_tags(text)
    total_parts = len(parsed)
    times_per_part = []

    voice_map = {i + 1: voices_flat[i] for i in range(30)}
    speed_map = {i + 1: float(speeds_flat[i]) for i in range(30)}

    for idx, (tag_num, chunk) in enumerate(parsed, start=1):
        part_start = time.time()
        voice = voice_map.get(tag_num)
        spd = speed_map.get(tag_num, 1.0)
        use_single = (voice == '00_Філатов')
        result = {}

        def run_synth():
            try:
                synth_mode = 'single' if use_single else 'multi'
                sr, audio_np = synthesize(synth_mode, chunk, spd, voice_name=voice, progress=NoProgress())
                result['sr'] = sr
                result['audio'] = audio_np
            except Exception as e:
                result['error'] = str(e)

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
                rem_text = f"залишилося {format_hms(rem_secs)}"

            yield (None, gr.update(value=idx, maximum=total_parts), elapsed_str, None, est_finish_str, rem_text)
            time.sleep(1)

        th.join()
        if 'error' in result:
            raise gr.Error(f"Помилка синтезу: {result['error']}")

        sr = result['sr']
        audio_np = result['audio']
        audio_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03d}.wav")
        sf.write(audio_filename, audio_np, sr)
        
        if save_option == 'Зберегти всі частини озвученого тексту':
            txt_filename = os.path.join(OUTPUT_DIR, f"part_{idx:03d}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as txt_file:
                txt_file.write(chunk)

        part_end = time.time()
        times_per_part.append(part_end - part_start)

        yield (audio_filename, gr.update(value=idx, maximum=total_parts), f"{int(part_end - global_start)} сек --- {format_hms(part_end - global_start)}", time.strftime('%H:%M:%S', time.localtime(part_end)), None, '')
    
    gr.Info('✅ Озвучення діалогу завершено!')


# --- Інтерфейс Gradio ---
save_choices = ['Зберегти всі частини озвученого тексту', 'Без збереження']
speaker_choices = ['00_Філатов'] + prompts_list
MAX_SPEAKERS = 30
INITIAL_SPEAKERS = 2

with gr.Blocks(title="Batch TTS з Прогресом", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Batch TTS з Прогресом\nСинтез мовлення для довгих текстів та діалогів.")
    
    with gr.Tabs():
        with gr.Tab("Multi Dialog (Кілька голосів)"):
            with gr.Row():
                with gr.Column(scale=2):
                    text_input_d = gr.Textbox(label='📋 Введіть діалог або залиште порожнім і оберіть файл', lines=10, placeholder='Приклад:\n#g1:\nПривіт, світе!\n#g2:\nПривіт, я інший голос.')
                    file_input_d = gr.File(label='Або завантажте текстовий файл (.txt)', type='file')
                    save_option_d = gr.Radio(choices=save_choices, label='Опції збереження', value=save_choices[1])
                    btn_d = gr.Button('▶ Розпочати діалог', variant='primary')
                
                with gr.Column(scale=3):
                    gr.Markdown("Налаштування голосів. Cпікер 1 відповідає тегу `#g1` і так далі.")
                    
                    # === ДИНАМІЧНИЙ ІНТЕРФЕЙС ДОДАВАННЯ ГОЛОСІВ ===
                    voice_components = []
                    speed_components = []
                    speaker_rows = []
                    
                    # Змінна для зберігання кількості видимих спікерів
                    visible_speakers_state = gr.State(value=INITIAL_SPEAKERS)

                    with gr.Blocks() as voice_config_ui:
                        for i in range(MAX_SPEAKERS):
                            # Показуємо перші INITIAL_SPEAKERS, решту ховаємо
                            is_visible = i < INITIAL_SPEAKERS
                            with gr.Row(visible=is_visible) as row:
                                gr.Markdown(f"**Спікер {i+1} (#g{i+1})**", scale=1)
                                dd = gr.Dropdown(label=None, show_label=False, choices=speaker_choices, value=speaker_choices[0], scale=4)
                                sv = gr.Slider(0.7, 1.3, value=1.0, step=0.05, label=None, show_label=False, scale=5)
                            speaker_rows.append(row)
                            voice_components.append(dd)
                            speed_components.append(sv)

                    with gr.Row():
                        add_voice_btn = gr.Button("➕ Додати голос", variant='secondary', size='sm')
                        reset_voices_btn = gr.Button("🔄 Скинути", size='sm')

            gr.Markdown("### Прогрес виконання")
            output_audio_d = gr.Audio(label='🔊 Остання озвучена частина', type='filepath')
            part_slider_d = gr.Slider(label='Частина тексту', minimum=1, maximum=1, step=1, value=1, interactive=False)
            with gr.Row():
                timer_text_d = gr.Textbox(label="⏱️ Загальний час", value="0", interactive=False)
                end_time_text_d = gr.Textbox(label="Завершено о", interactive=False)
                est_end_time_text_d = gr.Textbox(label="Прогноз закінчення", interactive=False)
                remaining_time_text_d = gr.Textbox(label="Залишилося часу", interactive=False)
            
            # --- Логіка для динамічних компонентів ---
            def add_voice(count):
                """Робить видимим наступний рядок налаштувань голосу."""
                updates = {}
                if count < MAX_SPEAKERS:
                    updates[speaker_rows[count]] = gr.update(visible=True)
                    updates[visible_speakers_state] = count + 1
                if count + 1 >= MAX_SPEAKERS:
                    updates[add_voice_btn] = gr.update(interactive=False)
                return updates
            
            def reset_voices():
                """Скидає кількість видимих голосів до початкового значення."""
                updates = {}
                for i in range(INITIAL_SPEAKERS, MAX_SPEAKERS):
                    updates[speaker_rows[i]] = gr.update(visible=False)
                updates[visible_speakers_state] = INITIAL_SPEAKERS
                updates[add_voice_btn] = gr.update(interactive=True)
                return updates

            add_voice_btn.click(
                fn=add_voice,
                inputs=[visible_speakers_state],
                outputs=[visible_speakers_state, add_voice_btn] + speaker_rows
            )
            
            reset_voices_btn.click(
                fn=reset_voices,
                inputs=None,
                outputs=[visible_speakers_state, add_voice_btn] + speaker_rows
            )
            
            # --- Логіка для кнопки запуску синтезу ---
            btn_inputs = [text_input_d, file_input_d] + speed_components + voice_components + [save_option_d]
            btn_outputs = [output_audio_d, part_slider_d, timer_text_d, end_time_text_d, est_end_time_text_d, remaining_time_text_d]

            def _btn_d_handler(text_input, file_input, *flat_values):
                speeds = list(flat_values[:MAX_SPEAKERS])
                voices = list(flat_values[MAX_SPEAKERS : MAX_SPEAKERS * 2])
                save_option = flat_values[-1]
                yield from batch_synthesize_dialog(text_input, file_input, speeds, voices, save_option)

            btn_d.click(
                fn=_btn_d_handler,
                inputs=btn_inputs,
                outputs=btn_outputs
            )

if __name__ == '__main__':
    demo.queue().launch(debug=True)

