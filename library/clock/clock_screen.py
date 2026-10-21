# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/

import datetime
import locale
import os
import platform
from typing import Optional, Tuple
import babel.dates

from library import config
from library.display import display
from library.log import logger


def _get_theme_file_path(filename: Optional[str]) -> Optional[str]:
    if not filename or not config.CLOCK_THEME_DATA:
        return None
    return os.path.join(config.CLOCK_THEME_DATA.get("PATH", ""), filename)


def _clamp_coord(x: int, y: int, w: int = 0, h: int = 0) -> Tuple[int, int, int, int]:
    disp_w = display.lcd.get_width()
    disp_h = display.lcd.get_height()
    cx = max(0, min(x, disp_w - 1))
    cy = max(0, min(y, disp_h - 1))
    cw = max(1, min(w, disp_w - cx)) if w > 0 else 0
    ch = max(1, min(h, disp_h - cy)) if h > 0 else 0
    return cx, cy, cw, ch


def _get_locale():
    try:
        if platform.system() == "Windows":
            lc = locale.getdefaultlocale()[0]
        else:
            lc = babel.dates.LC_TIME
    except:
        lc = None
    return lc or "it_IT"


class ClockScreen:
    """
    Handles drawing and refreshing the Digital Clock screen
    based on the clock theme YAML layout.
    """

    def __init__(self):
        self._last_time_str = None
        self._last_date_str = None
        self._frame_counter = 0
        self._current_phase = None
        self._current_bg_name = "background.png"

    def reset_cache(self):
        self._last_time_str = None
        self._last_date_str = None
        self._frame_counter = 0
        self._current_phase = None
        self._current_bg_name = "background.png"

    def get_current_phase(self) -> Tuple[str, str, Tuple[int, int, int]]:
        day_phases = config.CLOCK_THEME_DATA.get("day_phases", {})
        if not day_phases or not day_phases.get("ENABLED", False):
            return "default", "background.png", (255, 90, 0)

        now_hour = datetime.datetime.now().hour
        theme_path = config.CLOCK_THEME_DATA.get("PATH", "")

        matched_phase = None
        matched_cfg = {}
        # Iterate over configured phases in day_phases to check START_HOUR and END_HOUR
        for p_name, p_cfg in day_phases.items():
            if not isinstance(p_cfg, dict):
                continue
            s_hour = p_cfg.get("START_HOUR")
            e_hour = p_cfg.get("END_HOUR")
            if s_hour is not None and e_hour is not None:
                if s_hour < e_hour:
                    if s_hour <= now_hour < e_hour:
                        matched_phase = p_name
                        matched_cfg = p_cfg
                        break
                else:  # Overnight span (e.g. 22 to 6)
                    if now_hour >= s_hour or now_hour < e_hour:
                        matched_phase = p_name
                        matched_cfg = p_cfg
                        break

        # Fallback to standard defaults if not matched via custom hours
        if not matched_phase:
            if 6 <= now_hour < 9:
                matched_phase = "ALBA"
            elif 9 <= now_hour < 16:
                matched_phase = "GIORNO"
            elif 16 <= now_hour < 19:
                matched_phase = "POMERIGGIO"
            elif 19 <= now_hour < 22:
                matched_phase = "SERA"
            else:
                matched_phase = "NOTTE"
            matched_cfg = day_phases.get(matched_phase, {})

        default_images = {
            "ALBA": "bg_alba.png",
            "GIORNO": "bg_giorno.png",
            "POMERIGGIO": "bg_pomeriggio.png",
            "SERA": "bg_sera.png",
            "NOTTE": "bg_notte.png"
        }
        default_leds = {
            "ALBA": (255, 140, 90),
            "GIORNO": (255, 210, 110),
            "POMERIGGIO": (255, 120, 20),
            "SERA": (255, 80, 0),
            "NOTTE": (50, 100, 240)
        }

        bg_name = matched_cfg.get("IMAGE", default_images.get(matched_phase, "background.png"))
        led_color = matched_cfg.get("RGB_LED", default_leds.get(matched_phase, (255, 90, 0)))
        if isinstance(led_color, str):
            try:
                led_color = tuple(int(x.strip()) for x in led_color.split(','))
            except:
                led_color = default_leds.get(matched_phase, (255, 90, 0))

        if os.path.exists(os.path.join(theme_path, bg_name)):
            return matched_phase, bg_name, led_color
        return matched_phase, "background.png", led_color

    def display_static_elements(self):
        if not config.CLOCK_THEME_DATA:
            return

        # Ensure correct orientation for clock theme
        from library.display import get_theme_orientation
        clock_orient = get_theme_orientation(config.CLOCK_THEME_DATA)
        display.lcd.SetOrientation(clock_orient)

        theme_path = config.CLOCK_THEME_DATA.get("PATH", "")

        phase, bg_name, led_color = self.get_current_phase()
        self._current_phase = phase
        self._current_bg_name = bg_name

        try:
            display.lcd.SetBackplateLedColor(led_color)
        except Exception:
            pass

        # 1. Static images (Background, etc.)
        static_images = config.CLOCK_THEME_DATA.get("static_images", {})
        for name, img_data in static_images.items():
            if name.upper() == "BACKGROUND":
                img_path = os.path.join(theme_path, bg_name)
            else:
                img_path = os.path.join(theme_path, img_data.get("PATH", "background.png"))
            x, y, w, h = _clamp_coord(
                img_data.get("X", 0),
                img_data.get("Y", 0),
                img_data.get("WIDTH", 0),
                img_data.get("HEIGHT", 0),
            )
            logger.debug(f"ClockScreen: Drawing static image '{name}' from {img_path}")
            display.lcd.DisplayBitmap(
                bitmap_path=img_path,
                x=x,
                y=y,
                width=w,
                height=h,
            )

        # 2. Static text
        static_text = config.CLOCK_THEME_DATA.get("static_text", {})
        for name, txt_data in static_text.items():
            bg_img = _get_theme_file_path(txt_data.get("BACKGROUND_IMAGE", None))
            x, y, w, h = _clamp_coord(
                txt_data.get("X", 0),
                txt_data.get("Y", 0),
                txt_data.get("WIDTH", 0),
                txt_data.get("HEIGHT", 0),
            )
            display.lcd.DisplayText(
                text=txt_data.get("TEXT", ""),
                x=x,
                y=y,
                width=w,
                height=h,
                font=config.FONTS_DIR + txt_data.get("FONT", "roboto/Roboto-Bold.ttf"),
                font_size=txt_data.get("FONT_SIZE", 16),
                font_color=txt_data.get("FONT_COLOR", (255, 200, 100)),
                background_color=txt_data.get("BACKGROUND_COLOR", (0, 0, 0)),
                background_image=bg_img,
                align=txt_data.get("ALIGN", "left"),
                anchor=txt_data.get("ANCHOR", "lt"),
            )

    def render(self, force_redraw: bool = False):
        if not config.CLOCK_THEME_DATA:
            return

        if force_redraw:
            self.reset_cache()

        phase, bg_name, led_color = self.get_current_phase()
        if phase != self._current_phase:
            logger.info(f"ClockScreen: Day phase changed to {phase} ({bg_name})")
            self._current_phase = phase
            self._current_bg_name = bg_name
            self.display_static_elements()
            force_redraw = True

        theme_path = config.CLOCK_THEME_DATA.get("PATH", "")
        bg_full_path = os.path.join(theme_path, self._current_bg_name or "background.png")
        layout = config.CLOCK_THEME_DATA.get("clock_layout", {})
        now = datetime.datetime.now()

        # 1. Digital Time
        time_cfg = layout.get("TIME", {})
        if time_cfg.get("SHOW", True):
            show_seconds = time_cfg.get("SHOW_SECONDS", True)
            time_str = now.strftime("%H:%M:%S" if show_seconds else "%H:%M")

            if time_str != self._last_time_str or force_redraw:
                self._last_time_str = time_str
                tx, ty, tw, th = _clamp_coord(
                    time_cfg.get("X", 350),
                    time_cfg.get("Y", 25),
                    time_cfg.get("WIDTH", 0),
                    time_cfg.get("HEIGHT", 0),
                )
                display.lcd.DisplayText(
                    text=time_str,
                    x=tx,
                    y=ty,
                    width=tw,
                    height=th,
                    font=config.FONTS_DIR + time_cfg.get("FONT", "digital/DIGITAL-7.TTF"),
                    font_size=time_cfg.get("FONT_SIZE", 62),
                    font_color=time_cfg.get("FONT_COLOR", (255, 245, 220)),
                    background_color=time_cfg.get("BACKGROUND_COLOR", (0, 0, 0)),
                    background_image=bg_full_path,
                    align=time_cfg.get("ALIGN", "center"),
                    anchor=time_cfg.get("ANCHOR", "ma"),
                )

        # 2. Date
        date_cfg = layout.get("DATE", {})
        if date_cfg.get("SHOW", True):
            lc = _get_locale()
            try:
                date_str = babel.dates.format_date(now, format='full', locale=lc).capitalize()
            except:
                date_str = now.strftime("%A, %d %B %Y").capitalize()

            if date_str != self._last_date_str or force_redraw:
                self._last_date_str = date_str
                dx, dy, dw, dh = _clamp_coord(
                    date_cfg.get("X", 350),
                    date_cfg.get("Y", 96),
                    date_cfg.get("WIDTH", 0),
                    date_cfg.get("HEIGHT", 0),
                )
                display.lcd.DisplayText(
                    text=date_str,
                    x=dx,
                    y=dy,
                    width=dw,
                    height=dh,
                    font=config.FONTS_DIR + date_cfg.get("FONT", "roboto/Roboto-Bold.ttf"),
                    font_size=date_cfg.get("FONT_SIZE", 15),
                    font_color=date_cfg.get("FONT_COLOR", (255, 235, 190)),
                    background_color=date_cfg.get("BACKGROUND_COLOR", (0, 0, 0)),
                    background_image=bg_full_path,
                    align=date_cfg.get("ALIGN", "center"),
                    anchor=date_cfg.get("ANCHOR", "ma"),
                )

        # 3. Animated Flame on Charizard's Tail (optional)
        flame_cfg = layout.get("FLAME_ANIMATION", {})
        if flame_cfg.get("SHOW", False):
            frames_dir = flame_cfg.get("FRAMES_DIR", "flame")
            num_frames = flame_cfg.get("NUM_FRAMES", 4)
            if num_frames > 0:
                frame_idx = self._frame_counter % num_frames
                self._frame_counter += 1
                frame_path = os.path.join(config.CLOCK_THEME_DATA.get("PATH", ""), frames_dir, f"flame_{frame_idx}.png")
                if os.path.exists(frame_path):
                    fx, fy, fw, fh = _clamp_coord(
                        flame_cfg.get("X", 26),
                        flame_cfg.get("Y", 145),
                        flame_cfg.get("WIDTH", 40),
                        flame_cfg.get("HEIGHT", 48),
                    )
                    display.lcd.DisplayBitmap(
                        bitmap_path=frame_path,
                        x=fx,
                        y=fy,
                        width=fw,
                        height=fh,
                    )


clock_screen = ClockScreen()
