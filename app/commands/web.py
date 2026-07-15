"""web.py -- Web application testing tools (wpscan)"""

import sys
import urllib.request
import urllib.error
import ssl
import re
import time


WP_VERSION_PATTERNS = [
    (r'<meta name="generator" content="WordPress ([^"]+)"', "generator_meta"),
    (r'ver=([0-9.]+)', "query_string"),
    (r'/wp-content/themes/[^/]+/style\.css\?ver=([0-9.]+)', "theme_css"),
    (r'/wp-includes/js/wp-embed\.min\.js\?ver=([0-9.]+)', "embed_js"),
]

WP_VULN_DB = {
    "4.7": ["CVE-2017-1001000 (REST API privilege escalation)"],
    "4.7.1": ["CVE-2017-1001000 (REST API privilege escalation)"],
    "4.7.2": ["CVE-2017-8295 (password reset)"],
    "4.8": ["CVE-2017-17092 (path traversal)"],
    "4.8.1": ["CVE-2017-17092 (path traversal)"],
    "4.9": ["CVE-2018-6389 (DoS via load-scripts.php)"],
    "4.9.1": ["CVE-2018-6389 (DoS via load-scripts.php)"],
    "5.0": ["CVE-2019-8942 (path traversal in unzipping)"],
    "5.1": ["CVE-2019-9787 (CSRF in comment editing)"],
    "5.2": ["CVE-2019-16222 (XSS in cached pages)"],
    "5.2.1": ["CVE-2019-16777 (stored XSS in Customizer)"],
    "5.2.2": ["CVE-2019-17669 (stored XSS)"],
    "5.2.3": ["CVE-2019-17671 (unauthenticated view private posts)"],
    "5.2.4": ["CVE-2019-17672 (XSS in media uploads)"],
    "5.3": ["CVE-2020-8417 (CSRF in comment replies)"],
    "5.4": ["CVE-2020-11026 (XSS in shortcode preview)"],
    "5.4.1": ["CVE-2020-11027 (XSS in search block)"],
    "5.4.2": ["CVE-2020-14035 (XSS in file uploads)"],
    "5.5": ["CVE-2020-28035 (stored XSS via plugin upload)"],
    "5.5.1": ["CVE-2020-28036 (XSS in filename upload)"],
    "5.5.2": ["CVE-2020-28037 (SQL injection via wpdb)"],
    "5.5.3": ["CVE-2020-28038 (XSS in comment author URL)"],
    "5.6": ["CVE-2021-24145 (XSS in media library)"],
    "5.7": ["CVE-2021-29447 (XXE in media library)"],
    "5.7.1": ["CVE-2021-29447 (XXE in media library)"],
    "5.7.2": ["CVE-2021-39274 (XSS in AJAX)"],
    "5.8": ["CVE-2021-39275 (XSS in block editor)"],
    "5.8.1": ["CVE-2021-39275 (XSS in block editor)"],
    "5.8.2": ["CVE-2021-25003 (XSS in plugin install)"],
    "5.8.3": ["CVE-2021-25003 (XSS in plugin install)"],
    "5.9": ["CVE-2022-21661 (SQL injection in WP_Query)"],
    "5.9.1": ["CVE-2022-21661 (SQL injection in WP_Query)"],
    "5.9.2": ["CVE-2022-21662 (stored XSS)"],
    "5.9.3": ["CVE-2022-21663 (XSS in wp-mail.php)"],
    "6.0": ["CVE-2022-29467 (XSS in shortcode)"],
    "6.0.1": ["CVE-2022-29468 (XSS in block editor)"],
    "6.0.2": ["CVE-2022-35937 (information disclosure)"],
    "6.1": ["CVE-2022-35938 (XSS in template editor)"],
    "6.1.1": ["CVE-2022-35939 (XSS in navigation)"],
    "6.2": ["CVE-2023-28685 (XSS in upload screen)"],
}


def register(cmds, aliases):
    cmds["wpscan"] = _cmd_wpscan


def _usage():
    print("  usage: wpscan -u <url> [--enumerate u,p,t]\n"
          "  WordPress vulnerability scanner.\n"
          "  Examples:\n"
          "    wpscan -u http://example.com\n"
          "    wpscan -u https://example.com --enumerate u")


