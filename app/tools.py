"""tools.py -- Built-in tools for Tether OS shell"""

import subprocess
import socket
import sys
import os
import json
import time
import shutil
import struct

from lib.network import open_url


class Tools:
    @staticmethod
    def dns_leak_test():
        results = []
        test_domains = ["https://httpbin.org/ip", "https://ifconfig.me/ip"]
        for url in test_domains:
            try:
                with open_url(url, timeout=10) as resp:
                    payload = resp.read().decode().strip()
                results.append({"url": url, "ip": payload, "leak": False, "transport": "tor"})
            except Exception as e:
                results.append({"url": url, "error": str(e), "leak": True})
        return results

    @staticmethod
    def connection_test():
        status = {}
        try:
            s = socket.create_connection(("127.0.0.1", 9050), timeout=3)
            s.close()
            status["socks_port"] = True
        except Exception:
            status["socks_port"] = False
        try:
            s = socket.create_connection(("127.0.0.1", 9051), timeout=3)
            s.close()
            status["control_port"] = True
        except Exception:
            status["control_port"] = False
        try:
            with open_url("https://api.ipify.org", timeout=10) as resp:
                ext_ip = resp.read().decode().strip()
            status["external_ip"] = ext_ip
            status["tor_working"] = True
        except Exception:
            status["tor_working"] = False
            status["external_ip"] = None
        return status

    @staticmethod
    def geo_lookup(ip=None):
        if not ip:
            try:
                with open_url("https://api.ipify.org", timeout=10) as resp:
                    ip = resp.read().decode().strip()
            except Exception:
                return {"error": "Could not determine IP"}
        try:
            with open_url(
                f"http://ip-api.com/json/{ip}?fields=query,country,regionName,city,isp,org,as,mobile,proxy,hosting",
                timeout=10,
            ) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def system_info():
        import platform
        return {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "hostname": platform.node(),
        }

    @staticmethod
    def mac_info():
        info = {}
        if sys.platform == "win32":
            try:
                r = subprocess.run(
                    ["ipconfig", "/all"],
                    capture_output=True, text=True, timeout=10,
                )
                lines = r.stdout.split("\n")
                adapters = []
                current = {}
                for line in lines:
                    line = line.strip()
                    if "adapter" in line.lower() and ":" in line:
                        if current:
                            adapters.append(current)
                        current = {"name": line.split(":")[0].strip()}
                    elif "Physical Address" in line or "MAC" in line and ":" in line:
                        current["mac"] = line.split(":")[-1].strip()
                    elif "IPv4 Address" in line:
                        import re
                        ip_match = re.search(r"\d+\.\d+\.\d+\.\d+", line)
                        if ip_match:
                            current["ip"] = ip_match.group()
                if current:
                    adapters.append(current)
                info["adapters"] = adapters[:5]
            except Exception:
                info["error"] = "Could not retrieve MAC info"
        else:
            try:
                r = subprocess.run(
                    ["ifconfig"], capture_output=True, text=True, timeout=10,
                )
                info["raw"] = r.stdout[:500]
            except Exception:
                info["error"] = "ifconfig not available"
        return info

    @staticmethod
    def speed_test():
        result = {}
        test_url = "https://httpbin.org/bytes/1024"
        try:
            start = time.time()
            with open_url(test_url, timeout=15) as resp:
                data = resp.read()
            elapsed = time.time() - start
            size_kb = len(data) / 1024
            speed = size_kb / elapsed if elapsed > 0 else 0
            result["download_kb"] = round(size_kb, 2)
            result["time_seconds"] = round(elapsed, 2)
            result["speed_kbps"] = round(speed, 2)
        except Exception as e:
            result["error"] = str(e)
        return result

    @staticmethod
    def kill_switch(state=None):
        if sys.platform == "win32":
            return {"error": "The kernel kill switch is only available inside the Tether OS Linux image"}
        script = "/etc/init.d/S01iptables"
        if state is not None:
            if not os.path.isfile(script):
                return {"error": "Tether OS firewall service is not installed on this host"}
            action = "start" if state else "stop"
            result = subprocess.run([script, action], capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return {"error": result.stderr.strip() or result.stdout.strip() or "firewall command failed"}
        try:
            result = subprocess.run(
                ["iptables", "-S", "OUTPUT"], capture_output=True, text=True, timeout=5
            )
            enabled = result.returncode == 0 and "-P OUTPUT DROP" in result.stdout
            return {"status": "enabled" if enabled else "disabled"}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {"error": "iptables is unavailable"}
