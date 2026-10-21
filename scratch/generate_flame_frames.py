import math
import os
from PIL import Image, ImageEnhance

bg = Image.open(r"res\themes\LandscapeCharizardClock\background.png")
flame_box = (18, 110, 88, 195)
flame_crop = bg.crop(flame_box)

flame_dir = r"res\themes\LandscapeCharizardClock\flame"
os.makedirs(flame_dir, exist_ok=True)

num_frames = 4
fw, fh = flame_crop.size

for i in range(num_frames):
    t = (i / num_frames) * 2 * math.pi
    
    # Scale flame gently
    scale_y = 1.0 + 0.08 * math.sin(t)
    scale_x = 1.0 + 0.06 * math.cos(t)
    
    new_w = int(fw * scale_x)
    new_h = int(fh * scale_y)
    
    scaled = flame_crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Adjust brightness (flickering glow)
    bright = 1.0 + 0.15 * math.sin(t + 0.4)
    scaled = ImageEnhance.Brightness(scaled).enhance(bright)
    
    # Create canvas of flame_box size with background underneath
    canvas = flame_crop.copy()
    
    # Align at bottom-center
    px = (fw - new_w) // 2
    py = fh - new_h
    
    # Simple blend
    mask = Image.new("L", scaled.size, 220)
    canvas.paste(scaled, (px, py), mask)
    
    out_path = os.path.join(flame_dir, f"flame_{i}.png")
    canvas.save(out_path)
    print(f"Saved {out_path}")
