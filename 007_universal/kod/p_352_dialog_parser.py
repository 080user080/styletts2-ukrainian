"""
p_352_tts_dialog_parser.py - Парсер сценаріїв Multi Dialog для TTS.
Розбиває текст на частини з урахуванням обмежень токенів.
Підтримує теги #gN, суфікси швидкості та SFX.
"""

import re
import unicodedata
import logging
from typing import Dict, Any, List, Tuple, Optional

import numpy as np

# Константи для PL-BERT (не перевищувати 512 токенів)
PLBERT_MAX = 512
PLBERT_SAFE = 480  # Запас безпеки перед максимумом
HARD_MAX_TOKENS = 280  # Цільовий бюджет токенів на шматок
CHAR_CAP = 1200  # Максимум символів на шматок
SPEAKER_MAX = 30


class DialogParser:
    """Парсер сценаріїв Multi Dialog для TTS."""
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("DialogParser")
        self.tts_engine = app_context.get('tts_engine')
        self._tokenizer = self._init_tokenizer()
        self.logger.info("✅ Dialog Parser ініціалізовано")
    
    def _init_tokenizer(self):
        """Ініціалізація токенізатора."""
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained("albert-base-v2")
            self.logger.debug("Токенізатор Albert завантажено")
            return tokenizer
        except Exception as e:
            self.logger.warning(f"Токенізатор недоступний: {e}. Використовуються наближені розрахунки")
            return None
    
    def _token_length(self, text: str) -> int:
        """Оцінити довжину в токенах."""
        if self._tokenizer:
            try:
                return len(self._tokenizer.encode(text, add_special_tokens=True))
            except Exception:
                pass
        
        # Консервативний fallback: 1 символ ~ 1 токен + 32 для запасу
        return len(text) + 32
    
    def normalize_text(self, text: str) -> str:
        """
        Нормалізація тексту БЕЗ змін символу '+'.
        Символ '+' використовується для вказання наголосу.
        """
        if not isinstance(text, str):
            return str(text) if text else ""
        
        # NFKC нормалізація
        text = unicodedata.normalize("NFKC", text).replace("\ufeff", "")
        
        # Уніфікація апострофів та тире
        text = (text.replace("'", "'")
                   .replace("'", "'")
                   .replace("ʼ", "'")
                   .replace("ʻ", "'")
                   .replace("ʹ", "'")
                   .replace("—", "-")
                   .replace("–", "-")
                   .replace("−", "-"))
        
        # Видалення невидимих символів, збереження \n, \r, \t, '+'
        out = []
        for ch in text:
            if ch == '+':
                out.append(ch)
                continue
            
            cat = unicodedata.category(ch)
            if cat in ("Cf", "Cc") and ch not in ("\n", "\r", "\t"):
                continue
            out.append(ch)
        
        text = "".join(out)
        
        # NBSP → звичайний пробіл
        text = text.replace("\u00A0", " ")
        
        # Очищення пробілів навколо переносів
        text = re.sub(r"\s*\n\s*", "\n", text)
        
        return text.strip()
    
    def _split_sentence_safe(self, sent: str, max_tokens: int) -> List[str]:
        """Розбиває наддовге речення по словах без порушення структури."""
        parts, buf = [], []
        
        for tok in re.findall(r"\S+\s*|\s+", sent):
            buf.append(tok)
            if self._token_length("".join(buf)) > max_tokens:
                if len(buf) == 1:
                    # Навіть одне слово перевищує ліміт - ріжемо по частинах
                    chunk = tok
                    while self._token_length(chunk) > max_tokens:
                        cut = max(64, int(len(chunk) * 0.7))
                        parts.append(chunk[:cut])
                        chunk = chunk[cut:]
                    buf = [chunk]
                else:
                    # Помітити останнє слово та накопити попередні
                    last = buf.pop()
                    parts.append("".join(buf).strip())
                    buf = [last]
        
        if buf:
            parts.append("".join(buf).strip())
        
        out = [p for p in parts if p]
        
        # Додаткова страховка: ріжемо дуже довгі шматки
        safe = []
        for chunk in out:
            if len(chunk) <= CHAR_CAP and self._token_length(chunk) <= max_tokens:
                safe.append(chunk)
                continue
            
            frag = chunk
            while len(frag) > 0 and (self._token_length(frag) > max_tokens or len(frag) > CHAR_CAP):
                m = re.search(r'(.{200,}?[,;:])\s+', frag, flags=re.DOTALL)
                cut = m.end() if m else min(len(frag), max(300, len(frag)//2))
                safe.append(frag[:cut].strip())
                frag = frag[cut:].lstrip()
            
            if frag:
                safe.append(frag)
        
        return safe
    
    def split_to_parts(self, text: str, max_tokens: int = HARD_MAX_TOKENS) -> List[str]:
        """
        Розбиває текст на частини з урахуванням:
          - Ліміту токенів (max_tokens, зазвичай 280)
          - Максимуму символів (1200)
          - Абзаців та речень
        
        Args:
            text: Вхідний текст
            max_tokens: Максимум токенів на частину
        
        Returns:
            Список частин тексту
        """
        text = self.normalize_text(text)
        chunks = []
        
        # Розбиваємо по абзацах
        for para in re.split(r"\n{2,}", text.strip()):
            para = para.strip()
            if not para:
                continue
            
            # Розбиваємо по реченнях (послідовності символів перед . ! ? …)
            sents = re.split(r"(?<=[\.\!\?…])\s+", para)
            buf = []
            
            for s in sents:
                cand = (" ".join(buf + [s])).strip() if buf else s.strip()
                if not cand:
                    continue
                
                # Перевіряємо, чи вміщується в бюджет
                if self._token_length(cand) <= max_tokens and len(cand) <= CHAR_CAP:
                    buf.append(s)
                    continue
                
                # Якщо навіть речення довше бюджету - дробимо його
                if self._token_length(s) > max_tokens or len(s) > CHAR_CAP:
                    if buf:
                        chunks.append(" ".join(buf).strip())
                        buf = []
                    chunks.extend(self._split_sentence_safe(s, max_tokens))
                else:
                    if buf:
                        chunks.append(" ".join(buf).strip())
                    buf = [s]
            
            if buf:
                chunks.append(" ".join(buf).strip())
        
        # Фінальна перевірка кожного шматка
        safe_final = []
        for c in chunks:
            if self._token_length(c) <= max_tokens and len(c) <= CHAR_CAP:
                safe_final.append(c)
            else:
                safe_final.extend(self._split_sentence_safe(c, max_tokens))
        
        return [c for c in safe_final if c]
    
    def parse_script_events(self, text: str, voices_flat: List[str]) -> List[dict]:
        """
        Парсить сценарій у список подій.
        
        Формати тегів:
          #gN[_slow|_fast|_slowNN|_fastNN]: текст  → voice подія
          #<sfx_id>                                → sfx подія
        
        Args:
            text: Текст сценарію
            voices_flat: Список голосів (для валідації)
        
        Returns:
            Список словників подій
        """
        events: List[dict] = []
        if not isinstance(text, str):
            return events
        
        lines = self.normalize_text(text).splitlines()
        
        # Паттерн для voice подій: #g1_fast: текст
        voice_pat = re.compile(
            r"^#g\s*([1-9]|[12][0-9]|30)(?:_((?:slow|fast)(?:\d{1,3})?))?\s*:??\s+(.*)$",
            re.IGNORECASE
        )
        
        # Паттерн для SFX подій: #bell_sound
        sfx_pat = re.compile(r'^#([A-Za-z0-9_]+)\s*$', re.IGNORECASE)
        
        for line_no, raw_ln in enumerate(lines, start=1):
            ln = raw_ln.strip()
            if not ln:
                continue
            
            # Перевіра voice тегу
            m_voice = voice_pat.match(ln)
            if m_voice:
                g_str, suffix, text_body = m_voice.groups()
                g_num = int(g_str)
                suffix = suffix.lower() if suffix else ""
                
                if not text_body.strip():
                    raise RuntimeError(f"Порожній текст після тега #g{g_num} на рядку {line_no}")
                
                if g_num < 1 or g_num > SPEAKER_MAX:
                    raise RuntimeError(f"Неприпустимий номер спікера: {g_num} на рядку {line_no}")
                
                events.append({
                    "type": "voice",
                    "g": g_num,
                    "suffix": suffix,
                    "text": text_body
                })
                continue
            
            # Перевіра SFX тегу
            m_sfx = sfx_pat.match(ln)
            if m_sfx:
                sfx_id = m_sfx.group(1)
                
                # Валідація SFX у конфігурації
                sfx_handler = self.app_context.get('sfx_handler')
                if sfx_handler and not sfx_handler.validate_sfx_id(sfx_id):
                    raise RuntimeError(f"SFX '{sfx_id}' не знайдено у конфігу sfx.yaml (рядок {line_no})")
                
                events.append({
                    "type": "sfx",
                    "id": sfx_id,
                    "params": {}
                })
                continue
            
            # Коментарі (рядки, що починаються з #)
            if ln.startswith('#'):
                continue
            
            # Звичайний текст без тегу → спікер #g1
            events.append({
                "type": "voice",
                "g": 1,
                "suffix": "",
                "text": ln
            })
        
        return events
    
    def compute_speed_effective(self, g_num: int, suffix: str, 
                               speeds_flat: List[float], ignore_speed: bool = False) -> float:
        """
        Обчислює ефективну швидкість для voice-події.
        
        Пріоритет:
          1) Якщо ignore_speed=True → DEFAULT_SPEED
          2) Якщо suffix='slow' або 'fast' → 0.80 або 1.20
          3) Якщо suffix='slow95' → 0.95
          4) Іншомомірно → speeds_flat[g_num]
        """
        if ignore_speed:
            return 0.88  # Дефолт, можна отримати з конфігу
        
        suf = suffix.lower() if suffix else ""
        
        if suf == 'slow':
            return 0.80
        if suf == 'fast':
            return 1.20
        
        # Парсинг slow95, fast110
        if suf.startswith('slow') and len(suf) > 4:
            try:
                val = float(suf[4:]) / 100.0
                return val
            except Exception:
                pass
        
        if suf.startswith('fast') and len(suf) > 4:
            try:
                val = float(suf[4:]) / 100.0
                return val
            except Exception:
                pass
        
        # Використати значення слайдера
        if 1 <= g_num <= len(speeds_flat):
            try:
                return float(speeds_flat[g_num - 1])
            except Exception:
                pass
        
        return 0.88


def prepare_config_models():
    """Повертає моделі конфігурації."""
    return {}


def initialize(app_context: Dict[str, Any]) -> DialogParser:
    """Ініціалізація Dialog Parser."""
    logger = app_context.get('logger', logging.getLogger("DialogParser"))
    logger.info("📝 Ініціалізація парсера діалогів...")
    
    parser = DialogParser(app_context)
    app_context['dialog_parser'] = parser
    
    logger.info("✅ Dialog Parser готовий")
    return parser


def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка Dialog Parser."""
    if 'dialog_parser' in app_context:
        del app_context['dialog_parser']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("Dialog Parser зупинено")
