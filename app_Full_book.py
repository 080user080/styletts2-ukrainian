import os
import time
import gradio as gr
import soundfile as sf
from app import synthesize

OUTPUT_DIR = "output_audio"

def split_to_parts(text, max_chars=49000):
    split_symbols = '.?!:'
    parts = []
    buffer = ""

    for char in text:
        buffer += char
        if char in split_symbols and len(buffer) >= max_chars:
            parts.append(buffer.strip())
            buffer = ""
    
    if buffer.strip():
        parts.append(buffer.strip())

    return parts


def batch_synthesize(file_obj, speed):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ⏱️ Фіксуємо час початку
    global_start = time.time()
    print(f"\n🚀 START: {time.strftime('%H:%M:%S', time.localtime(global_start))}")

    file_path = file_obj.name
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    parts = split_to_parts(text)
    total_parts = len(parts)
    print(f"🔢 Усього частин до озвучення: {total_parts}")

    for idx, chunk in enumerate(parts, start=1):
        print("\n*** saying ***")
        print(chunk[:150].strip() + "..." if len(chunk) > 150 else chunk.strip())
        print("*** end ***")

        sr, audio_np = synthesize('single', chunk, speed)
        filename = os.path.join(OUTPUT_DIR, f"part_{idx:03}.wav")
        sf.write(filename, audio_np, sr)

        yield filename  # або більше полів, якщо потрібен прогрес

    # ✅ Фіксація завершення
    global_end = time.time()
    duration = global_end - global_start
    end_time_fmt = time.strftime('%H:%M:%S', time.localtime(global_end))
    print(f"\n✅ ЗАВЕРШЕНО о {end_time_fmt}")
    print(f"📦 Озвучено частин: {total_parts}")
    mins, secs = divmod(duration, 60)
    print(f"\033[92m⏱️ Загальний час виконання: {int(mins)} хв {int(secs)} сек\033[0m")

        

# Gradio UI
with gr.Blocks(title="Batch TTS з Прогресом") as demo:
    gr.Markdown("## 🗣️ Batch-озвучення з прогресом і тривалістю від запуску")
    file_input = gr.File(label='📄 Оберіть текстовий файл', file_count='single', type='filepath')
    speed = gr.Slider(0.7, 1.3, value=0.88, label='🚀 Швидкість')
    btn = gr.Button('▶ Розпочати озвучення')

    output_audio = gr.Audio(label='🔊 Поточна частина', type='filepath')
 
    btn.click(fn=batch_synthesize,
              inputs=[file_input, speed],
              outputs=[output_audio])

if __name__ == '__main__':
    demo.queue().launch()
