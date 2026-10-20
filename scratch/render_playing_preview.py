import os
import sys
sys.path.insert(0, os.getcwd())
from PIL import Image, ImageDraw

from library import config
config.CONFIG_DATA["display"]["REVISION"] = "SIMU"
config.CONFIG_DATA["config"]["THEME"] = "LandscapeMediaSpotify"

from library.display import display
from library.media.media_screen import media_screen
from library.media.media_provider import media_provider

# Mock playing media
cover = Image.new('RGB', (300, 300), color=(50, 10, 80))
cdraw = ImageDraw.Draw(cover)
cdraw.rectangle([(20, 20), (280, 280)], fill=(120, 30, 140))
cdraw.text((60, 130), "ALBUM COVER", fill=(255, 255, 255))

mock_info = {
    "status": "PLAYING",
    "title": "Starboy (feat. Daft Punk)",
    "artist": "The Weeknd, Daft Punk",
    "album": "Starboy",
    "position": 75.0,
    "duration": 230.0,
    "thumbnail": cover,
    "app_name": "Spotify"
}
media_provider.get_info = lambda: mock_info

display.initialize_display()
media_screen.display_static_elements()
media_screen.render(force_redraw=True)

# Copy screencap to playing preview
import shutil
shutil.copy("screencap.png", "C:/Users/Piero/.gemini/antigravity/brain/b8e2474c-80d3-41e4-bfbc-d88028fd84f1/media_screen_playing.png")
print("Playing preview generated successfully!")
