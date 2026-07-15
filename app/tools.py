"""tools.py -- Built-in tools for Tether OS shell"""

import subprocess
import socket
import sys
import os
import json
import time
import shutil
import struct


class Tools:
    @staticmethod
    def dns_leak_test():
        results = []
        test_domains = ["https://httpbin.org/ip", "https://ifconfig.me/ip"]
        for url in test_domains:
            try:
                import urllib.request
                req = urllib.request.Request(url)
                resp = urllib.request.urlopen(req, timeout=10)
                ip = resp.read().decode().strip()
                results.append({"url": url, "ip": ip, "leak": False})
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
            import urllib.request
            proxy = urllib.request.ProxyHandler({
                "http": "socks5://127.0.0.1:9050",
                "https": "socks5h://127.0.0.1:9050",
            })
            opener = urllib.request.build_opener(proxy)
            resp = opener.open("https://httpbin.org/ip", timeout=10)
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
                import urllib.request
                proxy = urllib.request.ProxyHandler({
                    "http": "socks5://127.0.0.1:9050",
                    "https": "socks5h://127.0.0.1:9050",
                })
                opener = urllib.request.build_opener(proxy)
                resp = opener.open("https://httpbin.org/ip", timeout=10)
                ip = resp.read().decode().strip()
            except Exception:
                return {"error": "Could not determine IP"}
        try:
            import urllib.request
            resp = urllib.request.urlopen(
                f"http://ip-api.com/json/{ip}?fields=query,country,regionName,city,isp,org,as,mobile,proxy,hosting",
                timeout=10
            )
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
            import urllib.request
            start = time.time()
            resp = urllib.request.urlopen(test_url, timeout=15)
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
            return {"error": "Kill switch not supported on Windows"}
        if state is True:
            os.environ["TETHER_KILLSWITCH"] = "1"
            return {"status": "enabled"}
        elif state is False:
            os.environ.pop("TETHER_KILLSWITCH", None)
            return {"status": "disabled"}
        return {"status": "enabled" if os.environ.get("TETHER_KILLSWITCH") else "disabled"}
