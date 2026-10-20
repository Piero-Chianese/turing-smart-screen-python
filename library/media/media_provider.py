# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/

import asyncio
import datetime
import io
import platform
import threading
import time
from typing import Dict, Any, Optional
from PIL import Image

from library.log import logger

try:
    if platform.system() == "Windows":
        import winsdk.windows.media.control as wmc
        import winsdk.windows.storage.streams as wss
    else:
        wmc = None
        wss = None
except Exception as e:
    logger.warning(f"Could not initialize Windows Media Control SDK: {e}")
    wmc = None
    wss = None


def format_seconds(seconds: float) -> str:
    """Format seconds into M:SS or MM:SS."""
    if not seconds or seconds < 0:
        return "0:00"
    total_sec = int(seconds)
    minutes = total_sec // 60
    sec = total_sec % 60
    return f"{minutes:02d}:{sec:02d}"


class MediaProvider:
    """
    Retrieves current media playback information (Spotify, web browser, etc.)
    using Windows System Media Transport Controls (SMTC).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._cached_info: Dict[str, Any] = {
            "status": "STOPPED",
            "title": "",
            "artist": "",
            "album": "",
            "position": 0.0,
            "duration": 0.0,
            "thumbnail": None,
            "app_name": "",
        }
        self._last_track_id = ""
        self._cached_thumbnail: Optional[Image.Image] = None
        self._thumbnail_attempts = 0
        self._last_poll_time = 0.0

    def get_info(self) -> Dict[str, Any]:
        """Returns the latest media playback information."""
        now = time.time()
        # Poll at most once every 0.35 seconds
        if now - self._last_poll_time > 0.35:
            self._poll()
            self._last_poll_time = now

        with self._lock:
            return dict(self._cached_info)

    def _poll(self):
        if wmc is None:
            return

        try:
            info = asyncio.run(self._async_fetch())
            with self._lock:
                self._cached_info = info
        except Exception as e:
            logger.debug(f"MediaProvider poll error: {e}")

    async def _async_fetch(self) -> Dict[str, Any]:
        try:
            manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            if not manager:
                return self._idle_info()

            sessions = manager.get_sessions()
            if not sessions:
                return self._idle_info()

            # Priority 1: Any session currently in PLAYING status (prefer Spotify if playing)
            target_session = None
            for s in sessions:
                try:
                    pb = s.get_playback_info()
                    if pb and pb.playback_status == wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                        if "spotify" in s.source_app_user_model_id.lower():
                            target_session = s
                            break
                        elif target_session is None:
                            target_session = s
                except:
                    pass

            # Priority 2: If none playing, search for a Spotify session (paused)
            if target_session is None:
                for s in sessions:
                    try:
                        if "spotify" in s.source_app_user_model_id.lower():
                            target_session = s
                            break
                    except:
                        pass

            # Priority 3: Current default session
            if target_session is None:
                target_session = manager.get_current_session()

            # Priority 4: Fallback to first session
            if target_session is None and len(sessions) > 0:
                target_session = sessions[0]

            if target_session is None:
                return self._idle_info()

            props = await target_session.try_get_media_properties_async()
            playback = target_session.get_playback_info()
            timeline = target_session.get_timeline_properties()

            status_str = "STOPPED"
            if playback:
                name = playback.playback_status.name
                if name == "PLAYING":
                    status_str = "PLAYING"
                elif name == "PAUSED":
                    status_str = "PAUSED"

            title = props.title if props and props.title else ""
            artist = props.artist if props and props.artist else ""
            album = props.album_title if props and props.album_title else ""
            app_id = target_session.source_app_user_model_id

            # Timeline position calculation:
            # SMTC provides a static snapshot of position at 'last_updated_time'.
            # If playing, calculate real current position by extrapolating elapsed time.
            pos = 0.0
            dur = 0.0
            if timeline:
                dur = timeline.end_time.total_seconds() if timeline.end_time else 0.0
                base_pos = timeline.position.total_seconds() if timeline.position else 0.0

                if status_str == "PLAYING" and timeline.last_updated_time:
                    try:
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        elapsed = (now_utc - timeline.last_updated_time).total_seconds()
                        if elapsed > 0:
                            pos = base_pos + elapsed
                        else:
                            pos = base_pos
                    except Exception:
                        pos = base_pos
                else:
                    pos = base_pos

                if dur > 0:
                    pos = min(dur, max(0.0, pos))
                else:
                    pos = max(0.0, pos)

            # Thumbnail loading with reliable retry logic:
            # When track changes, Spotify metadata (title/artist) updates before the image stream is ready.
            # We retry loading the thumbnail until it succeeds.
            track_id = f"{title}||{artist}"
            if track_id != self._last_track_id:
                self._last_track_id = track_id
                self._cached_thumbnail = None
                self._thumbnail_attempts = 0

            if self._cached_thumbnail is None and props and props.thumbnail and self._thumbnail_attempts < 15:
                self._thumbnail_attempts += 1
                try:
                    stream = await props.thumbnail.open_read_async()
                    if stream and stream.size > 0:
                        reader = wss.DataReader(stream)
                        await reader.load_async(stream.size)
                        buffer = bytearray(stream.size)
                        reader.read_bytes(buffer)
                        self._cached_thumbnail = Image.open(io.BytesIO(buffer)).convert("RGB")
                        logger.debug(f"MediaProvider: successfully loaded cover art for '{title}' ({len(buffer)} bytes)")
                except Exception as e:
                    logger.debug(f"MediaProvider: attempt {self._thumbnail_attempts} reading thumbnail: {e}")

            return {
                "status": status_str,
                "title": title,
                "artist": artist,
                "album": album,
                "position": pos,
                "duration": dur,
                "thumbnail": self._cached_thumbnail,
                "app_name": app_id,
            }
        except Exception as e:
            logger.debug(f"Async fetch exception: {e}")
            return self._idle_info()

    def _idle_info(self) -> Dict[str, Any]:
        return {
            "status": "STOPPED",
            "title": "",
            "artist": "",
            "album": "",
            "position": 0.0,
            "duration": 0.0,
            "thumbnail": None,
            "app_name": "",
        }


media_provider = MediaProvider()
