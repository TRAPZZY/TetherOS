"""scan.py -- Vulnerability scanning tools (nikto, nuclei)"""

import sys
import urllib.request
import urllib.error
import socket
try:
    import ssl
    _HAVE_SSL = True
except ImportError:
    _HAVE_SSL = False
    import warnings
    warnings.warn("ssl module unavailable - HTTPS features disabled")
import json
import time
import re


NUCLEI_TEMPLATES = [
    {"id": "tech-detect", "name": "Technology Detection", "severity": "info",
     "checks": [
         {"match": "server: nginx", "name": "Nginx"},
         {"match": "server: apache", "name": "Apache HTTPD"},
         {"match": "server: cloudflare", "name": "Cloudflare"},
         {"match": "x-powered-by: php", "name": "PHP"},
         {"match": "x-powered-by: asp", "name": "ASP.NET"},
         {"match": "x-generator: wordpress", "name": "WordPress"},
         {"match": "x-generator: joomla", "name": "Joomla"},
         {"match": "x-generator: drupal", "name": "Drupal"},
     ]},
    {"id": "missing-headers", "name": "Missing Security Headers", "severity": "medium",
     "headers": ["strict-transport-security", "x-content-type-options",
                  "x-frame-options", "x-xss-protection",
                  "content-security-policy", "referrer-policy"]},
    {"id": "open-port", "name": "Open Port Detection", "severity": "info",
     "ports": [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 1433, 1521, 3306, 3389, 5432, 6379, 8443, 27017]},
]


def register(cmds, aliases):
    cmds["nikto"] = _cmd_nikto
    cmds["nuclei"] = _cmd_nuclei


def _usage(name):
    help_texts = {
        "nikto": "usage: nikto -h <host> [-p <port>] [-ssl]\n  Web server vulnerability scanner.\n  Examples:\n    nikto -h example.com\n    nikto -h 192.168.1.1 -p 8443 -ssl",
        "nuclei": "usage: nuclei -u <url> [-t <template>] [-o json]\n  Template-based vulnerability scanner.\n  Examples:\n    nuclei -u http://example.com\n    nuclei -u https://example.com -t tech-detect",
    }
    print(f"  {help_texts.get(name, '')}")


def _fetch_url(url, timeout=10):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TRAP-HUB-Scanner/1.0"})
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        headers = dict(resp.headers)
        body = resp.read().decode("utf-8", errors="replace")[:5000]
        return {"status": resp.status, "headers": headers, "body": body, "url": url}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "headers": dict(e.headers), "body": "", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


def _cmd_nikto(args):
    host = None
    port = 80
    use_ssl = False
    i = 0
    while i < len(args):
        if args[i] == "-h" and i + 1 < len(args):
            host = args[i + 1].lower().strip("/").replace("http://", "").replace("https://", "")
            i += 2
        elif args[i] == "-p" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except:
                pass
            i += 2
        elif args[i] == "-ssl":
            use_ssl = True
            i += 1
        else:
            i += 1

    if not host:
        _usage("nikto")
        return

    protocol = "https" if use_ssl or port == 443 else "http"
    url = f"{protocol}://{host}:{port}/"
    print(f"  Nikto-like scan: {url}")
    print()

    result = _fetch_url(url)
    if "error" in result:
        print(f"  [!] Connection failed: {result['error']}")
        return

    print(f"  [*] Server response: {result['status']}")
    server = result["headers"].get("Server", result["headers"].get("server", "unknown"))
    print(f"  [*] Server: {server}")
    print()

    issues = []

    server_lower = server.lower()
    if server_lower:
        checks = [
            ("nginx/1." in server_lower and any(v in server_lower for v in ["0.", "1.0.", "1.1.", "1.2.", "1.3.", "1.4."]),
             f"Possible outdated Nginx version: {server}"),
            ("apache/2." in server_lower and any(v in server_lower for v in ["2.0.", "2.1.", "2.2."]),
             f"Possible outdated Apache version: {server}"),
            ("iis/" in server_lower and any(v in server_lower for v in ["6.", "7."]),
             f"Possible outdated IIS version: {server}"),
        ]
        for cond, msg in checks:
            if cond:
                issues.append(("MEDIUM", msg))

    sec_headers = ["strict-transport-security", "x-content-type-options",
                   "x-frame-options", "x-xss-protection", "content-security-policy"]
    missing = [h for h in sec_headers if h not in result["headers"] and h.replace("-", "_") not in result["headers"]]
    if missing:
        issues.append(("LOW", f"Missing security headers: {', '.join(missing[:4])}"))

    if result["status"] == 200:
        body_lower = result["body"].lower()
        if "wp-content" in body_lower:
            issues.append(("INFO", "WordPress installation detected"))
        if "drupal" in body_lower:
            issues.append(("INFO", "Drupal installation detected"))
        if "joomla" in body_lower:
            issues.append(("INFO", "Joomla installation detected"))

    common_paths = ["/admin", "/login", "/wp-admin", "/phpmyadmin",
                    "/.git/config", "/.env", "/backup", "/robots.txt"]
    for path in common_paths:
        check_url = f"{protocol}://{host}:{port}{path}"
        try:
            cr = _fetch_url(check_url, timeout=5)
            if cr.get("status") == 200:
                issues.append(("MEDIUM", f"Interesting path revealed: {path}"))
        except:
            pass

    if not issues:
        issues.append(("INFO", "No obvious vulnerabilities detected (basic scan)"))

    severity_colors = {"HIGH": "\033[31m", "MEDIUM": "\033[33m", "LOW": "\033[36m", "INFO": "\033[32m"}
    for sev, desc in issues:
        color = severity_colors.get(sev, "\033[0m")
        reset = "\033[0m"
        print(f"  {color}[{sev}]{reset} {desc}")

    print()
    print("  Nikto scan complete.")


