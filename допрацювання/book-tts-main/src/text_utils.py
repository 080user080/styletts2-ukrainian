import re
from num2words import num2words
from unicodedata import normalize as uni_normalize

_pad = "$"
_punctuation = '-´;:,.!?¡¿—…"«»“” ()†/='
_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
_letters_ipa = "éýíó'̯'͡ɑɐɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴøɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱʌɣɤʍχʎʏʑʐʒʔʡʕʢǀǁǂǃˈˌːˑʼʴʰʱʲ'̩'ᵻ"

symbols = [_pad] + list(_punctuation) + list(_letters) + list(_letters_ipa)
letters = list(_letters) + list(_letters_ipa)
dicts = {symbol: i for i, symbol in enumerate(symbols)}

def text_cleaner(text):
    return [dicts[char] for char in text if char in dicts]

def split_to_chunks(text, max_chunk_size):
    sentences = re.findall(r'[^.!?]+[.!?]+', text) or [text]
    chunks, current_chunk = [], ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_chunk_size:
            current_chunk += sentence
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def replace_numbers_with_words(text):
    return re.sub(r'\d+', lambda match: num2words(int(match.group()), lang='uk'), text)

def normalize(t):
    t = uni_normalize(
        "NFKC",
        (
            t.strip()
             .replace('"', "")
             .replace("*", "")
             .replace("+", "ˈ")
             .replace("[", "")
             .replace("]", "")
        )
    )
    t = re.sub(r'[᠆‐‑‒–—―⁻₋−⸺⸻]', '-', t)
    return re.sub(r' - ', ': ', t)

def split_to_sentence(text):
    if not text.strip():
        return []

    # Регулярний вираз для пошуку речень
    split_symbols = r'(?<=[.?!:;])\s+'
    parts, buffer = re.split(split_symbols, text), ''
    result = []

    for part in parts:
        if len(buffer) + len(part) > 150:
            result.extend(split_by_middle(buffer.strip()))
            buffer = part
        else:
            buffer += ' ' + part if buffer else part

    if buffer:
        result.extend(split_by_middle(buffer.strip()))

    return list(filter(None, result))

def split_by_middle(text):
    if len(text) <= 350:
        return [text]

    middle_index = len(text) // 2
    symbols = [',', '-']

    # Перевірка наявності хоча б одного символу в тексті
    positions = [
        (text.rfind(symbol, 0, middle_index), text.find(symbol, middle_index))
        for symbol in symbols if symbol in text
    ]

    # Якщо не знайдено жодного символу, додаємо перевірку на порожній список
    if positions:
        closest_symbol_index = min(positions, key=lambda x: min(x[0], x[1]))[0]
        if closest_symbol_index != -1:
            return split_by_middle(text[:closest_symbol_index] + '.') + split_by_middle(text[closest_symbol_index + 1:])

    # Пошук пробілів до і після середини
    before_middle_space = text.rfind(' ', 0, middle_index)
    after_middle_space = text.find(' ', middle_index)

    # Логіка для розбиття за пробілами
    if before_middle_space != -1 and (after_middle_space == -1 or middle_index - before_middle_space < after_middle_space - middle_index):
        return split_by_middle(text[:before_middle_space] + '.') + split_by_middle(text[before_middle_space + 1:])
    elif after_middle_space != -1:
        return split_by_middle(text[:after_middle_space] + '.') + split_by_middle(text[after_middle_space + 1:])

    # Якщо немає жодного зручного символу для розбиття
    return [text]

def transliterate(word):
    translit_map = {
        'a': 'а', 'b': 'б', 'c': 'к', 'd': 'д', 'e': 'е',
        'f': 'ф', 'g': 'г', 'h': 'х', 'i': 'і', 'j': 'дж',
        'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о',
        'p': 'п', 'q': 'к', 'r': 'р', 's': 'с', 't': 'т',
        'u': 'у', 'v': 'в', 'w': 'в', 'x': 'кс', 'y': 'й', 'z': 'з',
        'ch': 'ч', 'sh': 'ш', 'th': 'с', 'ph': 'ф', 'ng': 'нг'
    }

    # Обробка диграфів (наприклад, "sh", "ch")
    digraphs = ['ch', 'sh', 'th', 'ph', 'ng']
    result = ''
    i = 0
    word = word.lower()

    while i < len(word):
        if i + 1 < len(word) and word[i:i+2] in translit_map:
            result += translit_map[word[i:i+2]]
            i += 2
        elif word[i] in translit_map:
            result += translit_map[word[i]]
            i += 1
        else:
            result += word[i]  # залишаємо символ без змін, якщо не розпізнано
            i += 1

    return result