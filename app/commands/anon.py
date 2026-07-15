"""anon.py -- Anonymity commands (proxychains, macchanger, anonsurf)"""

import os
import sys
import subprocess
import random
import re
import time

_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _color(c, text):
    codes = {"g": "\033[32m", "r": "\033[31m", "y": "\033[33m", "c": "\033[36m", "b": "\033[1m", "d": "\033[0m"}
    return f"{codes.get(c, '')}{text}\033[0m"


# ---- proxychains ----

def _cmd_proxychains(args):
    if not args:
        print("  usage: proxychains <command> [args...]")
        print("  Routes the given command through Tor SOCKS5 proxy (127.0.0.1:9050)")
        print()
        print("  examples:")
        print("    proxychains curl https://check.torproject.org")
        print("    proxychains nmap --tor -p 80 example.com")
        print("    proxychains ping 8.8.8.8")
        return

    cmd = " ".join(args)
    proxy = "socks5://127.0.0.1:9050"
    print(f"  Routing through Tor proxy {proxy}...")
    print(f"  Executing: {cmd}")
    print()

    env = os.environ.copy()
    env["HTTP_PROXY"] = proxy
    env["HTTPS_PROXY"] = proxy
    env["ALL_PROXY"] = proxy
    env["http_proxy"] = proxy
    env["https_proxy"] = proxy
    env["all_proxy"] = proxy
    env["NO_PROXY"] = "localhost,127.0.0.1,::1"
    env["no_proxy"] = "localhost,127.0.0.1,::1"

    try:
        r = subprocess.run(
            args,
            capture_output=True, text=True, timeout=30, env=env,
            shell=True,
        )
        for line in r.stdout.split("\n"):
            print(f"  {line}")
        if r.stderr.strip():
            for line in r.stderr.split("\n"):
                if line.strip():
                    print(f"  (stderr) {line}")
    except FileNotFoundError:
        print(f"  proxychains: command not found: {args[0]}")
    except subprocess.TimeoutExpired:
        print("  proxychains: command timed out (30s)")
    except Exception as e:
        print(f"  proxychains: error: {e}")


# ---- macchanger ----

_SAVED_MACS = {}


def _get_mac_info():
    adapters = []
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-NetAdapter | Select-Object Name, MacAddress, Status | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            import json as _json
            data = _json.loads(r.stdout.strip())
            if not isinstance(data, list):
                data = [data]
            for item in data:
                adapters.append({
                    "name": item.get("Name", "?"),
                    "mac": item.get("MacAddress", "?"),
                    "status": item.get("Status", "?"),
                })
    except:
        pass
    return adapters


def _set_mac(adapter_name, new_mac):
    try:
        subprocess.run([
            "powershell", "-Command",
            f"Disable-NetAdapter -Name '{adapter_name}' -Confirm:$false"
        ], capture_output=True, timeout=10)

        subprocess.run([
            "powershell", "-Command",
            f"Set-NetAdapterAdvancedProperty -Name '{adapter_name}' "
            f"-RegistryKeyword 'NetworkAddress' -RegistryValue '{new_mac}'"
        ], capture_output=True, timeout=10)

        subprocess.run([
            "powershell", "-Command",
            f"Enable-NetAdapter -Name '{adapter_name}' -Confirm:$false"
        ], capture_output=True, timeout=10)
        return True
    except:
        return False


def _random_mac():
    prefixes = ["00", "02", "06", "0A", "12", "1A", "22", "2A", "32", "3A",
                "42", "4A", "52", "5A", "62", "6A", "72", "7A", "82", "8A",
                "92", "9A", "A2", "AA", "B2", "BA", "C2", "CA", "D2", "DA",
                "E2", "EA", "F2", "FA"]
    octets = [random.choice(prefixes)]
    for _ in range(5):
        octets.append(f"{random.randint(0, 255):02X}")
    return ":".join(octets)


def _cmd_macchanger(args):
    show_only = False
    randomize = False
    new_mac = None
    restore = False
    adapter = None

    i = 0
    while i < len(args):
        if args[i] == "-r":
            randomize = True
            i += 1
        elif args[i] == "-s":
            show_only = True
            i += 1
        elif args[i] == "-p":
            restore = True
            i += 1
        elif args[i] == "-m" and i + 1 < len(args):
            new_mac = args[i + 1].upper()
            if ":" not in new_mac:
                new_mac = ":".join(new_mac[i:i+2] for i in range(0, 12, 2))
            i += 2
        else:
            adapter = args[i]
            i += 1

    adapters = _get_mac_info()
    if not adapters:
        print("  macchanger: no network adapters found")
        print("  (requires PowerShell admin rights on Windows)")
        return

    if not adapter:
        adapter = adapters[0]["name"] if adapters else None
    if not adapter:
        print("  macchanger: could not determine network adapter")
        return

    current = None
    for a in adapters:
        if a["name"].lower() == adapter.lower():
            current = a["mac"]
            break
    if not current:
        print(f"  macchanger: adapter '{adapter}' not found")
        return

    if show_only or (not randomize and not new_mac and not restore):
        print(f"  Current MAC:  {current}")
        print(f"  Adapter:      {adapter}")
        print(f"  Status:       {'Up' if 'Up' in str(adapters) else '?'}")
        print()
        print(f"  Use -r for random, -m XX:XX:XX:XX:XX:XX for specific, -p to restore")
        return

    if adapter not in _SAVED_MACS:
        _SAVED_MACS[adapter] = current

    if restore:
        target = _SAVED_MACS.get(adapter, current)
        action = "restoring original"
    elif new_mac:
        target = new_mac
        action = "setting"
    else:
        target = _random_mac()
        action = "randomizing"

    print(f"  {action} MAC address for {adapter}")
    print(f"  Old: {current}")
    print(f"  New: {target}")
    print()

    if _set_mac(adapter, target.replace(":", "")):
        print(f"  \033[32m[OK] MAC changed successfully\033[0m")
        print(f"  New MAC: {target}")
    else:
        print(f"  \033[31m[FAIL] Could not change MAC\033[0m")
        print(f"  (Run PowerShell as Administrator for MAC spoofing)")
        _SAVED_MACS.pop(adapter, None)


