# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/

import os
from typing import Optional, Tuple
from PIL import Image

from library import config
from library.display import display
from library.log import logger
from library.media.media_provider import media_provider, format_seconds


def _truncate_text(text: str, max_length: int) -> str:
    if not text:
        return ""
    if max_length > 0 and len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text


def _get_theme_file_path(filename: Optional[str]) -> Optional[str]:
    if not filename or not config.MEDIA_THEME_DATA:
        return None
    return os.path.join(config.MEDIA_THEME_DATA.get("PATH", ""), filename)


def _clamp_coord(x: int, y: int, w: int = 0, h: int = 0) -> Tuple[int, int, int, int]:
    disp_w = display.lcd.get_width()
    disp_h = display.lcd.get_height()
    cx = max(0, min(x, disp_w - 1))
    cy = max(0, min(y, disp_h - 1))
    cw = max(1, min(w, disp_w - cx)) if w > 0 else 0
    ch = max(1, min(h, disp_h - cy)) if h > 0 else 0
    return cx, cy, cw, ch


class MediaScreen:
    """
    Handles drawing and refreshing the Spotify / Media screen
    based on the media theme YAML layout.
    """

    def __init__(self):
        self._last_title = None
        self._last_artist = None
        self._last_album = None
        self._last_status = None
        self._last_progress_val = None
        self._last_pos_str = None
        self._last_dur_str = None
        self._last_thumb_id = None

    def reset_cache(self):
        """Force complete redraw on the next render call."""
        self._last_title = None
        self._last_artist = None
        self._last_album = None
        self._last_status = None
        self._last_progress_val = None
        self._last_pos_str = None
        self._last_dur_str = None
        self._last_thumb_id = None

    def display_static_elements(self):
        """Draws background and static elements defined in the media theme."""
        if not config.MEDIA_THEME_DATA:
            return

        # Ensure correct orientation for media theme
        from library.display import get_theme_orientation
        media_orient = get_theme_orientation(config.MEDIA_THEME_DATA)
        display.lcd.SetOrientation(media_orient)

        theme_path = config.MEDIA_THEME_DATA.get("PATH", "")

        # 1. Static images (Background, Spotify Logo, etc.)
        static_images = config.MEDIA_THEME_DATA.get("static_images", {})
        for name, img_data in static_images.items():
            img_path = os.path.join(theme_path, img_data.get("PATH", ""))
            x, y, w, h = _clamp_coord(
                img_data.get("X", 0),
                img_data.get("Y", 0),
                img_data.get("WIDTH", 0),
                img_data.get("HEIGHT", 0),
            )
            logger.debug(f"MediaScreen: Drawing static image '{name}' from {img_path}")
            display.lcd.DisplayBitmap(
                bitmap_path=img_path,
                x=x,
                y=y,
                width=w,
                height=h,
            )

        # 2. Static text (Headers, labels, etc.)
        static_text = config.MEDIA_THEME_DATA.get("static_text", {})
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
                font_color=txt_data.get("FONT_COLOR", (30, 215, 96)),
                background_color=txt_data.get("BACKGROUND_COLOR", (18, 18, 18)),
                background_image=bg_img,
                align=txt_data.get("ALIGN", "left"),
                anchor=txt_data.get("ANCHOR", "lt"),
            )

    def render(self, force_redraw: bool = False):
        """
        Refreshes dynamic media elements (track, artist, album art, progress bar).
        Only pushes updates to the LCD when values have changed.
        """
        if not config.MEDIA_THEME_DATA:
            return

        if force_redraw:
            self.reset_cache()

        layout = config.MEDIA_THEME_DATA.get("media_layout", {})
        info = media_provider.get_info()

        status = info.get("status", "STOPPED")
        title = info.get("title", "")
        artist = info.get("artist", "")
        album = info.get("album", "")
        position = info.get("position", 0.0)
        duration = info.get("duration", 0.0)
        thumbnail = info.get("thumbnail", None)

        # Idle text fallback if nothing is playing
        if not title:
            title = "In attesa di musica..." if status == "STOPPED" else "Spotify"
            artist = "Avvia un brano su Spotify"
            album = ""
            status_text = "In attesa"
        else:
            if status == "PLAYING":
                status_text = "In riproduzione"
            elif status == "PAUSED":
                status_text = "In pausa"
            else:
                status_text = "Fermato"

        # 1. Cover Art / Thumbnail
        cover_cfg = layout.get("COVER_ART", {})
        if cover_cfg.get("SHOW", True):
            thumb_id = id(thumbnail) if thumbnail else "DEFAULT"
            if thumb_id != self._last_thumb_id or force_redraw:
                self._last_thumb_id = thumb_id
                cx, cy, cw, ch = _clamp_coord(
                    cover_cfg.get("X", 25),
                    cover_cfg.get("Y", 65),
                    cover_cfg.get("WIDTH", 180),
                    cover_cfg.get("HEIGHT", 180),
                )

                if thumbnail:
                    img_to_draw = thumbnail.resize((cw, ch), Image.Resampling.LANCZOS)
                    display.lcd.DisplayPILImage(img_to_draw, cx, cy, cw, ch)
                else:
                    def_cover_path = _get_theme_file_path(cover_cfg.get("DEFAULT_IMAGE", "default_cover.png"))
                    if def_cover_path and os.path.exists(def_cover_path):
                        display.lcd.DisplayBitmap(def_cover_path, cx, cy, cw, ch)

        # 2. Track Title
        title_cfg = layout.get("TITLE", {})
        if title_cfg.get("SHOW", True):
            display_title = _truncate_text(title, title_cfg.get("MAX_LENGTH", 25))
            if display_title != self._last_title or force_redraw:
                self._last_title = display_title
                tx, ty, tw, th = _clamp_coord(
                    title_cfg.get("X", 225),
                    title_cfg.get("Y", 70),
                    title_cfg.get("WIDTH", 245),
                    title_cfg.get("HEIGHT", 35),
                )
                display.lcd.DisplayText(
                    text=display_title,
                    x=tx,
                    y=ty,
                    width=tw,
                    height=th,
                    font=config.FONTS_DIR + title_cfg.get("FONT", "roboto/Roboto-Bold.ttf"),
                    font_size=title_cfg.get("FONT_SIZE", 22),
                    font_color=title_cfg.get("FONT_COLOR", (255, 255, 255)),
                    background_color=title_cfg.get("BACKGROUND_COLOR", (18, 18, 18)),
                    background_image=_get_theme_file_path(title_cfg.get("BACKGROUND_IMAGE", "background.png")),
                    align=title_cfg.get("ALIGN", "left"),
                    anchor=title_cfg.get("ANCHOR", "lt"),
                )

        # 3. Artist
        artist_cfg = layout.get("ARTIST", {})
        if artist_cfg.get("SHOW", True):
            display_artist = _truncate_text(artist, artist_cfg.get("MAX_LENGTH", 30))
            if display_artist != self._last_artist or force_redraw:
                self._last_artist = display_artist
                ax, ay, aw, ah = _clamp_coord(
                    artist_cfg.get("X", 225),
                    artist_cfg.get("Y", 115),
                    artist_cfg.get("WIDTH", 245),
                    artist_cfg.get("HEIGHT", 30),
                )
                display.lcd.DisplayText(
                    text=display_artist,
                    x=ax,
                    y=ay,
                    width=aw,
                    height=ah,
                    font=config.FONTS_DIR + artist_cfg.get("FONT", "roboto/Roboto-Medium.ttf"),
                    font_size=artist_cfg.get("FONT_SIZE", 18),
                    font_color=artist_cfg.get("FONT_COLOR", (30, 215, 96)),
                    background_color=artist_cfg.get("BACKGROUND_COLOR", (18, 18, 18)),
                    background_image=_get_theme_file_path(artist_cfg.get("BACKGROUND_IMAGE", "background.png")),
                    align=artist_cfg.get("ALIGN", "left"),
                    anchor=artist_cfg.get("ANCHOR", "lt"),
                )

        # 4. Album
        album_cfg = layout.get("ALBUM", {})
        if album_cfg.get("SHOW", True):
            display_album = _truncate_text(album, album_cfg.get("MAX_LENGTH", 32))
            if display_album != self._last_album or force_redraw:
                self._last_album = display_album
                alx, aly, alw, alh = _clamp_coord(
                    album_cfg.get("X", 225),
                    album_cfg.get("Y", 155),
                    album_cfg.get("WIDTH", 245),
                    album_cfg.get("HEIGHT", 25),
                )
                display.lcd.DisplayText(
                    text=display_album if display_album else " ",
                    x=alx,
                    y=aly,
                    width=alw,
                    height=alh,
                    font=config.FONTS_DIR + album_cfg.get("FONT", "roboto/Roboto-Regular.ttf"),
                    font_size=album_cfg.get("FONT_SIZE", 14),
                    font_color=album_cfg.get("FONT_COLOR", (180, 180, 180)),
                    background_color=album_cfg.get("BACKGROUND_COLOR", (18, 18, 18)),
                    background_image=_get_theme_file_path(album_cfg.get("BACKGROUND_IMAGE", "background.png")),
                    align=album_cfg.get("ALIGN", "left"),
                    anchor=album_cfg.get("ANCHOR", "lt"),
                )

        # 5. Playback Status
        status_cfg = layout.get("STATUS", {})
        if status_cfg.get("SHOW", True):
            if status_text != self._last_status or force_redraw:
                self._last_status = status_text
                sx, sy, sw, sh = _clamp_coord(
                    status_cfg.get("X", 225),
                    status_cfg.get("Y", 195),
                    status_cfg.get("WIDTH", 245),
                    status_cfg.get("HEIGHT", 25),
                )
                display.lcd.DisplayText(
                    text=status_text,
                    x=sx,
                    y=sy,
                    width=sw,
                    height=sh,
                    font=config.FONTS_DIR + status_cfg.get("FONT", "roboto/Roboto-Regular.ttf"),
                    font_size=status_cfg.get("FONT_SIZE", 14),
                    font_color=status_cfg.get("FONT_COLOR", (150, 150, 150)),
                    background_color=status_cfg.get("BACKGROUND_COLOR", (18, 18, 18)),
                    background_image=_get_theme_file_path(status_cfg.get("BACKGROUND_IMAGE", "background.png")),
                    align=status_cfg.get("ALIGN", "left"),
                    anchor=status_cfg.get("ANCHOR", "lt"),
                )

        # 6. Progress Bar
        bar_cfg = layout.get("PROGRESS_BAR", {})
        if bar_cfg.get("SHOW", True):
            progress_pct = int((position / duration * 100)) if duration > 0 else 0
            progress_pct = max(0, min(100, progress_pct))
            if progress_pct != self._last_progress_val or force_redraw:
                self._last_progress_val = progress_pct
                bx, by, bw, bh = _clamp_coord(
                    bar_cfg.get("X", 25),
                    bar_cfg.get("Y", 265),
                    bar_cfg.get("WIDTH", 430),
                    bar_cfg.get("HEIGHT", 8),
                )
                display.lcd.DisplayProgressBar(
                    x=bx,
                    y=by,
                    width=bw,
                    height=bh,
                    value=progress_pct,
                    min_value=0,
                    max_value=100,
                    bar_color=bar_cfg.get("BAR_COLOR", (30, 215, 96)),
                    bar_outline=False,
                    background_color=bar_cfg.get("BACKGROUND_COLOR", (45, 45, 45)),
                    background_image=None,
                )

        # 7. Time Position
        pos_cfg = layout.get("TIME_POSITION", {})
        if pos_cfg.get("SHOW", True):
            pos_str = format_seconds(position)
            if pos_str != self._last_pos_str or force_redraw:
                self._last_pos_str = pos_str
                px, py, pw, ph = _clamp_coord(
                    pos_cfg.get("X", 25),
                    pos_cfg.get("Y", 280),
                    pos_cfg.get("WIDTH", 0),
                    pos_cfg.get("HEIGHT", 0),
                )
                display.lcd.DisplayText(
                    text=pos_str,
                    x=px,
                    y=py,
                    width=pw,
                    height=ph,
                    font=config.FONTS_DIR + pos_cfg.get("FONT", "roboto-mono/RobotoMono-Regular.ttf"),
                    font_size=pos_cfg.get("FONT_SIZE", 13),
                    font_color=pos_cfg.get("FONT_COLOR", (180, 180, 180)),
                    background_color=pos_cfg.get("BACKGROUND_COLOR", (18, 18, 18)),
                    background_image=_get_theme_file_path(pos_cfg.get("BACKGROUND_IMAGE", "background.png")),
                    align=pos_cfg.get("ALIGN", "left"),
                    anchor=pos_cfg.get("ANCHOR", "lt"),
                )

        # 8. Time Duration
        dur_cfg = layout.get("TIME_DURATION", {})
        if dur_cfg.get("SHOW", True):
            dur_str = format_seconds(duration)
            if dur_str != self._last_dur_str or force_redraw:
                self._last_dur_str = dur_str
                dx, dy, dw, dh = _clamp_coord(
                    dur_cfg.get("X", 455),
                    dur_cfg.get("Y", 280),
                    dur_cfg.get("WIDTH", 0),
                    dur_cfg.get("HEIGHT", 0),
                )
                display.lcd.DisplayText(
                    text=dur_str,
                    x=dx,
                    y=dy,
                    width=dw,
                    height=dh,
                    font=config.FONTS_DIR + dur_cfg.get("FONT", "roboto-mono/RobotoMono-Regular.ttf"),
                    font_size=dur_cfg.get("FONT_SIZE", 13),
                    font_color=dur_cfg.get("FONT_COLOR", (180, 180, 180)),
                    background_color=dur_cfg.get("BACKGROUND_COLOR", (18, 18, 18)),
                    background_image=_get_theme_file_path(dur_cfg.get("BACKGROUND_IMAGE", "background.png")),
                    align=dur_cfg.get("ALIGN", "right"),
                    anchor=dur_cfg.get("ANCHOR", "ra"),
                )


media_screen = MediaScreen()
