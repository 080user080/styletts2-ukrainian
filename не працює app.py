import glob
import os
import re
import gradio as gr
import copy
import soundfile as sf
import spaces
from verbalizer import Verbalizer
import torch
from ipa_uk import ipa
from unicodedata import normalize
from styletts2_inference.models import StyleTTS2
from ukrainian_word_stress import Stressifier, StressSymbol
stressify = Stressifier()

device = 'cuda' if torch.cuda.is_available() else 'cpu'
use_fp16 = torch.cuda.is_available()

prompts_dir = 'voices'

verbalizer = Verbalizer(device=device)


def split_to_parts(text):
    split_symbols = '.?!:'
    parts = ['']
    index = 0
    for s in text:
        parts[index] += s
        if s in split_symbols and len(parts[index]) > 150:
            index += 1
            parts.append('')
    return parts



single_model = StyleTTS2(hf_path='patriotyk/styletts2_ukrainian_single', device=device)
single_model.eval()
if use_fp16:
    single_model.half()
# стиль повинен бути на тому ж девайсі та в тому ж dtype
single_style = torch.load('filatov.pt', map_location=device)
single_style = (single_style.half() if use_fp16 else single_style.float()).to(device)


multi_model = StyleTTS2(hf_path='patriotyk/styletts2_ukrainian_multispeaker', device=device)
multi_model.eval()
if use_fp16:
    multi_model.half()
#multi_model = StyleTTS2(
#    config_path='d:/TTS/NEW/config.yml',
#    weights_path='d:/TTS/NEW/pytorch_model.bin',
#    device=device
#)

multi_styles = {}
 # Зафіксовані токенайзери, щоб multi не перетирав single
single_tok = copy.deepcopy(single_model.tokenizer)
multi_tok  = copy.deepcopy(multi_model.tokenizer)

prompts_list = sorted(glob.glob(os.path.join(prompts_dir, '*.pt')))
prompts_list = [os.path.splitext(os.path.basename(p))[0] for p in prompts_list]# моя добавка

#prompts_list = ['.'.join(p.split('/')[-1].split('.')[:-1]) for p in prompts_list]

#print(f"Using prompts_dir: {prompts_dir}")  # Додано для перевірки
#print(f"All files found: {prompts_list}")  # Додано для перевірки

for audio_prompt in prompts_list:
    audio_path = os.path.join(prompts_dir, audio_prompt+'.pt')
    #audio_path = os.path.abspath(os.path.join(prompts_dir, audio_prompt + '.pt'))
#    print(f"Trying to load: {audio_path}")  # Додано для перевірки
    st = torch.load(audio_path, map_location=device)
    st = (st.half() if use_fp16 else st.float()).to(device)
    multi_styles[audio_prompt] = st
    print('loaded ', audio_prompt)

# --- Приведення стилів до узгодженого формату/dtype/device ---
def _coerce_style(x):
    """
    Приводить стиль до torch.Tensor на потрібному девайсі та dtype.
    Підтримує формати: Tensor | dict | list/tuple.
    """
    t = x
    if isinstance(t, dict):
        for k in ('style', 's_prev', 'embedding', 'z', 'vec'):
            if k in t:
                t = t[k]
                break
        else:
            t = next(iter(t.values()))
    if isinstance(t, (list, tuple)):
        t = torch.as_tensor(t)
    if not isinstance(t, torch.Tensor):
        t = torch.tensor(t)
    t = t.to(device)
    if use_fp16 and t.dtype != torch.float16:
        t = t.half()
    if not use_fp16 and t.dtype != torch.float32:
        t = t.float()
    return t

models = {
    'multi': {
        'model': multi_model,
        'styles': {k: _coerce_style(v) for k, v in multi_styles.items()}
    },
    'single': {
        'model': single_model,
        'style': _coerce_style(single_style)
    }
}

# (токенайзери вже зафіксовані вище)


def verbalize(text):
    parts = split_to_parts(text)
    verbalized = ''
    for part in parts:
        verbalized += verbalizer.generate_text(part)
    return verbalized

description = f'''
<h1 style="text-align:center;">StyleTTS2: Українська. ОНОВЛЕНО BOSS-оМ</h1><br>
Програма може не коректно визначати деякі наголоси.
Якщо наголос не правильний, використовуйте символ + після наголошеного складу.
Текст який складається з одного слова може синтезуватися з певними артефактами, пишіть повноцінні речення.
Якщо текст містить цифри чи акроніми, можна натисну кнопку "Вербалізувати" яка повинна замінити цифри і акроніми
в словесну форму.

'''

