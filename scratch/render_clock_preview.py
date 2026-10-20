import os, sys
sys.path.insert(0, os.getcwd())
import shutil

from library import config
config.CONFIG_DATA["display"]["REVISION"] = "SIMU"
config.CONFIG_DATA["config"]["THEME"] = "LandscapeCharizardClock"

from library.display import display
from library.clock.clock_screen import clock_screen

display.initialize_display()
clock_screen.display_static_elements()
clock_screen.render(force_redraw=True)

# Copy screencap to preview
target_preview = "C:/Users/Piero/.gemini/antigravity/brain/b8e2474c-80d3-41e4-bfbc-d88028fd84f1/charizard_clock_preview.png"
shutil.copy("screencap.png", target_preview)
print(f"Charizard clock preview saved to {target_preview} successfully!")
