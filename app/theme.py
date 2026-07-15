"""theme.py -- TRAP HUB theme engine
Color presets, ANSI helpers, persistence.
"""

import json
import os

THEMES = {
    "matrix": {
        "name": "Matrix",
        "primary": "\033[31m",
        "secondary": "\033[32m",
        "accent": "\033[36m",
        "warning": "\033[33m",
        "text": "\033[32m",
        "prompt_user": "\033[31m",
        "prompt_host": "\033[36m",
        "prompt_path": "\033[33m",
        "prompt_sep": "\033[31m",
        "border": "\033[31m",
        "dim": "\033[2m",
        "bold": "\033[1m",
        "reset": "\033[0m",
        "hex": {"primary": "#FF0000", "secondary": "#00FF00", "accent": "#00FFFF",
                "warning": "#FFFF00", "text": "#00FF00"},
    },
    "amber": {
        "name": "Amber",
        "primary": "\033[33m",
        "secondary": "\033[93m",
        "accent": "\033[93m",
        "warning": "\033[31m",
        "text": "\033[93m",
        "prompt_user": "\033[33m",
        "prompt_host": "\033[93m",
        "prompt_path": "\033[33m",
        "prompt_sep": "\033[33m",
        "border": "\033[33m",
        "dim": "\033[2m",
        "bold": "\033[1m",
        "reset": "\033[0m",
        "hex": {"primary": "#FFB000", "secondary": "#FFD700", "accent": "#FFE000",
                "warning": "#FF0000", "text": "#FFB000"},
    },
    "terminal": {
        "name": "Terminal",
        "primary": "\033[37m",
        "secondary": "\033[97m",
        "accent": "\033[36m",
        "warning": "\033[33m",
        "text": "\033[37m",
        "prompt_user": "\033[32m",
        "prompt_host": "\033[37m",
        "prompt_path": "\033[36m",
        "prompt_sep": "\033[37m",
        "border": "\033[37m",
        "dim": "\033[2m",
        "bold": "\033[1m",
        "reset": "\033[0m",
        "hex": {"primary": "#CCCCCC", "secondary": "#FFFFFF", "accent": "#00CCCC",
                "warning": "#FFCC00", "text": "#CCCCCC"},
    },
    "hacker": {
        "name": "Hacker",
        "primary": "\033[31m",
        "secondary": "\033[91m",
        "accent": "\033[33m",
        "warning": "\033[93m",
        "text": "\033[91m",
        "prompt_user": "\033[31m",
        "prompt_host": "\033[91m",
        "prompt_path": "\033[33m",
        "prompt_sep": "\033[31m",
        "border": "\033[31m",
        "dim": "\033[2m",
        "bold": "\033[1m",
        "reset": "\033[0m",
        "hex": {"primary": "#CC0000", "secondary": "#FF3333", "accent": "#FF9900",
                "warning": "#FFFF00", "text": "#FF3333"},
    },
}


def _config_path():
    d = os.path.join(os.path.expanduser("~"), ".tether")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "theme.json")


def load_theme():
    path = _config_path()
    if os.path.isfile(path):
        try:
            with open(path) as f:
                data = json.load(f)
            name = data.get("theme", "matrix")
            if name in THEMES:
                return THEMES[name]
        except:
            pass
    return THEMES["matrix"]


def save_theme(name):
    if name not in THEMES:
        return False
    path = _config_path()
    with open(path, "w") as f:
        json.dump({"theme": name}, f)
    return True


def list_themes():
    return list(THEMES.keys())


class Theme:
    _instance = None

    def __init__(self):
        self.current = None

    def get(self):
        if not self.current:
            self.current = load_theme()
        return self.current

    def set(self, name):
        if name in THEMES:
            self.current = THEMES[name]
            save_theme(name)
            return True
        return False

    def c(self, key):
        return self.get().get(key, "")

    def p(self, text, key="text"):
        return f"{self.c(key)}{text}{self.c('reset')}"


theme = Theme()
