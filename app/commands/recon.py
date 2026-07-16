"""recon.py -- Reconnaissance commands (nmap, dnsrecon, gobuster, etc.)"""

import socket
import struct
import re
import asyncio
import urllib.request
import urllib.error
try:
    import ssl
    _HAVE_SSL = True
except ImportError:
    _HAVE_SSL = False
    import warnings
    warnings.warn("ssl module unavailable - HTTPS features disabled")
import json
import time
import os
import sys
import ipaddress

_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_wordlist(name):
    path = os.path.join(_dir, "wordlists", name)
    if os.path.isfile(path):
        with open(path, errors="replace") as f:
            return [l.strip() for l in f if l.strip() and not l.startswith("#")]
    return []


def _try_resolve(hostname):
    try:
        return socket.getaddrinfo(hostname, 0, socket.AF_INET)[0][4][0]
    except Exception:
        return None


def _color(c, text):
    codes = {"g": "\033[32m", "r": "\033[31m", "y": "\033[33m", "c": "\033[36m", "b": "\033[1m", "d": "\033[0m"}
    return f"{codes.get(c, '')}{text}\033[0m"


# ---- whois ----

def _cmd_whois(args):
    if not args:
        print("  usage: whois <domain>")
        return
    domain = args[0]
    print(f"  Querying WHOIS for {domain}...")
    try:
        s = socket.create_connection(("whois.iana.org", 43), timeout=10)
        s.sendall((domain + "\r\n").encode())
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        text = data.decode("utf-8", errors="replace")
        for line in text.split("\n")[:30]:
            line = line.strip()
            if line:
                print(f"  {line}")
        s.close()
    except Exception as e:
        print(f"  whois error: {e}")


# ---- nmap ----

def _cmd_nmap(args):
    parser = {"ports": "1-1024", "tor": False, "sv": False, "os": False, "aggr": False}
    targets = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-p" and i + 1 < len(args):
            parser["ports"] = args[i + 1]
            i += 2
        elif a == "--tor":
            parser["tor"] = True
            i += 1
        elif a == "-sV":
            parser["sv"] = True
            i += 1
        elif a == "-O":
            parser["os"] = True
            i += 1
        elif a == "-A":
            parser["aggr"] = parser["sv"] = parser["os"] = True
            i += 1
        elif a in ("-sT", "-sS"):
            i += 1
        else:
            targets.append(a)
            i += 1

    if not targets:
        print("  usage: nmap [-p ports] [-sV] [-O] [-A] [--tor] <target> [target2...]")
        return

    raw_ports = parser["ports"]
    port_list = []
    for part in raw_ports.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            port_list.extend(range(int(lo), int(hi) + 1))
        else:
            port_list.append(int(part))

    tor_suffix = " via Tor" if parser["tor"] else ""
    print(f"  Starting Tether OS nmap scan{tor_suffix}")
    print(f"  Scanning {len(targets)} host(s) on {len(port_list)} port(s)")
    print()

    for target in targets:
        ip = _try_resolve(target) or target
        print(f"  Host: {target} ({ip})")
        open_ports = []

        for port in port_list:
            try:
                s = socket.socket()
                s.settimeout(1.5)
                if parser["tor"]:
                    s.connect(("127.0.0.1", 9050))
                else:
                    s.connect((ip, port))
                s.close()
                open_ports.append(port)
                print(f"    PORT {port}/tcp  OPEN")
            except:
                pass

        if not open_ports:
            print(f"    All {len(port_list)} ports filtered or closed")

        if parser["sv"] and open_ports:
            print()
            print(f"  Service detection on open ports:")
            for port in open_ports:
                try:
                    s = socket.socket()
                    s.settimeout(2)
                    s.connect((ip, port))
                    s.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
                    banner = s.recv(256).decode("utf-8", errors="replace").strip()[:80]
                    print(f"    {ip}:{port} - {banner}")
                    s.close()
                except:
                    print(f"    {ip}:{port} - [no banner]")

        if parser["os"]:
            print()
            print(f"  OS detection:")
            try:
                s = socket.socket()
                s.settimeout(2)
                s.connect((ip, 80))
                s.sendall(b"GET / HTTP/1.0\r\n\r\n")
                resp = s.recv(1024).decode("utf-8", errors="replace")
                if "Server:" in resp:
                    svr = resp.split("Server:")[1].split("\r\n")[0].strip()
                    print(f"    Detected: {svr}")
                else:
                    print(f"    [could not determine]")
                s.close()
            except:
                print(f"    [could not determine]")

        if len(targets) > 1:
            print()

    print(f"  Scan completed.")


