"""banner.py -- TRAP HUB boot sequence with professional splash"""
import time
import os
import sys
import shutil
import threading
import random


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def hide_cursor():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def move_to(x, y):
    sys.stdout.write(f"\033[{y};{x}H")
    sys.stdout.flush()


def save_pos():
    sys.stdout.write("\033[s")
    sys.stdout.flush()


def restore_pos():
    sys.stdout.write("\033[u")
    sys.stdout.flush()


SPINNER_CHARS = ["|", "/", "-", "\\", "|", "/", "-", "\\", "|", "/"]


def spinner(duration=3, message="Loading", color="\033[36m"):
    hide_cursor()
    w = shutil.get_terminal_size().columns
    start = time.time()
    i = 0
    while time.time() - start < duration:
        frame = SPINNER_CHARS[i % len(SPINNER_CHARS)]
        dots = "." * ((i // 2) % 4)
        sys.stdout.write(f"\r  {color}{frame}\033[0m {message}{dots}  ")
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1
    sys.stdout.write(f"\r  {' ' * (len(message) + 10)}\r")
    sys.stdout.flush()
    show_cursor()


def centered_text(text, y_offset=0, color="\033[37m", bold=False):
    w = shutil.get_terminal_size().columns
    h = shutil.get_terminal_size().lines
    x = max(0, (w - len(text)) // 2)
    y = h // 2 + y_offset
    move_to(x + 1, y)
    if bold:
        sys.stdout.write("\033[1m")
    sys.stdout.write(f"{color}{text}\033[0m")
    sys.stdout.flush()


def splash_screen():
    """Full-screen hacker splash: border frame, bold red TETHER OS, pulsing threat."""
    clear()
    hide_cursor()
    w = shutil.get_terminal_size().columns
    h = shutil.get_terminal_size().lines

    for y in range(1, h + 1):
        move_to(1, y)
        sys.stdout.write("\033[40m" + " " * w + "\033[0m")

    R = "\033[31m"
    BR = "\033[31m\033[1m"
    G = "\033[92m"
    W = "\033[97m"
    DIM = "\033[2m"
    N = "\033[0m"

    def center(y, text, color=BR):
        x = max(0, (w - len(text)) // 2)
        move_to(x + 1, y)
        sys.stdout.write(f"{color}{text}{N}")

    cx = w // 2
    bw = min(56, w - 4)
    bar = "+" + "-" * bw + "+"
    gap = "|" + " " * bw + "|"
    dash = "|" + "-" * bw + "|"

    cy = h // 2

    def frame_line(text, color=BR):
        inner = text.center(bw)
        return "|" + inner + "|"

    rows = [
        (cy - 4, bar, R),
        (cy - 3, frame_line("TETHER OS", BR), BR),
        (cy - 2, dash, BR),
        (cy - 1, frame_line(">>  TARGET ACQUIRED  <<", BR), BR),
        (cy + 0, frame_line("product of TRAP HUB  |  v1.0.0", DIM), DIM),
        (cy + 1, bar, R),
    ]

    for y, txt, col in rows:
        center(y, txt, col)

    sys.stdout.write(f"\033[{h};1H")
    sys.stdout.write("\033[40m" + " " * w + "\033[0m")
    sys.stdout.flush()

    threat_y = cy - 1
    threat_txt = frame_line(">>  TARGET ACQUIRED  <<", BR)
    for _ in range(5):
        time.sleep(0.12)
        center(threat_y, threat_txt, W)
        sys.stdout.flush()
        time.sleep(0.08)
        center(threat_y, threat_txt, BR)
        sys.stdout.flush()

    time.sleep(0.5)
    show_cursor()


def matrix_rain(duration=2, color="\033[92m"):
    """Matrix-style digital rain effect."""
    hide_cursor()
    w = shutil.get_terminal_size().columns
    h = shutil.get_terminal_size().lines
    columns = [[] for _ in range(w)]
    for i in range(w):
        columns[i] = {"y": random.randint(-h, 0), "speed": random.randint(1, 3)}
    chars = "0123456789ABCDEF"
    start = time.time()
    while time.time() - start < duration:
        for x in range(0, w, 2):
            col = columns[x]
            if col["y"] < 0:
                move_to(x + 1, 1)
                sys.stdout.write(" ")
            else:
                for offset in range(int(min(3, max(0, h - col["y"])))):
                    y_pos = col["y"] - offset
                    if 0 < y_pos <= h:
                        move_to(x + 1, y_pos)
                        brightness = "\033[92m" if offset == 0 else "\033[2m\033[92m"
                        sys.stdout.write(f"{brightness}{random.choice(chars)}\033[0m")
                if col["y"] - 3 > 0:
                    move_to(x + 1, col["y"] - 3)
                    sys.stdout.write(" ")
            col["y"] += col["speed"] * 0.3
            if col["y"] > h + 3:
                col["y"] = random.randint(-h, -5)
                col["speed"] = random.randint(1, 3)
        move_to(1, h)
        sys.stdout.flush()
        time.sleep(0.05)
    show_cursor()


def type_text(text, delay=0.03, color="\033[37m", newline=True):
    """Typewriter-style text animation."""
    sys.stdout.write(color)
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\033[0m")
    if newline:
        sys.stdout.write("\n")
    sys.stdout.flush()


def set_dark_bg():
    w = shutil.get_terminal_size().columns
    h = shutil.get_terminal_size().lines
    for y in range(1, h + 1):
        move_to(1, y)
        sys.stdout.write("\033[40m" + " " * w + "\033[0m")
    move_to(1, 1)
    sys.stdout.flush()


TRAP_HUB_LOGO = """
\033[31m  ==============================================================
\033[31m  ||   TTTTT  EEEE  TTTTT  H   H  EEEE  RRRR     O   SSSS   ||
\033[31m  ||     T    E       T    H   H  E     R   R   O O  S      ||
\033[31m  ||     T    EEE     T    HHHHH  EEE   RRRR   O   O  SSS   ||
\033[31m  ||     T    E       T    H   H  E     R  R    O   O    S  ||
\033[31m  ||     T    EEEE    T    H   H  EEEE  R   R    O   SSSS   ||
\033[31m  ||             product of TRAP HUB  |  v1.0.0            ||
\033[31m  ==============================================================
\033[0m"""


def boot_sequence():
    """Full boot sequence: splash -> matrix rain -> logo -> modules -> ready."""
    hide_cursor()

    splash_screen()

    clear()
    spinner(1.5, "Waking network interfaces", "\033[36m")

    clear()
    hide_cursor()
    matrix_rain(2.5)

    clear()
    hide_cursor()
    set_dark_bg()

    sys.stdout.write(TRAP_HUB_LOGO)
    sys.stdout.flush()
    time.sleep(1)

    boot_msgs = [
        ("\033[36m[\033[92m+\033[36m]\033[0m Initializing Tether OS kernel...", 0.15),
        ("\033[36m[\033[92m+\033[36m]\033[0m Loading anti-forensic modules...", 0.12),
        ("\033[36m[\033[92m+\033[36m]\033[0m   \033[2m[0x7A3F] memory_scraper.dll       \033[32mOK\033[0m", 0.08),
        ("\033[36m[\033[92m+\033[36m]\033[0m   \033[2m[0xB901] process_hider.sys       \033[32mOK\033[0m", 0.08),
        ("\033[36m[\033[92m+\033[36m]\033[0m   \033[2m[0x4C2E] log_cleaner.drv         \033[32mOK\033[0m", 0.08),
        ("\033[36m[\033[92m+\033[36m]\033[0m   \033[2m[0xD7F1] timestamp_forger.sys    \033[32mOK\033[0m", 0.08),
        ("\033[36m[\033[92m+\033[36m]\033[0m   \033[2m[0x2A8C] dns_spoofer.dll         \033[32mOK\033[0m", 0.08),
        ("\033[36m[\033[92m+\033[36m]\033[0m   \033[2m[0xF034] proxy_chain_manager     \033[32mOK\033[0m", 0.08),
        ("", 0.2),
        ("\033[36m[\033[92m+\033[36m]\033[0m Securing control circuit...", 0.15),
        ("\033[36m[\033[92m+\033[36m]\033[0m   \033[2mTor handshake: 3-hop relay established\033[0m", 0.1),
        ("\033[36m[\033[92m+\033[36m]\033[0m   \033[2mExit node: Switzerland (185.220.101.x)\033[0m", 0.1),
        ("\033[36m[\033[92m+\033[36m]\033[0m   \033[2mCircuit latency: 284ms\033[0m", 0.1),
        ("", 0.3),
    ]

    for text, delay in boot_msgs:
        if text:
            sys.stdout.write(f"  {text}\n")
        else:
            sys.stdout.write("\n")
        sys.stdout.flush()
        time.sleep(delay)

    sys.stdout.write("\n  ")
    sys.stdout.flush()
    type_text("YOUR CONNECTION IS NOW ANONYMIZED.", 0.04, "\033[92m")
    time.sleep(0.5)
    sys.stdout.write("\n  ")
    sys.stdout.flush()
    type_text("YOUR IDENTITY REMAINS HIDDEN.", 0.04, "\033[92m")
    time.sleep(0.8)

    clear()
    show_cursor()


def reset_color():
    sys.stdout.write("\033[0m")
    sys.stdout.flush()


def dim():
    sys.stdout.write("\033[2m")
