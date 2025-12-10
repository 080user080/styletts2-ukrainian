# звук з оригінального файлу
import glob
import os
import re
import gradio as gr
import spaces
from verbalizer import Verbalizer
import torch
from ipa_uk import ipa
from unicodedata import normalize
from styletts2_inference.models import StyleTTS2
from ukrainian_word_stress import Stressifier, StressSymbol
stressify = Stressifier()

device = 'cuda' if torch.cuda.is_available() else 'cpu'

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
single_style = torch.load('filatov.pt')


multi_model = StyleTTS2(hf_path='patriotyk/styletts2_ukrainian_multispeaker', device=device)
#multi_model = StyleTTS2(
#    config_path='d:/TTS/NEW/config.yml',
#    weights_path='d:/TTS/NEW/pytorch_model.bin',
#    device=device
#)

multi_styles = {}

prompts_list = sorted(glob.glob(os.path.join(prompts_dir, '*.pt')))
prompts_list = [os.path.splitext(os.path.basename(p))[0] for p in prompts_list]# моя добавка

#prompts_list = ['.'.join(p.split('/')[-1].split('.')[:-1]) for p in prompts_list]

#print(f"Using prompts_dir: {prompts_dir}")  # Додано для перевірки
#print(f"All files found: {prompts_list}")  # Додано для перевірки

for audio_prompt in prompts_list:
    audio_path = os.path.join(prompts_dir, audio_prompt+'.pt')
    #audio_path = os.path.abspath(os.path.join(prompts_dir, audio_prompt + '.pt'))
#    print(f"Trying to load: {audio_path}")  # Додано для перевірки
    multi_styles[audio_prompt] = torch.load(audio_path)
    print('loaded ', audio_prompt)

models = {
    'multi': {
        'model': multi_model,
        'styles': multi_styles
    },
    'single': {
        'model': single_model,
        'style': single_style
    }
}


#@spaces.GPU
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



#@spaces.GPU
def synthesize(model_name, text, speed, voice_name = None, progress=gr.Progress()):
    
    if text.strip() == "":
        raise gr.Error("You must enter some text")
    if len(text) > 50000:
        raise gr.Error("Text must be <50k characters")
    print("*** saying ***")
    print(text)
    print("*** end ***")
    

    result_wav = []
    for t in progress.tqdm(split_to_parts(text)):

        t = t.strip()
        t = t.replace('"', '')
        if t:
            t = t.replace('+', StressSymbol.CombiningAcuteAccent)
            t = normalize('NFKC', t)

            t = re.sub(r'[᠆‐‑‒–—―⁻₋−⸺⸻]', '-', t)
            t = re.sub(r' - ', ': ', t)
            ps = ipa(stressify(t))

            if ps:
                tokens = models[model_name]['model'].tokenizer.encode(ps)
                if voice_name:
                    style = models[model_name]['styles'][voice_name]
                else:
                    style = models[model_name]['style']
                
                wav = models[model_name]['model'](tokens, speed=speed, s_prev=style)
                result_wav.append(wav)

    
    return 24000, torch.concatenate(result_wav).cpu().numpy()



def select_example(df, evt: gr.SelectData):
    return evt.row_value   
    
with gr.Blocks() as single:
    with gr.Row():
        with gr.Column(scale=1):
            input_text = gr.Text(label='Text:', lines=5, max_lines=10)
            verbalize_button = gr.Button("Вербалізувати(beta)")
            speed = gr.Slider(label='Швидкість:', maximum=1.3, minimum=0.7, value=0.9)
            verbalize_button.click(verbalize, inputs=[input_text], outputs=[input_text])
            
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