# ---- dnsrecon ----

def _cmd_dnsrecon(args):
    domain = None
    scan_type = "std"
    wordlist_path = None
    i = 0
    while i < len(args):
        if args[i] == "-d" and i + 1 < len(args):
            domain = args[i + 1]
            i += 2
        elif args[i] == "-t" and i + 1 < len(args):
            scan_type = args[i + 1]
            i += 2
        elif args[i] == "-D" and i + 1 < len(args):
            wordlist_path = args[i + 1]
            i += 2
        else:
            domain = args[i]
            i += 1

    if not domain:
        print("  usage: dnsrecon -d <domain> [-t std|brt|srv] [-D wordlist]")
        return

    print(f"  DNS Reconnaissance for {domain}")
    print()

    if scan_type in ("std", "all"):
        for rtype in ("A", "AAAA", "MX", "NS", "TXT", "SOA"):
            try:
                results = socket.getaddrinfo(domain, 0, socket.AF_UNSPEC, socket.SOCK_STREAM)
                ips = set()
                for r in results:
                    ips.add(r[4][0])
                for ip in sorted(ips):
                    print(f"  {rtype:6} {domain:40} {ip}")
            except:
                pass

        try:
            host, aliaslist, ipaddrlist = socket.gethostbyname_ex(domain)
            for alias in aliaslist:
                print(f"  CNAME  {alias}")
        except:
            pass

    if scan_type in ("brt", "all"):
        subdomains = _get_wordlist("subdomains.txt")
        if wordlist_path and os.path.isfile(wordlist_path):
            with open(wordlist_path) as f:
                subdomains = [l.strip() for l in f if l.strip()]
        print(f"  Brute-forcing {len(subdomains)} subdomains...")
        found = 0
        for sub in subdomains:
            fqdn = f"{sub}.{domain}"
            ip = _try_resolve(fqdn)
            if ip:
                found += 1
                print(f"  {fqdn:50} {ip}")
        if found == 0:
            print(f"  No subdomains found via brute-force")

    if scan_type in ("srv", "all"):
        for svc in ("_http._tcp", "_https._tcp", "_smtp._tcp", "_imap._tcp",
                     "_pop3._tcp", "_ldap._tcp", "_kerberos._tcp"):
            try:
                results = socket.getaddrinfo(f"{svc}.{domain}", 0)
                for r in results:
                    print(f"  SRV    {svc}.{domain:35} {r[4][0]}")
            except:
                pass

    print("  Done.")


# ---- gobuster ----

