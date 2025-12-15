#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_chunker_gui.py

GUI-утиліта для розбиття тексту на логічні блоки і збереження в окремі файли.
Основні вимоги:
- Першочергове початкове розбиття по заголовках (англійська пріоритет).
- Далі розбиття блоків на частини ~max_chars по межах речень/пунктуації.
- Немає копіювання в буфер обміну.
- GUI для вибору вхідного файлу та папки виходу. Якщо папку не обрали,
  створюється timestamp-папка поруч з вхідним файлом.
- Створюється manifest.json і process.log.

Всі правки автора позначені коментарем #GPT
"""

# GPT: імпорти
import re
import sys
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
import threading
import traceback
import unicodedata
import logging

# GUI: tkinter (вбудований)
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, scrolledtext

# GPT: Сталі за замовчуванням
DEFAULT_MAX_CHARS = 10000
DEFAULT_OVERLAP = 0
INDEX_PADDING = 3  # кількість цифр у префіксі (000...)

# GPT: regex для заголовків (англ. пріоритет, потім рос./укр.)
HEADING_PATTERNS = [
    r'^\s*(Chapter|CHAPTER|Chapters|PART|Part|BOOK|Book|Section|SECTION)\b.*$',
    r'^\s*(Book|BOOK)\b.*$',
    r'^\s*(Глава|ГЛАВА|Розділ|РОЗДІЛ|Частина|ЧАСТИНА|Раздел|РАЗДЕЛ)\b.*$'
]
_HEADING_RE_LIST = [re.compile(p, flags=re.UNICODE) for p in HEADING_PATTERNS]

# GPT: regex для грубого розбиття на "речення/фрагменти"
_SIMPLE_SENTENCE_RE = re.compile(r'(.+?[.!?…](?:["\')\]]+)?)(?:\s+|$)', flags=re.DOTALL)

# GPT: regex для внутрішніх роздільників при довгому реченні
_INTERNAL_SEP_RE = re.compile(r'[.!?…;,:]\s+|\n+', flags=re.UNICODE)

# GPT: логування в файл буде налаштовано під час виконання

# GPT: допоміжні функції

def normalize_text(text: str) -> str:
    """Нормалізація тексту: приведення кінців рядків, видалення зайвих пробілів."""
    txt = text.replace('\r\n', '\n').replace('\r', '\n')
    # нормалізуємо unicode збіги (композиція)
    txt = unicodedata.normalize('NFC', txt)
    return txt.strip('\n') + '\n'


def is_heading_line(line: str, prioritize_english: bool = True) -> bool:
    """Перевірка чи є рядок заголовком. Пріоритет англійської опціональний."""
    line_stripped = line.strip()
    if not line_stripped:
        return False
    # Якщо пріоритет англійської - перевіряємо англ шаблони першими
    checks = _HEADING_RE_LIST if prioritize_english else list(reversed(_HEADING_RE_LIST))
    for rx in checks:
        if rx.match(line_stripped):
            return True
    return False


def split_by_headings(text: str, prioritize_english: bool = True):
    """
    Повертає список блоків у вигляді кортежів (title, block_text).
    Якщо перед першим заголовком є фронтматеріал - він повертається першим блоком з title = filename-approx.
    """
    lines = text.split('\n')
    blocks = []
    current_lines = []
    current_title = None

    for i, line in enumerate(lines):
        if is_heading_line(line, prioritize_english=prioritize_english):
            # якщо вже є поточний блок - закриваємо
            if current_title is not None or current_lines:
                blocks.append((current_title if current_title else 'FrontMatter', '\n'.join(current_lines).strip()+"\n"))
            # починаємо новий блок
            current_title = line.strip()
            current_lines = [line]
        else:
            # додаємо до поточного блоку
            current_lines.append(line)
    # після завершення
    if current_lines:
        blocks.append((current_title if current_title else 'FrontMatter', '\n'.join(current_lines).strip()+"\n"))
    return blocks


def break_long_fragment(fragment: str, max_chars: int):
    """Розбиває дуже довгий "речення" на частини <= max_chars, намагаючись використовувати внутрішні сепаратори."""
    parts = []
    # знаходимо індекси роздільників
    idxs = [0]
    for m in _INTERNAL_SEP_RE.finditer(fragment):
        idxs.append(m.end())
    idxs.append(len(fragment))

    temp_parts = []
    for i in range(len(idxs) - 1):
        piece = fragment[idxs[i]:idxs[i+1]].strip()
        if not piece:
            continue
        if not temp_parts or len(temp_parts[-1]) + 1 + len(piece) <= max_chars:
            if temp_parts:
                temp_parts[-1] = (temp_parts[-1] + ' ' + piece).strip()
            else:
                temp_parts.append(piece)
        else:
            if len(piece) > max_chars:
                # грубий поділ по max_chars
                for j in range(0, len(piece), max_chars):
                    temp_parts.append(piece[j:j+max_chars].strip())
            else:
                temp_parts.append(piece)
    # фаребек: якщо будь-який залишився більший за max_chars
    final = []
    for p in temp_parts:
        if len(p) <= max_chars:
            final.append(p)
        else:
            for j in range(0, len(p), max_chars):
                final.append(p[j:j+max_chars].strip())
    return final


def split_text_into_chunks(text: str, max_chars: int = DEFAULT_MAX_CHARS, overlap: int = DEFAULT_OVERLAP):
    """Розбиття тексту на чанки по ~max_chars з урахуванням речень.
    Повертає список рядків (чанків).
    """
    text = text.strip()
    if not text:
        return []

    sentences = [m.group(1).strip() for m in _SIMPLE_SENTENCE_RE.finditer(text)]
    if not sentences:
        sentences = [text]

    chunks = []
    cur = ''
    for s in sentences:
        if not s:
            continue
        if len(cur) + 1 + len(s) <= max_chars:
            cur = (cur + '\n' + s).strip() if cur else s
        else:
            if cur:
                chunks.append(cur)
            if len(s) > max_chars:
                parts = break_long_fragment(s, max_chars)
                for p in parts[:-1]:
                    chunks.append(p)
                cur = parts[-1]
            else:
                cur = s
    if cur:
        chunks.append(cur)

    # overlap реалізуємо як просте копіювання останніх N символів у початок наступного
    if overlap > 0 and len(chunks) > 1:
        overlapped = []
        for i, c in enumerate(chunks):
            if i == 0:
                overlapped.append(c)
            else:
                prev = overlapped[-1]
                add = prev[-overlap:] if len(prev) >= overlap else prev
                newc = (add + '\n' + c).strip()
                overlapped.append(newc)
        chunks = overlapped

    return chunks


def sha1_text(text: str) -> str:
    h = hashlib.sha1()
    h.update(text.encode('utf-8'))
    return h.hexdigest()


def sanitize_filename(name: str, maxlen: int = 200) -> str:
    """Очищає ім'я файлу від небезпечних символів та обмежує довжину."""
    # замінюємо небажані символи на підкреслення
    safe = re.sub(r'[\\/:*?"<>|]', '_', name)
    safe = re.sub(r'\s+', ' ', safe).strip()
    if len(safe) > maxlen:
        safe = safe[:maxlen].rsplit(' ', 1)[0]
    return safe


