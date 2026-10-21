import math
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

bg = Image.open(r"res\themes\LandscapeCharizardClock\background.png").convert("RGBA")
flame_box = (20, 115, 85, 195)
flame_crop = bg.crop(flame_box)

frames = []
num_frames = 6

# Create 6 subtle looping frames of flickering flame and rising sparks
for i in range(num_frames):
    t = (i / num_frames) * 2 * math.pi
    
    # 1. Flame flicker: scale slightly and adjust brightness
    scale_y = 1.0 + 0.08 * math.sin(t)
    scale_x = 1.0 + 0.05 * math.cos(t)
    
    fw, fh = flame_crop.size
    new_w = int(fw * scale_x)
    new_h = int(fh * scale_y)
    
    # Resize with smooth filter
    scaled_flame = flame_crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Brightness flicker (1.0 to 1.15)
    brightness = 1.0 + 0.12 * math.sin(t + 0.5)
    scaled_flame = ImageEnhance.Brightness(scaled_flame).enhance(brightness)
    
    # Composite back over background
    frame = bg.copy()
    
    # Align bottom of flame so it stays attached to tail
    paste_x = flame_box[0] - (new_w - fw) // 2
    paste_y = flame_box[3] - new_h
    
    frame.paste(scaled_flame, (paste_x, paste_y))
    
    frames.append(frame.convert("RGB"))

# Save as animated GIF
gif_path = r"C:\Users\Piero\.gemini\antigravity\brain\b8e2474c-80d3-41e4-bfbc-d88028fd84f1\charizard_animated.gif"
frames[0].save(
    gif_path,
    save_all=True,
    append_images=frames[1:],
    duration=150,  # 150ms per frame (~7 FPS)
    loop=0
)
print(f"Saved animated GIF to {gif_path}")
