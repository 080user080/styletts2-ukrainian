import os
import yt_dlp

class YouTubeDownloader:
    def __init__(self):
        self.base_output_dir = './output'

    def _extract_video_info(self, url: str):
        options = {'quiet': True}
        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        return "".join(c for c in name if c.isalnum() or c in " _-").rstrip()

    def _run_ydl(self, options: dict, url: str):
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

    def download(self, url: str) -> str:
        video_info = self._extract_video_info(url)
        title = self._sanitize_filename(video_info['title'])
        output_dir = os.path.join(self.base_output_dir, title)
        os.makedirs(output_dir, exist_ok=True)

        self._download_video(url, output_dir)
        self._download_english_auto_subtitles(url, output_dir)
        self._download_audio_only(url, output_dir)

        print(f"✅ Завантажено: {output_dir}")

        return output_dir

    def _download_video(self, url: str, output_dir: str):
        options = {
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(output_dir, 'video.%(ext)s'),
        }
        self._run_ydl(options, url)

    def _download_english_auto_subtitles(self, url: str, output_dir: str):
        options = {
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'skip_download': True,
            'subtitlesformat': 'text',
            'outtmpl': os.path.join(output_dir, 'sub.%(ext)s'),
        }
        self._run_ydl(options, url)

    def _download_audio_only(self, url: str, output_dir: str):
        options = {
            'format': 'bestaudio',
            'outtmpl': os.path.join(output_dir, 'voice.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            'quiet': True,
        }
        self._run_ydl(options, url)