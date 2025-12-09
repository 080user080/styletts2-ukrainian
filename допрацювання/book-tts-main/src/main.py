from container import container
import typer
import os
from services.subtitle_parser import SubtitleParser
from commands.youtube import YoutobeCommand
from commands.server import ServerCommand
from services.tts_book import TTSBookService
from services.book_translator import BookTranslator

app = typer.Typer()

@app.command()
def greet(name: str):
    print(f"Hello, {name}!")

@app.command()
def test():
    loader: YoutobeCommand = container.youtobe_command()
    loader.synthesize('https://www.youtube.com/watch?v=YrRs4acFOv0')
    print('Success')

@app.command(name="tts-book")
def tts_book(book_name: str, replace: bool = typer.Option(False, "--replace", "-r")):
    print(f"Processing book: {book_name} with replace={replace}")
    service: TTSBookService = container.tts_book_service()
    service.process(book_name, replace)
    print(f"Book {book_name} processed successfully.")

@app.command(name="translate-book")
def translate_book(book_name: str):
    service: BookTranslator = container.book_translator()
    service.process(book_name)

if __name__ == "__main__":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./google-credentials.json"
    app()