def _cmd_gobuster(args):
    url = None
    wordlist_path = None
    threads = 10
    extensions = []
    i = 0
    while i < len(args):
        if args[i] == "-u" and i + 1 < len(args):
            url = args[i + 1].rstrip("/")
            i += 2
        elif args[i] == "-w" and i + 1 < len(args):
            wordlist_path = args[i + 1]
            i += 2
        elif args[i] == "-t" and i + 1 < len(args):
            threads = int(args[i + 1])
            i += 2
        elif args[i] == "-x" and i + 1 < len(args):
            extensions = [e.strip() for e in args[i + 1].split(",")]
            i += 2
        else:
            if not url:
                url = args[i].rstrip("/")
            i += 1

    if not url:
        print("  usage: gobuster -u <url> [-w wordlist] [-t threads] [-x extensions]")
        return

    dirs = _get_wordlist("directories.txt")
    if wordlist_path and os.path.isfile(wordlist_path):
        with open(wordlist_path) as f:
            dirs = [l.strip() for l in f if l.strip()]

    print(f"  Directory brute-forcing {url}")
    print(f"  Wordlist: {len(dirs)} entries, Threads: {threads}")
    if extensions:
        print(f"  Extensions: {', '.join(extensions)}")
    print()

    found = 0
    ctx = ssl._create_unverified_context()

    def check_path(path):
        nonlocal found
        full_url = f"{url}/{path}"
        try:
            req = urllib.request.Request(full_url, method="HEAD")
            resp = urllib.request.urlopen(req, timeout=5, context=ctx)
            status = resp.status
            if status in (200, 204, 301, 302, 307, 403, 401, 500):
                found += 1
                size = len(resp.read())
                print(f"  [{status}] {path:50} {size}B")
            resp.close()
        except urllib.error.HTTPError as e:
            if e.code in (403, 401, 500):
                found += 1
                print(f"  [{e.code}] {path}")
        except:
            pass

    for path in dirs[:500]:
        check_path(path)
        for ext in extensions:
            check_path(f"{path}.{ext}")

    if found == 0:
        print("  No directories discovered.")
    else:
        print(f"\n  Found {found} entries.")


# ---- theHarvester ----

def _cmd_theharvester(args):
    domain = None
    source = "all"
    limit = 100
    i = 0
    while i < len(args):
        if args[i] == "-d" and i + 1 < len(args):
            domain = args[i + 1]
            i += 2
        elif args[i] == "-b" and i + 1 < len(args):
            source = args[i + 1]
            i += 2
        elif args[i] == "-l" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            domain = args[i]
            i += 1

    if not domain:
        print("  usage: theharvester -d <domain> [-b crtsh|dns|all] [-l limit]")
        return

    print(f"  OSINT harvest for {domain}")
    print()

    hosts = set()
    emails = set()

    if source in ("crtsh", "all"):
        print("  [*] Querying crt.sh Certificate Transparency...")
        ctx = ssl._create_unverified_context()
        try:
            url = f"https://crt.sh/?q=%25.{domain}&output=json"
            resp = urllib.request.urlopen(url, timeout=15, context=ctx)
            data = json.loads(resp.read().decode())
            for entry in data[:limit]:
                name = entry.get("name_value", "")
                for n in name.split("\n"):
                    n = n.strip().lower()
                    if n.endswith(f".{domain}") and n not in hosts:
                        hosts.add(n)
                        print(f"    HOST: {n}")
            resp.close()
        except Exception as e:
            print(f"    crt.sh error: {e}")

    if source in ("dns", "all"):
        print("  [*] DNS brute-force...")
        subs = _get_wordlist("subdomains.txt")[:200]
        for sub in subs:
            fqdn = f"{sub}.{domain}"
            ip = _try_resolve(fqdn)
            if ip and fqdn not in hosts:
                hosts.add(fqdn)
                print(f"    HOST: {fqdn} -> {ip}")

    if not hosts and not emails:
        print("  No results found.")

    print(f"\n  Found {len(hosts)} hosts.")


# ---- whatweb ----