# ---- anonsurf ----

def _cmd_anonsurf(args):
    mode = args[0].lower() if args else "status"

    if mode == "start":
        proxy = "socks5://127.0.0.1:9050"
        env_file = os.path.join(os.path.expanduser("~"), ".tether", "proxy.env")
        os.makedirs(os.path.dirname(env_file), exist_ok=True)
        with open(env_file, "w") as f:
            f.write(f"HTTP_PROXY={proxy}\n")
            f.write(f"HTTPS_PROXY={proxy}\n")
            f.write(f"ALL_PROXY={proxy}\n")
            f.write(f"http_proxy={proxy}\n")
            f.write(f"https_proxy={proxy}\n")
            f.write(f"all_proxy={proxy}\n")
            f.write("NO_PROXY=localhost,127.0.0.1,::1\n")
        print("  \033[32m[OK] Anonymous mode STARTED\033[0m")
        print("  All system proxy traffic will be routed through Tor")
        print(f"  Proxy: {proxy}")
        print()
        print("  \033[33m[!] Note: Only affects apps that respect HTTP_PROXY\033[0m")
        print("  Use 'proxychains <cmd>' for apps that ignore system proxy")
        print()
        print("  \033[36m  TIP: Check with: curl --proxy http://127.0.0.1:9050 https://check.torproject.org\033[0m")

    elif mode == "stop":
        env_file = os.path.join(os.path.expanduser("~"), ".tether", "proxy.env")
        if os.path.isfile(env_file):
            os.remove(env_file)
        print("  \033[33m[OK] Anonymous mode STOPPED\033[0m")
        print("  Proxy environment variables cleared")

    elif mode == "status":
        env_file = os.path.join(os.path.expanduser("~"), ".tether", "proxy.env")
        active = os.path.isfile(env_file)

        try:
            import socket as _s
            s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
            s.settimeout(2)
            tor_running = s.connect_ex(("127.0.0.1", 9050)) == 0
            s.close()
        except:
            tor_running = False

        if active and tor_running:
            print("  \033[32mAnonymous mode: FULLY ACTIVE\033[0m")
        elif active and not tor_running:
            print("  \033[33mAnonymous mode: PARTIAL (proxy set, Tor not detected)\033[0m")
        elif not active and tor_running:
            print("  \033[33mAnonymous mode: INACTIVE (Tor running, no proxy)\033[0m")
        else:
            print("  \033[31mAnonymous mode: INACTIVE\033[0m")

        if active:
            with open(env_file) as f:
                for line in f:
                    print(f"    {line.strip()}")

        print(f"  Tor daemon:   {'\033[32mRUNNING\033[0m' if tor_running else '\033[31mSTOPPED\033[0m'}")
        print()
        print("  To activate:  anonsurf start")
        print("  To deactivate: anonsurf stop")

    elif mode == "toggle":
        env_file = os.path.join(os.path.expanduser("~"), ".tether", "proxy.env")
        if os.path.isfile(env_file):
            os.remove(env_file)
            print("  \033[33m[OK] Anonymous mode STOPPED\033[0m")
        else:
            proxy = "socks5://127.0.0.1:9050"
            os.makedirs(os.path.dirname(env_file), exist_ok=True)
            with open(env_file, "w") as f:
                f.write(f"HTTP_PROXY={proxy}\nHTTPS_PROXY={proxy}\nALL_PROXY={proxy}\n")
                f.write(f"http_proxy={proxy}\nhttps_proxy={proxy}\nall_proxy={proxy}\n")
                f.write("NO_PROXY=localhost,127.0.0.1,::1\n")
            print("  \033[32m[OK] Anonymous mode STARTED\033[0m")

    else:
        print("  usage: anonsurf [start|stop|status|toggle]")
        print("  Routes system HTTP/HTTPS traffic through Tor proxy")
        print()
        print("  Examples:")
        print("    anonsurf start   -- set proxy env vars")
        print("    anonsurf stop    -- clear proxy env vars")
        print("    anonsurf status  -- show current state")


def register(commands, aliases):
    commands.update({
        "proxychains": _cmd_proxychains,
        "macchanger": _cmd_macchanger,
        "anonsurf": _cmd_anonsurf,
    })
    aliases.update({
        "proxychains": "proxychains",
        "macchanger": "macchanger",
        "mac": "macchanger -s",
        "anonsurf": "anonsurf",
    })
    return commands, aliases
