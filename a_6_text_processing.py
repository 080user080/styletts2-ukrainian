"""
a_6_text_processing.py
Нормалізація тексту, токенізація, розбиття на частини для PL-BERT (ліміт 512).
"""

import re
import unicodedata

try:
    from transformers import AutoTokenizer
except Exception:
    AutoTokenizer = None

# Ліміти безпеки
CHAR_CAP = 1200        # жорстка стеля по символах для одного шматка
HARD_MAX_TOKENS = 280  # цільовий бюджет токенів на шматок
PLBERT_MAX = 512
PLBERT_SAFE = 480      # запас безпеки перед 512

_tok = None
if AutoTokenizer is not None:
    try:
        _tok = AutoTokenizer.from_pretrained("albert-base-v2")
    except Exception:
        _tok = None


def normalize_text(s: str) -> str:
    """
    Нормалізує текст: уніфікація апострофів, тире, прибирання невидимих символів.
    НЕ чіпає '+'.
    """
    if not isinstance(s, str):
        return s
    s = unicodedata.normalize("NFKC", s).replace("\ufeff", "")
    # Уніфікація апострофів і тире
    s = (s.replace("'", "'").replace("ʼ", "'").replace("ʻ", "'").replace("ʹ", "'")
         .replace("—", "-").replace("–", "-").replace("−", "-"))
    # Прибрати невидимі керівні (Cf/Cc), зберегти \n \r \t і '+'
    out = []
    for ch in s:
        if ch == '+':
            out.append(ch)
            continue
        cat = unicodedata.category(ch)
        if cat in ("Cf", "Cc") and ch not in ("\n", "\r", "\t"):
            continue
        out.append(ch)
    s = "".join(out)
    # NBSP -> пробіл, підчистити пробіли навколо переносів
    s = s.replace("\u00A0", " ")
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s


def _tok_len(t: str) -> int:
    """Обчислює кількість токенів або консервативну оцінку."""
    if _tok is None:
        # СУПЕР-консервативний fallback: 1 символ ~ 1 токен + запас
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
    # Додаткова страховка: ріжемо дуже довгі шматки по комах/крапках
    safe = []
    for chunk in out:
        if len(chunk) <= CHAR_CAP and _tok_len(chunk) <= max_tokens:
            safe.append(chunk)
            continue
        frag = chunk
        while len(frag) > 0 and (_tok_len(frag) > max_tokens or len(frag) > CHAR_CAP):
            m = re.search(r'(.{200,}?[,;:])\s+', frag, flags=re.DOTALL)
            cut = m.end() if m else min(len(frag), max(300, len(frag) // 2))
            safe.append(frag[:cut].strip())
            frag = frag[cut:].lstrip()
        if frag:
            safe.append(frag)
    return safe


def split_to_parts(text: str, max_tokens: int = HARD_MAX_TOKENS) -> list[str]:
    """
    Розбиває текст на шматки ≤~280 токенів і ≤1200 символів.
    Поважає абзаци й речення, зберігає '+'.
    """
    text = normalize_text(text)
    chunks = []
    for para in re.split(r"\n{2,}", text.strip()):
        para = para.strip()
        if not para:
            continue
        sents = re.split(r"(?<=[\.\!\?…])\s+", para)
        buf = []
        for s in sents:
            cand = (" ".join(buf + [s])).strip() if buf else s.strip()
            if not cand:
                continue
            if _tok_len(cand) <= max_tokens and len(cand) <= CHAR_CAP:
                buf.append(s)
                continue
            if _tok_len(s) > max_tokens or len(s) > CHAR_CAP:
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
    # Фінальна перевірка
    safe_final = []
    for c in chunks:
        if _tok_len(c) <= max_tokens and len(c) <= CHAR_CAP:
            safe_final.append(c)
        else:
            safe_final.extend(_split_sentence_safe(c, max_tokens))
    return [c for c in safe_final if c]