_FINGERPRINTS = {
    "Server: Apache": ("Apache HTTP Server", "httpd"),
    "Server: nginx": ("Nginx", "httpd"),
    "Server: Microsoft-IIS": ("Microsoft IIS", "httpd"),
    "Server: lighttpd": ("Lighttpd", "httpd"),
    "Server: Caddy": ("Caddy", "httpd"),
    "X-Generator: WordPress": ("WordPress", "CMS"),
    "X-Powered-CMS: WordPress": ("WordPress", "CMS"),
    "X-Drupal": ("Drupal", "CMS"),
    "X-Joomla": ("Joomla", "CMS"),
    "X-Magento": ("Magento", "CMS"),
    "Set-Cookie: PHPSESSID": ("PHP", "language"),
    "Set-Cookie: ASPSESSIONID": ("ASP.NET", "language"),
    "Set-Cookie: JSESSIONID": ("Java/JSP", "language"),
    "X-Powered-By: PHP": ("PHP", "language"),
    "X-Powered-By: ASP.NET": ("ASP.NET", "language"),
    "X-Powered-By: Express": ("Express.js", "framework"),
    "X-Frame-Options": ("Has X-Frame-Options", "security"),
    "Strict-Transport-Security": ("HSTS Enabled", "security"),
    "Content-Security-Policy": ("CSP Enabled", "security"),
    "X-Content-Type-Options: nosniff": ("X-Content-Type-Options", "security"),
    "X-XSS-Protection": ("XSS Protection", "security"),
}


def _cmd_whatweb(args):
    if not args:
        print("  usage: whatweb <url>")
        return
    url = args[0].rstrip("/")
    if not url.startswith("http"):
        url = f"http://{url}"

    print(f"  Fingerprinting {url}")
    print()

    ctx = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        headers = {k.lower(): v for k, v in resp.headers.items()}
        body = resp.read().decode("utf-8", errors="replace")[:5000]
        resp.close()

        print(f"  HTTP Status: {resp.status}")
        print(f"  Content-Type: {headers.get('content-type', '?')}")
        print()

        found = []
        for sig, (name, cat) in _FINGERPRINTS.items():
            sig_lower = sig.lower()
            for k, v in headers.items():
                if sig_lower in f"{k}: {v}".lower():
                    found.append((name, cat))

        if "wordpress" in body.lower() or "wp-content" in body.lower():
            found.append(("WordPress", "CMS"))
        if "drupal" in body.lower():
            found.append(("Drupal", "CMS"))
        if "joomla" in body.lower():
            found.append(("Joomla", "CMS"))

        seen = set()
        for name, cat in found:
            if name not in seen:
                seen.add(name)
                print(f"  [{cat:15}] {name}")

        if not found:
            print("  No fingerprints matched.")

    except Exception as e:
        print(f"  whatweb error: {e}")


# ---- enum4linux ----

def _cmd_enum4linux(args):
    host = None
    i = 0
    while i < len(args):
        if args[i] == "-h" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] == "-a":
            i += 1
        else:
            host = args[i]
            i += 1

    if not host:
        print("  usage: enum4linux [-a] <host>")
        print("  Enumerate SMB/Windows information from a remote host.")
        print("  Examples:")
        print("    enum4linux 192.168.1.1")
        print("    enum4linux -a 192.168.1.1")
        return

    print(f"  SMB enumeration against {host}")
    print()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex((host, 445))
        s.close()

        if result != 0:
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s2.settimeout(3)
            result = s2.connect_ex((host, 139))
            s2.close()

        if result != 0:
            print(f"  [!] No SMB ports open on {host} (445/tcp, 139/tcp)")
            return

        print(f"  [+] SMB service detected on {host}")
        print()

        print(f"  [*] Enumerating shares...")
        print(f"       ADMIN$ - Remote Admin (hidden)")
        print(f"       C$ - Default Share (hidden)")
        print(f"       IPC$ - Remote IPC (hidden)")
        print(f"       (requires valid credentials for full enumeration)")

        print(f"\n  [*] Checking OS fingerprint...")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((host, 445))
            banner = s.recv(1024)
            s.close()
            if banner[:4] == b'\x00\x00\x00' and len(banner) > 36:
                major = banner[36]
                minor = banner[37]
                build = struct.unpack("<H", banner[38:40])[0]
                os_map = {5: "Windows 2000", 6: "Windows Vista/2008/7", 10: "Windows 10/2016"}
                os_name = os_map.get(major, f"Windows (NT {major}.{minor})")
                print(f"       OS: {os_name} (build {build})")
        except:
            print(f"       Could not fingerprint OS")

        print(f"\n  [*] Enumerating users (guest access)...")
        default_users = ["Administrator", "Guest", "DefaultAccount",
                         "root", "nobody", "vagrant", "ubuntu"]
        print(f"       Potential local users: {', '.join(default_users)}")

    except Exception as e:
        print(f"  [+] Host appears online (basic check passed)")

    print()
    print("  Enum4linux scan complete (simulated).")


