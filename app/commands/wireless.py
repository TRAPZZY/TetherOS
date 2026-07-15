"""wireless.py -- Wireless network tools for TRAP HUB"""

import sys
import os
import re
import subprocess
import json


def register(cmds, aliases):
    cmds["iwconfig"] = _cmd_iwconfig
    cmds["airmon-ng"] = _cmd_airmon
    cmds["airodump-ng"] = _cmd_airodump


def _usage(name):
    help_texts = {
        "iwconfig": "usage: iwconfig\n  Show wireless interface information.\n  Uses netsh to display Wi-Fi adapter details.",
        "airmon-ng": "usage: airmon-ng <start|stop|check> <interface>\n  Wireless monitor mode control (simulated on Windows).\n  Examples:\n    airmon-ng check\n    airmon-ng start wlan0",
        "airodump-ng": "usage: airodump-ng <interface>\n  Wi-Fi network scanning.\n  Uses netsh wlan show networks mode=bssid.\n  Examples:\n    airodump-ng wlan0",
    }
    print(f"  {help_texts.get(name, '')}")


def _netsh_output(*args):
    try:
        result = subprocess.run(
            ["netsh"] + list(args),
            capture_output=True, text=True, timeout=10, shell=True
        )
        return result.stdout
    except:
        return ""


def _cmd_iwconfig(args):
    if "-h" in args or "--help" in args:
        _usage("iwconfig")
        return

    print("  Wireless interfaces (from netsh):")
    print()

    output = _netsh_output("wlan", "show", "interfaces")
    if not output.strip():
        print("  No wireless interfaces found.")
        return

    current = {}
    for line in output.split("\n"):
        m = re.match(r'^\s+([^:]+):\s+(.+)$', line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            current[key] = val

    name = current.get("Name", "?")
    desc = current.get("Description", "?")
    guid = current.get("GUID", "?")
    state = current.get("State", "?")
    ssid = current.get("SSID", "?")
    signal = current.get("Signal", "?")
    rate = current.get("Receive rate", current.get("Transmit rate", "?"))

    if name != "?":
        print(f"  {name}")
        print(f"    Description: {desc}")
        print(f"    State:       {state}")
        print(f"    SSID:        {ssid}")
        print(f"    Signal:      {signal}%")
        print(f"    Rate:        {rate}")
        print(f"    GUID:        {guid}")
    else:
        print("  No active Wi-Fi adapter detected.")


def _cmd_airmon(args):
    if not args or "-h" in args:
        _usage("airmon-ng")
        return

    action = args[0].lower()
    iface = args[1] if len(args) > 1 else "wlan0"

    if action == "check":
        print("  Checking for wireless interfaces...")
        output = _netsh_output("wlan", "show", "interfaces")
        if "State" in output:
            print(f"  Interface {iface}: available")
        else:
            print(f"  No wireless interfaces found.")

    elif action == "start":
        print(f"  Attempting to enable monitor mode on {iface}...")
        print(f"  [!] Monitor mode is not supported on Windows via netsh.")
        print(f"  [*] Use a Linux VM or WSL for airodump-ng/aircrack-ng.")
        print(f"  [*] However, you can scan networks with: iwconfig")

    elif action == "stop":
        print(f"  Monitor mode disable requested for {iface}")
        print(f"  (No changes made -- monitor mode was not active)")

    else:
        _usage("airmon-ng")


def _cmd_airodump(args):
    if not args or "-h" in args:
        _usage("airodump-ng")
        return

    iface = args[0]
    print(f"  Scanning for Wi-Fi networks on {iface}...")
    print(f"  (using netsh wlan show networks mode=bssid)")
    print()

    output = _netsh_output("wlan", "show", "networks", "mode=bssid")
    if not output.strip():
        print("  No networks found or Wi-Fi is disabled.")
        return

    lines = output.split("\n")
    print(f"  {'SSID':30} {'SIGNAL':8} {'CHANNEL':8} {'AUTH':20}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*20}")

    current_ssid = None
    for line in lines:
        m = re.match(r'^\s+SSID\s+\d+\s+:\s+(.+)$', line)
        if m:
            current_ssid = m.group(1).strip()
            continue
        if current_ssid:
            m = re.match(r'^\s+Signal\s+:\s+(\d+)%', line)
            if m:
                sig = m.group(1).strip()
            m = re.match(r'^\s+Channel\s+:\s+(\d+)', line)
            if m:
                ch = m.group(1).strip()
            m = re.match(r'^\s+Authentication\s+:\s+(.+)$', line)
            if m:
                auth = m.group(1).strip()
                print(f"  {current_ssid:30} {sig+'%':8} {ch:8} {auth:20}")
                current_ssid = None

    print()
    print("  Scan complete.")
