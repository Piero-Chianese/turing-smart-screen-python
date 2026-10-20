# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
# Copyright (C) 2022 Rollbacke
# Copyright (C) 2022 Ebag333
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import queue
import sys
from pathlib import Path
import yaml

from library.log import logger


def load_yaml(configfile):
    with open(configfile, "rt", encoding='utf8') as stream:
        yamlconfig = yaml.safe_load(stream)
        return yamlconfig


PATH = sys.path[0]
MAIN_DIRECTORY = Path(__file__).parent.parent.resolve()
FONTS_DIR = str(MAIN_DIRECTORY / "res" / "fonts") + "/"
CONFIG_DATA = load_yaml(MAIN_DIRECTORY / "config.yaml")
THEME_DEFAULT = load_yaml(MAIN_DIRECTORY / "res/themes/default.yaml")
THEME_DATA = None
MEDIA_THEME_DATA = None
CLOCK_THEME_DATA = None


def copy_default(default, theme):
    """recursively supply default values into a dict of dicts of dicts ...."""
    for k, v in default.items():
        if k not in theme:
            theme[k] = v
        if type(v) == type({}):
            copy_default(default[k], theme[k])


def load_theme():
    global THEME_DATA
    try:
        theme_path = Path("res/themes/" + CONFIG_DATA['config']['THEME'])
        logger.info("Loading theme %s from %s" % (CONFIG_DATA['config']['THEME'], theme_path / "theme.yaml"))
        THEME_DATA = load_yaml(MAIN_DIRECTORY / theme_path / "theme.yaml")
        THEME_DATA['PATH'] = str(MAIN_DIRECTORY / theme_path) + "/"
    except:
        logger.error("Theme not found or contains errors!")
        try:
            sys.exit(0)
        except:
            os._exit(0)

    copy_default(THEME_DEFAULT, THEME_DATA)


def load_media_theme():
    global MEDIA_THEME_DATA
    media_cfg = CONFIG_DATA.get('media_screen', {})
    if not media_cfg.get('ENABLED', False):
        return

    theme_name = media_cfg.get('THEME', 'LandscapeMediaSpotify')
    try:
        theme_path = Path("res/themes/" + theme_name)
        logger.info("Loading media theme %s from %s" % (theme_name, theme_path / "theme.yaml"))
        MEDIA_THEME_DATA = load_yaml(MAIN_DIRECTORY / theme_path / "theme.yaml")
        MEDIA_THEME_DATA['PATH'] = str(MAIN_DIRECTORY / theme_path) + "/"
    except Exception as e:
        logger.warning("Media theme '%s' not found or contains errors: %s" % (theme_name, str(e)))
        MEDIA_THEME_DATA = None


def load_clock_theme():
    global CLOCK_THEME_DATA
    clock_cfg = CONFIG_DATA.get('clock_screen', {})
    if not clock_cfg.get('ENABLED', False):
        return

    theme_name = clock_cfg.get('THEME', 'LandscapeCharizardClock')
    try:
        theme_path = Path("res/themes/" + theme_name)
        logger.info("Loading clock theme %s from %s" % (theme_name, theme_path / "theme.yaml"))
        CLOCK_THEME_DATA = load_yaml(MAIN_DIRECTORY / theme_path / "theme.yaml")
        CLOCK_THEME_DATA['PATH'] = str(MAIN_DIRECTORY / theme_path) + "/"
    except Exception as e:
        logger.warning("Clock theme '%s' not found or contains errors: %s" % (theme_name, str(e)))
        CLOCK_THEME_DATA = None


def check_theme_compatible(display_size: str):
    # Check if theme is compatible with hardware revision
    if display_size != THEME_DATA['display'].get("DISPLAY_SIZE", '3.5"'):
        logger.error("The selected theme " + CONFIG_DATA['config'][
            'THEME'] + " is not compatible with your display revision " + CONFIG_DATA["display"]["REVISION"])
        try:
            sys.exit(0)
        except:
            os._exit(0)


# Load themes on import
load_theme()
load_media_theme()
load_clock_theme()

# Queue containing the serial requests to send to the screen
update_queue = queue.Queue()