def _fetch(url, timeout=10):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TRAP-HUB-WPScan/1.0"})
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        body = resp.read().decode("utf-8", errors="replace")
        return {"status": resp.status, "body": body, "headers": dict(resp.headers)}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"status": e.code, "body": body, "headers": dict(e.headers)}
    except Exception as e:
        return {"error": str(e)}


def _detect_wp_version(body):
    for pattern, source in WP_VERSION_PATTERNS:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            return m.group(1), source
    return None, None


def _cmd_wpscan(args):
    url = None
    enumerate_users = False
    enumerate_plugins = False
    enumerate_themes = False

    i = 0
    while i < len(args):
        if args[i] == "-u" and i + 1 < len(args):
            url = args[i + 1].rstrip("/")
            i += 2
        elif args[i] == "--enumerate" and i + 1 < len(args):
            flags = args[i + 1]
            enumerate_users = "u" in flags
            enumerate_plugins = "p" in flags
            enumerate_themes = "t" in flags
            i += 2
        else:
            i += 1

    if not url:
        _usage()
        return

    print(f"  WordPress scan: {url}")
    print()

    result = _fetch(url)
    if "error" in result:
        print(f"  [!] Connection failed: {result['error']}")
        return

    is_wp = False
    body = result["body"]
    headers = result["headers"]

    if "/wp-content/" in body or "/wp-includes/" in body:
        is_wp = True

    if not is_wp:
        print("  [!] No WordPress indicators found.")
        print("  [*] Target may not be running WordPress.")
        return

    print(f"  [*] HTTP Status: {result['status']}")
    server = headers.get("Server", headers.get("server", "unknown"))
    print(f"  [*] Server: {server}")
    print()

    version, source = _detect_wp_version(body)
    if version:
        print(f"  [+] WordPress version: {version} (from {source})")
        if version in WP_VULN_DB:
            print(f"  [!] Known vulnerabilities for {version}:")
            for vuln in WP_VULN_DB[version]:
                print(f"       - {vuln}")
        else:
            print(f"  [*] No known vulnerabilities in local database for {version}")
    else:
        print(f"  [-] Could not detect WordPress version")

    print()
    if "/wp-json/" in body:
        print(f"  [+] REST API available at {url}/wp-json/")

    wp_paths = ["/wp-admin/", "/wp-login.php", "/xmlrpc.php",
                "/wp-content/", "/wp-includes/", "/readme.html"]
    for wp_path in wp_paths:
        pr = _fetch(url + wp_path, timeout=5)
        if pr.get("status") == 200 or pr.get("status") == 403:
            print(f"  [*] Path found: {wp_path} ({pr.get('status')})")

    if enumerate_users:
        print(f"\n  [*] Enumerating users...")
        for user_id in range(1, 6):
            ur = _fetch(f"{url}/?author={user_id}", timeout=5)
            if ur.get("status") == 200:
                m = re.search(r'<title>([^<]+)', ur["body"])
                if m:
                    title = m.group(1).replace(" &#8211; ", " - ")
                    print(f"       User ID {user_id}: {title}")

    if enumerate_plugins:
        print(f"\n  [*] Checking common plugins...")
        common_plugins = ["akismet", "hello-dolly", "jetpack", "wordfence",
                          "yoast", "contact-form-7", "woocommerce", "elementor"]
        for plugin in common_plugins:
            pr = _fetch(f"{url}/wp-content/plugins/{plugin}/readme.txt", timeout=5)
            if pr.get("status") == 200:
                print(f"       Plugin installed: {plugin}")

    if enumerate_themes:
        print(f"\n  [*] Checking themes...")
        common_themes = ["twentytwentyfour", "twentytwentythree", "twentytwentytwo",
                         "twentytwentyone", "twentytwenty"]
        for theme in common_themes:
            tr = _fetch(f"{url}/wp-content/themes/{theme}/style.css", timeout=5)
            if tr.get("status") == 200:
                print(f"       Theme installed: {theme}")

    print()
    print("  WPScan complete.")
