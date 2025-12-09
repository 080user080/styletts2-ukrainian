import os
from tqdm import tqdm
from text_utils import split_to_chunks
from contracts.tts_service import TTSServiceInterface
from services.ukrainian_verbalizer import UkrainianVerbalizer

class TTSBookService:
    def __init__(self, input_dir: str, output_dir: str, tts: TTSServiceInterface, verbalizer: UkrainianVerbalizer | None = None):
        self.verbalizer = verbalizer
        self.tts = tts
        self.input_dir = input_dir
        self.output_dir = output_dir

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.input_dir, exist_ok=True)

    def process(self, book_name: str, replace: bool):
        book_path = os.path.join(self.input_dir, f'{book_name}.txt')
        if not os.path.exists(book_path):
            raise FileNotFoundError(f"Файл відсутній: {book_path}")

        output_path = os.path.join(self.output_dir, book_name)
        os.makedirs(output_path, exist_ok=True)
        
        chunks_path = os.path.join(output_path, 'chunks')
        os.makedirs(chunks_path, exist_ok=True)

        verbalize_path = os.path.join(output_path, 'verbalize')
        os.makedirs(verbalize_path, exist_ok=True)

        print(f'Завантажено файл {book_path}')
        with open(book_path, 'r', encoding='utf-8') as file:
            text = file.read().strip()

        chunks = split_to_chunks(text, 47 * 1024)
        print(f'Розбито на {len(chunks)} частини.')

        for index, chunk in tqdm(enumerate(chunks, start=1), total=len(chunks), desc="Обробка частин", unit="частина"):
            print(f'=== Частина {index} ===')

            chunk_file_path = os.path.join(chunks_path, f'chunk-{index}.txt')
            with open(chunk_file_path, "w", encoding="utf-8") as f:
                f.write(chunk)

            output_file_path = os.path.join(output_path, f'{index}.mp3')

            if os.path.exists(output_file_path) and not replace:
                print(f'Файл існує: {output_file_path}')
                continue

            if self.verbalizer:
                chunk = self.verbalizer.verbalize(chunk)
                verbalize_file_path = os.path.join(verbalize_path, f'verbalize-{index}.txt')
                with open(verbalize_file_path, "w", encoding="utf-8") as f:
                    f.write(chunk)

            if os.path.exists(output_file_path) and replace:
                os.remove(output_file_path)

            self.tts.synthesize_to_file(chunk, output_file_path)