def _cmd_nuclei(args):
    url = None
    template_id = None
    output_json = False
    i = 0
    while i < len(args):
        if args[i] == "-u" and i + 1 < len(args):
            url = args[i + 1].rstrip("/")
            i += 2
        elif args[i] == "-t" and i + 1 < len(args):
            template_id = args[i + 1].lower()
            i += 2
        elif args[i] == "-o" and i + 1 < len(args) and args[i + 1] == "json":
            output_json = True
            i += 2
        else:
            i += 1

    if not url:
        _usage("nuclei")
        return

    print(f"  Nuclei scan: {url}")
    print()

    result = _fetch_url(url)
    if "error" in result:
        print(f"  [!] Connection failed: {result['error']}")
        return

    findings = []

    for tmpl in NUCLEI_TEMPLATES:
        if template_id and tmpl["id"] != template_id:
            continue

        if "checks" in tmpl:
            for check in tmpl["checks"]:
                header_text = json.dumps(result["headers"]).lower()
                body_lower = result["body"].lower()
                match_val = check["match"].lower()
                if match_val in header_text or match_val in body_lower:
                    findings.append({
                        "template": tmpl["id"],
                        "name": check["name"],
                        "severity": tmpl["severity"],
                        "matched": check["match"],
                    })

        if "headers" in tmpl:
            missing = [h for h in tmpl["headers"] if h not in result["headers"]
                       and h.replace("-", "_") not in result["headers"]]
            for h in missing:
                findings.append({
                    "template": tmpl["id"],
                    "name": f"Missing header: {h}",
                    "severity": tmpl["severity"],
                    "matched": h,
                })

        if "ports" in tmpl:
            for p in tmpl["ports"][:10]:
                try:
                    s = socket.socket()
                    s.settimeout(1)
                    if s.connect_ex((url.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0], p)) == 0:
                        findings.append({
                            "template": tmpl["id"],
                            "name": f"Port {p} open",
                            "severity": "info",
                            "matched": f"tcp/{p}",
                        })
                    s.close()
                except:
                    pass

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 5))

    sev_colors = {"critical": "\033[31m", "high": "\033[31m", "medium": "\033[33m",
                  "low": "\033[36m", "info": "\033[32m"}

    if output_json:
        print(json.dumps({"target": url, "findings": findings}, indent=2))

    if not findings:
        print("  No findings from active templates.")
        print(f"  {len(NUCLEI_TEMPLATES)} templates loaded, 0 matches.")
    else:
        print(f"  {'TEMPLATE':20} {'SEVERITY':10} {'FINDING':40}")
        print(f"  {'-'*20} {'-'*10} {'-'*40}")
        for f in findings:
            sev = f["severity"].ljust(10)
            sev_display = f"{sev_colors.get(f['severity'], '')}{sev}\033[0m"
            print(f"  {f['template']:20} {sev_display} {f['name']}")
        print()
        print(f"  {len(findings)} finding(s) from {len(NUCLEI_TEMPLATES)} templates.")

    print("  Nuclei scan complete.")
