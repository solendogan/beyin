from brainpack.downloader import detect_source_type, list_youtube_episodes, download_audio
import tempfile, os

url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
print('Source type:', detect_source_type(url))
episodes = list_youtube_episodes(url, limit=1)
print('Episodes found:', episodes)
from pathlib import Path
out_dir = Path(tempfile.mkdtemp())
result = download_audio(episodes[0]["url"], out_dir)
print('Downloaded to:', result)
if result:
    print('File exists:', os.path.exists(result))
    print('File size:', os.path.getsize(result), 'bytes')
else:
    print('Download failed')
