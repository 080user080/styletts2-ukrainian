import os
import pathlib
from tqdm import tqdm
from services.google_translator import GoogleTranslator
from text_utils import split_to_chunks

CHUNK_SIZE = 4_000

class BookTranslator:
    def __init__(
        self,
        input_dir: str,
        google_translator: GoogleTranslator,
    ):
        self.google_translator = google_translator
        self.input_dir = input_dir

    def process(self, book_name: str, source_lang: str = 'en', target_lang: str = 'uk'):
        book_path = os.path.join(self.input_dir, f'{book_name}.txt')
        if not os.path.exists(book_path):
            raise FileNotFoundError(f"Файл відсутній: {book_path}")

        translated_path = pathlib.Path(self.input_dir) / f'{book_name}.ukr.txt'
        if os.path.exists(translated_path):
            raise FileExistsError(f"Перекладений файл вже існує: {translated_path}")

        print(f'Завантажено файл {book_path}')
        with open(book_path, 'r', encoding='utf-8') as file:
            text = file.read().strip()

        chunks = split_to_chunks(text, CHUNK_SIZE)
        print(f"Total chunks: {len(chunks)} (≈{len(text):,} characters)")

        with translated_path.open("w", encoding="utf-8") as out_file:
            for chunk in tqdm(chunks, desc="Translating", unit="chunk"):
                translated = self.google_translator.translate(chunk, source_lang, target_lang)
                out_file.write(translated + "\n")
                out_file.flush()
        print(f"Done! Saved ► {translated_path}")