# GPT: основна логіка формування файлів

def process_file_save_blocks(input_path: Path, output_folder: Path, max_chars: int, overlap: int, prioritize_english: bool, logger=None):
    """Читає файл, розбиває по заголовках, потім по чанках, зберігає файли і manifest.json."""
    if logger is None:
        logger = logging.getLogger('text_chunker')

    logger.info(f'Читання файлу: {input_path}')
    raw = input_path.read_text(encoding='utf-8', errors='replace')
    text = normalize_text(raw)

    blocks = split_by_headings(text, prioritize_english=prioritize_english)
    logger.info(f'Знайдено {len(blocks)} блоків після початкового розбиття')

    manifest = []
    file_index = 0

    for b_idx, (title, block_text) in enumerate(blocks):
        # сформувати назву блоку
        if title and title != 'FrontMatter':
            block_title = title
        else:
            # спробуємо витягнути перші корисні рядки для назви
            preview = '\n'.join(block_text.split('\n')[:3]).strip()
            block_title = preview if preview else input_path.stem

        # для кожного блоку розбиваємо на чанки
        if len(block_text) <= max_chars:
            chunks = [block_text]
        else:
            chunks = split_text_into_chunks(block_text, max_chars=max_chars, overlap=overlap)

        for part_in_block, chunk in enumerate(chunks):
            prefix = str(file_index).zfill(INDEX_PADDING)
            # ім'я файлу: префікс + очищена назва
            name_part = sanitize_filename(block_title)
            filename = f"{prefix} {name_part}.txt"
            file_path = output_folder / filename

            # додаємо заголовок блоку на початок, якщо це перша частина блоку
            content = chunk
            if part_in_block == 0 and title and title != 'FrontMatter':
                content = title + '\n\n' + chunk

            file_path.write_text(content, encoding='utf-8')

            record = {
                'index': file_index,
                'filename': filename,
                'block_title': block_title,
                'part_in_block': part_in_block,
                'chars': len(content),
                'sha1': sha1_text(content),
                'original_file': str(input_path.name),
                'created_at': datetime.utcnow().isoformat() + 'Z'
            }
            manifest.append(record)
            logger.info(f'Записано файл {filename} ({record["chars"]} chars)')
            file_index += 1

    # зберігаємо manifest.json
    manifest_path = output_folder / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    # process.log уже веде logger у файл; додаткові дані можемо записати
    logger.info(f'Обробка завершена. Створено {file_index} файл(ів). Manifest: {manifest_path.name}')
    return manifest