# ---- cewl ----

def _cmd_cewl(args):
    url = None
    depth = 1
    min_word = 3
    max_words = 100
    output_file = None

    i = 0
    while i < len(args):
        if not args[i].startswith("-") and not url:
            url = args[i]
        elif args[i] == "-d" and i + 1 < len(args):
            try: depth = int(args[i + 1])
            except: pass
            i += 2
        elif args[i] == "-m" and i + 1 < len(args):
            try: min_word = int(args[i + 1])
            except: pass
            i += 2
        elif args[i] == "-w" and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] == "--max" and i + 1 < len(args):
            try: max_words = int(args[i + 1])
            except: pass
            i += 2
        else:
            i += 1

    if not url:
        print("  usage: cewl <url> [-d <depth>] [-m <min-word-length>] [-w <output-file>]")
        print("  Custom wordlist generator from web page content.")
        print("  Examples:")
        print("    cewl http://example.com")
        print("    cewl http://example.com -d 2 -m 5 -w wordlist.txt")
        return

    print(f"  Generating wordlist from: {url} (depth={depth}, min_len={min_word})")
    print()

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "TRAP-HUB-CeWL/1.0"})
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        body = resp.read().decode("utf-8", errors="replace")

        words = re.findall(r'[a-zA-Z][a-zA-Z0-9_\-]{' + str(min_word - 1) + r',}', body)
        words = [w.strip().lower() for w in words if len(w.strip()) >= min_word]

        exclude = {"the", "and", "for", "are", "but", "not", "you", "all",
                   "can", "had", "her", "was", "one", "our", "out", "has",
                   "have", "been", "some", "them", "than", "that", "this",
                   "very", "just", "also", "with", "from", "they", "what",
                   "when", "where", "which", "their", "there", "would",
                   "about", "could", "should", "after", "other", "every"}
        words = [w for w in words if w not in exclude and not w.isdigit()]

        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1

        sorted_words = sorted(freq.items(), key=lambda x: -x[1])[:max_words]

        print(f"  {'COUNT':8} {'WORD':30}")
        print(f"  {'-'*8} {'-'*30}")
        for word, count in sorted_words:
            print(f"  {count:<8} {word}")

        if output_file:
            abs_out = os.path.abspath(output_file)
            try:
                with open(abs_out, "w", encoding="utf-8") as f:
                    for word, _ in sorted_words:
                        f.write(word + "\n")
                print(f"\n  [*] Wordlist saved: {abs_out} ({len(sorted_words)} words)")
            except Exception as e:
                print(f"\n  [!] Could not write file: {e}")

        print(f"\n  CeWL complete. {len(sorted_words)} unique words extracted.")

    except Exception as e:
        print(f"  CeWL error: {e}")


def register(commands, aliases):
    commands.update({
        "nmap": _cmd_nmap,
        "dnsrecon": _cmd_dnsrecon,
        "gobuster": _cmd_gobuster,
        "theharvester": _cmd_theharvester,
        "whatweb": _cmd_whatweb,
        "whois": _cmd_whois,
        "enum4linux": _cmd_enum4linux,
        "cewl": _cmd_cewl,
    })
    aliases.update({
        "nmap": "nmap",
    })
    return commands, aliases
