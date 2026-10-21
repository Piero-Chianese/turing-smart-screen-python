# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/

import platform
import threading
import time
from typing import Optional, Tuple

from library import config
from library.display import display
from library.log import logger

if platform.system() == "Windows":
    import win32con
else:
    win32con = None


PAGE_SYSTEM = "SYSTEM"
PAGE_MEDIA = "MEDIA"
PAGE_CLOCK = "CLOCK"


def parse_hotkey_string(hotkey_str: str) -> Tuple[int, int]:
    """
    Parses a hotkey string like 'ctrl+shift+s' or 'f10' into (modifiers, vk_code)
    for win32gui.RegisterHotKey.
    """
    if win32con is None or not hotkey_str:
        return 0, 0

    modifiers = 0
    parts = [p.strip().lower() for p in hotkey_str.split('+')]
    for p in parts[:-1]:
        if p in ('ctrl', 'control'):
            modifiers |= win32con.MOD_CONTROL
        elif p in ('alt', 'menu'):
            modifiers |= win32con.MOD_ALT
        elif p in ('shift',):
            modifiers |= win32con.MOD_SHIFT
        elif p in ('win', 'windows'):
            modifiers |= win32con.MOD_WIN

    key = parts[-1]
    vk_code = 0
    if len(key) == 1:
        vk_code = ord(key.upper())
    elif key.startswith('f') and key[1:].isdigit():
        vk_code = getattr(win32con, f"VK_F{key[1:]}", 0)
    elif key == 'space':
        vk_code = win32con.VK_SPACE
    elif key in ('pause', 'break'):
        vk_code = win32con.VK_PAUSE
    elif key == 'scrolllock':
        vk_code = win32con.VK_SCROLL

    return modifiers, vk_code


class PageManager:
    """
    Manages active screen pages (System Monitor, Spotify/Media screen, Clock screen)
    and serializes transitions between them.
    """

    def __init__(self):
        self._current_page = PAGE_SYSTEM
        self._lock = threading.Lock()
        self._auto_return_timer: Optional[threading.Timer] = None

    @property
    def current_page(self) -> str:
        with self._lock:
            return self._current_page

    def is_page_active(self, page_name: str) -> bool:
        with self._lock:
            return self._current_page == page_name

    def get_enabled_pages(self):
        pages = [PAGE_SYSTEM]
        if config.CONFIG_DATA.get("media_screen", {}).get("ENABLED", False):
            pages.append(PAGE_MEDIA)
        if config.CONFIG_DATA.get("clock_screen", {}).get("ENABLED", False):
            pages.append(PAGE_CLOCK)
        return pages

    def toggle_page(self):
        """Cycle through enabled pages."""
        pages = self.get_enabled_pages()
        with self._lock:
            if self._current_page in pages:
                idx = pages.index(self._current_page)
                target = pages[(idx + 1) % len(pages)]
            else:
                target = pages[0]
        self.switch_to_page(target)

    def toggle_media_page(self):
        with self._lock:
            target = PAGE_SYSTEM if self._current_page == PAGE_MEDIA else PAGE_MEDIA
        self.switch_to_page(target)

    def toggle_clock_page(self):
        with self._lock:
            target = PAGE_SYSTEM if self._current_page == PAGE_CLOCK else PAGE_CLOCK
        self.switch_to_page(target)

    def switch_to_page(self, page_name: str):
        with self._lock:
            if self._auto_return_timer:
                self._auto_return_timer.cancel()
                self._auto_return_timer = None

            if self._current_page == page_name:
                return

            self._current_page = page_name
            logger.info(f"Switched active screen to '{page_name}'")

            # 1. Wait briefly for in-flight image chunks of the previous page to complete
            # so the serial link and LCD controller are in a clean, idle state
            if hasattr(display.lcd, 'update_queue') and display.lcd.update_queue:
                t_end = time.time() + 0.35
                while not display.lcd.update_queue.empty() and time.time() < t_end:
                    time.sleep(0.01)

            # 2. Reset text bounding box cache on display driver to avoid cross-theme ghosting
            if hasattr(display.lcd, 'text_bbox_cache'):
                display.lcd.text_bbox_cache.clear()

        if page_name == PAGE_MEDIA:
            self._activate_media_page()
        elif page_name == PAGE_CLOCK:
            self._activate_clock_page()
        else:
            self._activate_system_page()

    def _activate_media_page(self):
        from library.media.media_screen import media_screen
        if hasattr(media_screen, 'reset_cache'):
            media_screen.reset_cache()
        if config.MEDIA_THEME_DATA:
            from library.display import get_theme_orientation
            media_orient = get_theme_orientation(config.MEDIA_THEME_DATA)
            display.lcd.SetOrientation(media_orient)

        # 1. Draw media screen background & static images/texts
        media_screen.display_static_elements()
        # 2. Render initial dynamic media content
        media_screen.render(force_redraw=True)

        # 3. Setup auto-return timer if configured
        media_cfg = config.CONFIG_DATA.get("media_screen", {})
        timeout = media_cfg.get("AUTO_RETURN_TIMEOUT", 0)
        if timeout and timeout > 0:
            def auto_return():
                logger.info(f"Auto-return timeout ({timeout}s) reached, returning to System Monitor")
                self.switch_to_page(PAGE_SYSTEM)

            with self._lock:
                self._auto_return_timer = threading.Timer(float(timeout), auto_return)
                self._auto_return_timer.daemon = True
                self._auto_return_timer.start()

    def _activate_clock_page(self):
        from library.clock.clock_screen import clock_screen
        clock_screen.reset_cache()
        if config.CLOCK_THEME_DATA:
            from library.display import get_theme_orientation
            clock_orient = get_theme_orientation(config.CLOCK_THEME_DATA)
            display.lcd.SetOrientation(clock_orient)

        clock_screen.display_static_elements()
        clock_screen.render(force_redraw=True)

    def _activate_system_page(self):
        from library.display import get_theme_orientation
        sys_orient = get_theme_orientation(config.THEME_DATA)
        display.lcd.SetOrientation(sys_orient)

        # 1. Redraw system monitor static background and text
        display.display_static_images()
        display.display_static_text()

        # 2. Force immediate refresh of sensor values
        try:
            import library.stats as stats
            stats.CPU.percentage()
            stats.CPU.load()
            stats.CPU.temperature()
            if stats.Gpu.is_available():
                stats.Gpu.stats()
            stats.Memory.stats()
            stats.Disk.stats()
            stats.Net.stats()
            stats.Date.stats()
            stats.SystemUptime.stats()
        except Exception as e:
            logger.debug(f"Error refreshing sensors after page switch: {e}")


page_manager = PageManager()