examples = [
   # ["Решта окупантів звернула на Вокзальну — центральну вулицю Бучі. Тільки уявіть їхній настрій, коли перед ними відкрилася ця пасторальна картина! Невеличкі котеджі й просторіші будинки шикуються обабіч, перед ними вивищуються голі липи та електро-стовпи, тягнуться газони й жовто-чорні бордюри. Доглянуті сади визирають із-поза зелених парканів, гавкотять собаки, співають птахи… На дверях будинку номер тридцять шість досі висить різдвяний вінок.", 1.0],
    ["Одна дівчинка стала королевою Франції. Звали її Анна, і була вона донькою Ярослава Му+дрого, великого київського князя. Він опі+кувався літературою та культурою в Київській Русі+, а тоді переважно про таке не дбали – більше воювали і споруджували фортеці.", 1.0],
   # ["Одна дівчинка народилася і виросла в Америці, та коли стала дорослою, зрозуміла, що дуже любить українські вірші й найбільше хоче робити вистави про Україну. Звали її Вірляна. Дід Вірляни був український мовознавець і педагог Кость Кисілевський, котрий навчався в Лейпцизькому та Віденському університетах і, після Другої світової війни виїхавши до США, започаткував систему шкіл українознавства по всій Америці. Тож Вірляна зростала в українському середовищі, а окрім того – в середовищі вихідців з інших країн.", 1.0],
  #  ["За інформацією від Державної служби з надзвичайних ситуацій станом на 7 ранку 15 липня.", 1.0],
   # ["Очікується, що цей застосунок буде запущено 22.08.2025.", 1.0],
]



SINGLE_SR = 24000
MULTI_SR  = 22050  # для більшості multi-укр чекпоінтів
OUTPUT_DIR = "output_audio"
SINGLE_QUEUE = os.path.join(OUTPUT_DIR, "_single_queue")

def _concat_to_numpy(wavs: list[torch.Tensor]) -> tuple[int, "np.ndarray"]:
    import numpy as _np
    wav = torch.cat(wavs, dim=-1) if len(wavs) > 1 else wavs[0]
    arr = wav.detach().float().cpu().numpy()
    arr = _np.clip(arr, -1.0, 1.0).astype("float32")
    # повертаємо SR пізніше згідно режиму
    return arr

# --- Окремий препроцесинг для single / multi ---
def _prep_single(t: str) -> str:
    # single: БЕЗ IPA/stressify; '+' -> комбінуючий наголос; нормалізація NFC
    t = t.strip().replace('"', '')
    t = t.replace('+', StressSymbol.CombiningAcuteAccent)
    t = normalize('NFC', t)
    # тире можна уніфікувати, це не впливає на алфавіт
    t = re.sub(r'[᠆‐-‒–—―⁻₋−⸺⸻]', '-', t)
    return t

def _prep_multi(t: str) -> str:
    # multi: '+' -> комбінуючий наголос + IPA/stressify
    t = t.strip().replace('"', '')
    t = t.replace('+', StressSymbol.CombiningAcuteAccent)
    t = normalize('NFKC', t)
    t = re.sub(r'[᠆‐-‒–—―⁻₋−⸺⸻]', '-', t)
    t = re.sub(r' - ', ': ', t)
    return ipa(stressify(t))

# (без черги; все з однієї вкладки)

# (видалено дубль _prep_single/_prep_multi)

def synthesize(model_name, text, speed, voice_name=None, progress=gr.Progress()):
    if text.strip() == "":
        raise gr.Error("You must enter some text")
    if len(text) > 50000:
        raise gr.Error("Text must be <50k characters")

    print("*** saying ***")
    print(f"[mode={model_name}] [speed={speed}] [voice={voice_name}]")
    print(text)
    print("*** end ***")

    result_wav = []
    for t in progress.tqdm(split_to_parts(text)):
        t = t.strip()
        if not t:
            continue

        # окремий препроцесинг
        ps = _prep_single(t) if model_name == "single" else _prep_multi(t)
        if model_name == "single":
            # діагностика: переконайтеся, що наголос став комбінуючим символом
            if '́' not in ps:  # U+0301
                print("[WARN single] Немає комбінуючого наголосу U+0301 у цьому шматку.")
        if not ps:
            continue

        mdl = models[model_name]["model"]
        tok = single_tok if model_name == "single" else multi_tok
        try:
            ids = tok.encode(ps)
            token_ids = torch.as_tensor(ids, dtype=torch.long, device=device)
            style = (
                models[model_name]["styles"][voice_name]
                if voice_name
                else models[model_name]["style"]
            )
            with torch.inference_mode():
                wav = mdl(token_ids, speed=speed, s_prev=style)
            if wav.dim() > 1:
                wav = wav.squeeze()
            result_wav.append(wav)
        except Exception as e:
            print(f"[ERROR synthesize] chunk failed: {type(e).__name__}: {e}")
            continue

    sr = SINGLE_SR if model_name == "single" else MULTI_SR
    if not result_wav:
        raise gr.Error("Порожній результат синтезу")
    return sr, _concat_to_numpy(result_wav)