# GPT: GUI клас
class TextChunkerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Text Chunker')
        self.geometry('800x520')

        # налаштування логера
        self.logger = logging.getLogger('text_chunker')
        self.logger.setLevel(logging.INFO)

        # текст логування у файл буде створений при старті процесу
        self.log_handler = None

        # змінні UI
        self.input_path_var = tk.StringVar()
        self.output_folder_var = tk.StringVar()
        self.max_chars_var = tk.IntVar(value=DEFAULT_MAX_CHARS)
        self.overlap_var = tk.IntVar(value=DEFAULT_OVERLAP)
        self.prioritize_eng_var = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        # Вибір файлу
        row = 0
        ttk.Label(frm, text='Вхідний файл:').grid(column=0, row=row, sticky=tk.W)
        inp_entry = ttk.Entry(frm, textvariable=self.input_path_var, width=80)
        inp_entry.grid(column=1, row=row, sticky=tk.W)
        ttk.Button(frm, text='Вибрати...', command=self.choose_input_file).grid(column=2, row=row, padx=6)

        # Вибір папки виходу
        row += 1
        ttk.Label(frm, text='Папка виходу (необов\u2014язково):').grid(column=0, row=row, sticky=tk.W)
        out_entry = ttk.Entry(frm, textvariable=self.output_folder_var, width=80)
        out_entry.grid(column=1, row=row, sticky=tk.W)
        ttk.Button(frm, text='Вибрати...', command=self.choose_output_folder).grid(column=2, row=row, padx=6)

        # Параметри
        row += 1
        ttk.Label(frm, text='Max chars:').grid(column=0, row=row, sticky=tk.W)
        ttk.Entry(frm, textvariable=self.max_chars_var, width=10).grid(column=1, row=row, sticky=tk.W)
        ttk.Label(frm, text='Overlap chars:').grid(column=1, row=row, sticky=tk.E, padx=(120,0))
        ttk.Entry(frm, textvariable=self.overlap_var, width=10).grid(column=1, row=row, sticky=tk.E, padx=(0,40))

        row += 1
        ttk.Checkbutton(frm, text='Prioritize English headings', variable=self.prioritize_eng_var).grid(column=0, row=row, sticky=tk.W)

        # Кнопки запуску
        row += 1
        ttk.Button(frm, text='Start', command=self.on_start).grid(column=0, row=row, pady=10)
        ttk.Button(frm, text='Exit', command=self.destroy).grid(column=1, row=row, pady=10, sticky=tk.W)

        # Progress / Log
        row += 1
        ttk.Label(frm, text='Log:').grid(column=0, row=row, sticky=tk.W)
        self.log_text = scrolledtext.ScrolledText(frm, height=18)
        self.log_text.grid(column=0, row=row+1, columnspan=3, sticky=tk.NSEW)

        # configure grid weights
        frm.rowconfigure(row+1, weight=1)
        frm.columnconfigure(1, weight=1)

    def choose_input_file(self):
        p = filedialog.askopenfilename(filetypes=[('Text files', '*.txt;*.md;*.rtf'), ('All files', '*.*')])
        if p:
            self.input_path_var.set(p)

    def choose_output_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.output_folder_var.set(p)

    def log(self, message: str):
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.see(tk.END)

    def setup_file_logger(self, log_path: Path):
        # налаштування file handler
        if self.log_handler:
            self.logger.removeHandler(self.log_handler)
            self.log_handler.close()
        fh = logging.FileHandler(str(log_path), encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.log_handler = fh

    def on_start(self):
        input_path = self.input_path_var.get().strip()
        if not input_path:
            messagebox.showerror('Error', 'Оберіть вхідний файл')
            return
        input_path = Path(input_path)
        if not input_path.exists():
            messagebox.showerror('Error', 'Вхідний файл не знайдено')
            return

        # визначення папки виходу
        out_folder = self.output_folder_var.get().strip()
        if out_folder:
            out_folder = Path(out_folder)
            out_folder.mkdir(parents=True, exist_ok=True)
        else:
            # створити папку поруч з файлом з timestamp
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out_folder = input_path.parent / f'{ts}'
            out_folder.mkdir(parents=True, exist_ok=True)

        # створюємо лог-файл у папці виходу
        log_path = out_folder / 'process.log'
        self.setup_file_logger(log_path)

        # читаємо параметри
        try:
            max_chars = int(self.max_chars_var.get())
        except Exception:
            max_chars = DEFAULT_MAX_CHARS
        try:
            overlap = int(self.overlap_var.get())
        except Exception:
            overlap = DEFAULT_OVERLAP
        prioritize_english = bool(self.prioritize_eng_var.get())

        # запускаємо в окремому потоці
        t = threading.Thread(target=self._run_processing, args=(input_path, out_folder, max_chars, overlap, prioritize_english))
        t.daemon = True
        t.start()

    def _run_processing(self, input_path: Path, out_folder: Path, max_chars: int, overlap: int, prioritize_english: bool):
        try:
            self.log(f'Start processing {input_path} -> {out_folder}')
            self.logger.info(f'Start processing {input_path} -> {out_folder}')

            manifest = process_file_save_blocks(input_path, out_folder, max_chars=max_chars, overlap=overlap, prioritize_english=prioritize_english, logger=self.logger)

            self.log('Processing finished.')
            self.log(f'Created {len(manifest)} files. Manifest saved.')
            self.logger.info('Processing finished successfully')

            # відкриваємо папку
            if messagebox.askyesno('Done', 'Обробка завершена. Відкрити папку з файлами?'):
                try:
                    os.startfile(str(out_folder))
                except Exception:
                    pass
        except Exception as e:
            tb = traceback.format_exc()
            self.logger.error('Error during processing:\n' + tb)
            self.log('ERROR: ' + str(e))
            messagebox.showerror('Processing error', str(e))


# GPT: точка входу
def main():
    app = TextChunkerGUI()
    app.mainloop()


if __name__ == '__main__':
    main()
