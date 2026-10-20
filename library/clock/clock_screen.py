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

    def reset_cache(self):
        self._last_time_str = None
        self._last_date_str = None

    def display_static_elements(self):
        if not config.CLOCK_THEME_DATA:
            return

        # Ensure correct orientation for clock theme
        from library.display import get_theme_orientation
        clock_orient = get_theme_orientation(config.CLOCK_THEME_DATA)
        display.lcd.SetOrientation(clock_orient)

        theme_path = config.CLOCK_THEME_DATA.get("PATH", "")

        # 1. Static images (Background, etc.)
        static_images = config.CLOCK_THEME_DATA.get("static_images", {})
        for name, img_data in static_images.items():
            img_path = os.path.join(theme_path, img_data.get("PATH", ""))
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
                    time_cfg.get("X", 240),
                    time_cfg.get("Y", 45),
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
                    font_size=time_cfg.get("FONT_SIZE", 64),
                    font_color=time_cfg.get("FONT_COLOR", (255, 235, 190)),
                    background_color=time_cfg.get("BACKGROUND_COLOR", (0, 0, 0)),
                    background_image=_get_theme_file_path(time_cfg.get("BACKGROUND_IMAGE", "background.png")),
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
                    date_cfg.get("X", 240),
                    date_cfg.get("Y", 125),
                    date_cfg.get("WIDTH", 0),
                    date_cfg.get("HEIGHT", 0),
                )
                display.lcd.DisplayText(
                    text=date_str,
                    x=dx,
                    y=dy,
                    width=dw,
                    height=dh,
                    font=config.FONTS_DIR + date_cfg.get("FONT", "roboto/Roboto-Medium.ttf"),
                    font_size=date_cfg.get("FONT_SIZE", 18),
                    font_color=date_cfg.get("FONT_COLOR", (255, 180, 80)),
                    background_color=date_cfg.get("BACKGROUND_COLOR", (0, 0, 0)),
                    background_image=_get_theme_file_path(date_cfg.get("BACKGROUND_IMAGE", "background.png")),
                    align=date_cfg.get("ALIGN", "center"),
                    anchor=date_cfg.get("ANCHOR", "ma"),
                )


clock_screen = ClockScreen()