def select_example(df, evt: gr.SelectData):
    return evt.row_value   
    
with gr.Blocks() as single:
    with gr.Row():
        with gr.Column(scale=1):
            input_text = gr.Text(label='Text:', lines=5, max_lines=10)
            verbalize_button = gr.Button("Вербалізувати(beta)")
            speed = gr.Slider(label='Швидкість:', maximum=1.3, minimum=0.7, value=0.9)
            verbalize_button.click(verbalize, inputs=[input_text], outputs=[input_text])
            # Кнопка: синтезувати всю чергу Філатова
            synth_queue_btn = gr.Button("Синтезувати чергу Філатова")
            
        with gr.Column(scale=1):
            output_audio = gr.Audio(
                    label="Audio:",
                    autoplay=False,
                    streaming=False,
                    type="numpy",
                )
            synthesise_button = gr.Button("Синтезувати")
            single_text = gr.Text(value='single', visible=False)
            synthesise_button.click(synthesize, inputs=[single_text, input_text, speed], outputs=[output_audio])
            # Обробник черги single
            def _synthesize_single_queue(spd):
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                if not os.path.isdir(SINGLE_QUEUE):
                    raise gr.Error("Черга порожня.")
                files = sorted([f for f in os.listdir(SINGLE_QUEUE) if f.endswith(".txt")])
                if not files:
                    raise gr.Error("Черга порожня.")
                last_audio = None
                for fname in files:
                    path = os.path.join(SINGLE_QUEUE, fname)
                    txt = open(path, "r", encoding="utf-8").read()
                    ps = _prep_single(txt)
                    mdl = models["single"]["model"]
                    with torch.inference_mode():
                        tokens = single_tok.encode(ps)
                        wav = mdl(tokens, speed=spd, s_prev=models["single"]["style"])
                        if wav.dim() > 1:
                            wav = wav.squeeze()
                    arr = wav.detach().float().cpu().numpy()
                    arr = (arr.clip(-1.0, 1.0)).astype("float32")
                    os.makedirs(OUTPUT_DIR, exist_ok=True)
                    out_name = os.path.splitext(fname)[0] + ".wav"  # part_XXX.wav
                    out_path = os.path.join(OUTPUT_DIR, out_name)
                    sf.write(out_path, arr, SINGLE_SR)
                    last_audio = (SINGLE_SR, arr)
                    os.remove(path)
                    print(f"[SINGLE] Збережено {out_path}")
                return last_audio
            synth_queue_btn.click(_synthesize_single_queue, inputs=[speed], outputs=[output_audio])
    
    with gr.Row():
        examples_table = gr.Dataframe(wrap=True, headers=["Текст", "Швидкість"], datatype=["str", "number"], value=examples, interactive=False)
        examples_table.select(select_example, inputs=[examples_table], outputs=[input_text, speed])
    
with gr.Blocks() as multy:
    with gr.Row():
        with gr.Column(scale=1):
            input_text = gr.Text(label='Text:', lines=5, max_lines=10)
            verbalize_button = gr.Button("Вербалізувати(beta)")
            speed = gr.Slider(label='Швидкість:', maximum=1.3, minimum=0.7, value=0.9)
            speaker = gr.Dropdown(label="Голос:", choices=prompts_list, value=prompts_list[0])
            verbalize_button.click(verbalize, inputs=[input_text], outputs=[input_text])

        with gr.Column(scale=1):
            output_audio = gr.Audio(
                    label="Audio:",
                    autoplay=False,
                    streaming=False,
                    type="numpy",
                )
            synthesise_button = gr.Button("Синтезувати")
            multi = gr.Text(value='multi', visible=False)
            
            synthesise_button.click(synthesize, inputs=[multi, input_text, speed, speaker], outputs=[output_audio])
    with gr.Row():
        examples_table = gr.Dataframe(wrap=True, headers=["Текст", "Швидкість"], datatype=["str", "number"], value=examples, interactive=False)
        examples_table.select(select_example, inputs=[examples_table], outputs=[input_text, speed])




with gr.Blocks(title="StyleTTS2 ukrainian", css="") as demo:
    gr.Markdown(description)
    gr.TabbedInterface([single, multy], ['Single speaker', 'Multі speaker'])
    

if __name__ == "__main__":
    demo.queue(api_open=True, max_size=15).launch(show_api=True)