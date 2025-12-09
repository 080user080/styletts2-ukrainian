from dependency_injector import containers, providers
import yaml
from services.google_translator import GoogleTranslator
from services.ukrainian_verbalizer import UkrainianVerbalizer
from services.ukrainian_tts import UkrainianTTS
from services.youtube_downloader import YouTubeDownloader
from services.subtitle_parser import SubtitleParser
from commands.youtube import YoutobeCommand
from commands.server import ServerCommand
from services.tts_book import TTSBookService
from services.book_translator import BookTranslator

class AppContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    google_translator = providers.Factory(
        GoogleTranslator,
        project_id=config.google_translator.project_id,
        location=config.google_translator.location,
    )

    ukrainian_tts = providers.Factory(
        UkrainianTTS,
        prompt_audio=config.ukrainian_tts.prompt_audio,
    )

    verbalizer = providers.Singleton(UkrainianVerbalizer)

    tts_book_service = providers.Factory(
        TTSBookService,
        input_dir=config.shared.input_dir,
        output_dir=config.shared.output_dir,
        tts=ukrainian_tts,
        verbalizer=verbalizer
    )

    book_translator = providers.Factory(
        BookTranslator,
        input_dir=config.shared.input_dir,
        google_translator=google_translator,
    )

with open("./src/config.yml", "r", encoding="utf-8") as f:
    yaml_config = yaml.safe_load(f)

container = AppContainer()
container.config.from_dict(yaml_config)