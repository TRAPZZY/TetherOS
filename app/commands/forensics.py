"""forensics.py -- Digital forensics tools (binwalk, hexdump, strings, exiftool)"""

import sys
import os
import binascii
import struct
import datetime

BINWALK_SIGNATURES = [
    ("ZIP Archive", b"PK\x03\x04"),
    ("GZip Archive", b"\x1f\x8b"),
    ("BZip2 Archive", b"BZh"),
    ("PNG Image", b"\x89PNG"),
    ("JPEG Image", b"\xff\xd8\xff"),
    ("PDF Document", b"%PDF"),
    ("ELF Binary", b"\x7fELF"),
    ("Mach-O Binary", b"\xfe\xed\xfa\xce"),
    ("PE Executable", b"MZ"),
    ("Java Class", b"\xca\xfe\xba\xbe"),
    ("SQSH Filesystem", b"sqsh"),
    ("CPIO Archive", b"070707"),
    ("LZMA Stream", b"\x5d\x00\x00"),
    ("7z Archive", b"7z\xbc\xaf\x27\x1c"),
    ("Tar Archive", b"ustar"),
    ("RIFF (AVI/WAV)", b"RIFF"),
    ("SQLite DB", b"SQLite format 3\x00"),
    ("BMP Image", b"BM"),
    ("GIF Image", b"GIF8"),
    ("WebP Image", b"RIFF"),
]


def register(cmds, aliases):
    cmds["binwalk"] = _cmd_binwalk
    cmds["hexdump"] = _cmd_hexdump
    cmds["strings"] = _cmd_strings
    cmds["exiftool"] = _cmd_exiftool


def _usage(name):
    help_texts = {
        "binwalk": "usage: binwalk <file>\n  Scan file for embedded files and signatures.\n  Scans for ZIP, GZip, PNG, JPEG, PDF, ELF, PE, and more.",
        "hexdump": "usage: hexdump <file> [-n <bytes>]\n  Display file contents in hexadecimal.\n  Examples:\n    hexdump file.bin\n    hexdump file.bin -n 256",
        "strings": "usage: strings <file> [-n <min-length>]\n  Extract printable ASCII strings.\n  Examples:\n    strings file.bin\n    strings file.bin -n 8",
        "exiftool": "usage: exiftool <file>\n  Display file metadata and EXIF information.\n  Examples:\n    exiftool image.jpg\n    exiftool document.pdf",
    }
    print(f"  {help_texts.get(name, '')}")


def _read_file(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            return f.read()
    except:
        return None


def _cmd_binwalk(args):
    if not args:
        _usage("binwalk")
        return

    fpath = args[0]
    data = _read_file(fpath)
    if data is None:
        print(f"  binwalk: {fpath}: cannot open")
        return

    size = len(data)
    print(f"  Binwalk scan: {fpath} ({size} bytes)")
    print()

    found = []
    for name, sig in BINWALK_SIGNATURES:
        pos = 0
        while True:
            pos = data.find(sig, pos)
            if pos == -1:
                break
            found.append((pos, name))
            pos += 1

    found.sort(key=lambda x: x[0])

    if not found:
        print("  No known signatures found.")
    else:
        print(f"  {'OFFSET':12} {'DESCRIPTION':30}")
        print(f"  {'-'*12} {'-'*30}")
        for offset, desc in found:
            print(f"  {offset:<12} {desc}")

    entropy = _estimate_entropy(data)
    print(f"\n  Estimated entropy: {entropy:.2f} (max 8.0)")
    if entropy > 7.5:
        print("  [!] High entropy -- possible encrypted or compressed data")
    elif entropy > 6.0:
        print("  [*] Medium entropy")

    print("\n  Binwalk scan complete.")


def _estimate_entropy(data):
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    ent = 0.0
    for f in freq:
        if f > 0:
            p = f / len(data)
            ent -= p * (p and (p ** 0.5) or 0)
    import math
    ent = 0.0
    for f in freq:
        if f > 0:
            p = f / len(data)
            ent -= p * math.log2(p)
    return ent


def _cmd_hexdump(args):
    fpath = None
    n_bytes = 512
    i = 0
    while i < len(args):
        if args[i] == "-n" and i + 1 < len(args):
            try:
                n_bytes = int(args[i + 1])
            except:
                pass
            i += 2
        else:
            fpath = args[i]
            i += 1

    if not fpath:
        _usage("hexdump")
        return

    data = _read_file(fpath)
    if data is None:
        print(f"  hexdump: {fpath}: cannot open")
        return

    data = data[:n_bytes]
    print(f"  Hex dump: {fpath} ({len(data)} bytes shown)")
    print()

    width = 16
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        addr = f"{i:08x}"
        padded_hex = hex_part.ljust(width * 3 - 1)
        print(f"  {addr}  {padded_hex}  |{ascii_part}|")

    print(f"\n  {len(data)} bytes shown.")


def _cmd_strings(args):
    fpath = None
    min_len = 4
    i = 0
    while i < len(args):
        if args[i] == "-n" and i + 1 < len(args):
            try:
                min_len = int(args[i + 1])
            except:
                pass
            i += 2
        else:
            fpath = args[i]
            i += 1

    if not fpath:
        _usage("strings")
        return

    data = _read_file(fpath)
    if data is None:
        print(f"  strings: {fpath}: cannot open")
        return

    results = []
    current = []
    for b in data:
        if 32 <= b < 127:
            current.append(chr(b))
        else:
            if len(current) >= min_len:
                results.append("".join(current))
            current = []

    if len(current) >= min_len:
        results.append("".join(current))

    if not results:
        print(f"  No strings of length >= {min_len} found.")
    else:
        print(f"  Extracted {len(results)} string(s) (min length: {min_len}):")
        print()
        for s in results:
            print(f"  {s}")


def _cmd_exiftool(args):
    if not args:
        _usage("exiftool")
        return

    fpath = args[0]
    if not os.path.isfile(fpath):
        print(f"  exiftool: {fpath}: No such file")
        return

    size = os.path.getsize(fpath)
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
    ctime = datetime.datetime.fromtimestamp(os.path.getctime(fpath))

    print(f"  EXIF metadata: {fpath}")
    print()
    print(f"  {'Property':30} {'Value'}")
    print(f"  {'-'*30} {'-'*40}")
    print(f"  {'File Size':30} {size} bytes")
    print(f"  {'File Name':30} {os.path.basename(fpath)}")
    print(f"  {'File Path':30} {os.path.abspath(fpath)}")
    print(f"  {'Modified':30} {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  {'Created':30} {ctime.strftime('%Y-%m-%d %H:%M:%S')}")

    ext = os.path.splitext(fpath)[1].lower()
    with open(fpath, "rb") as f:
        header = f.read(32)

    if ext in (".jpg", ".jpeg", ".tiff", ".tif"):
        _parse_exif_jpeg(fpath, header)

    if ext in (".png",):
        _parse_exif_png(header)

    if ext == ".pdf":
        _parse_exif_pdf(fpath)

    print("\n  Exiftool complete.")


def _parse_exif_jpeg(fpath, header):
    print(f"  {'Image Width':30} JPEG (embedded size unknown)")
    print(f"  {'Image Height':30} JPEG (embedded size unknown)")
    print(f"  {'MIME Type':30} image/jpeg")


def _parse_exif_png(header):
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        try:
            w = struct.unpack(">I", header[16:20])[0]
            h = struct.unpack(">I", header[20:24])[0]
            print(f"  {'Image Width':30} {w} px")
            print(f"  {'Image Height':30} {h} px")
            print(f"  {'MIME Type':30} image/png")
        except:
            pass


def _parse_exif_pdf(fpath):
    try:
        with open(fpath, "rb") as f:
            content = f.read(4096).decode("latin-1")
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("/Title"):
                print(f"  {'Title':30} {line.split('(', 1)[1].rsplit(')', 1)[0] if '(' in line else '?'}")
            elif line.startswith("/Author"):
                print(f"  {'Author':30} {line.split('(', 1)[1].rsplit(')', 1)[0] if '(' in line else '?'}")
            elif line.startswith("/Creator"):
                print(f"  {'Creator':30} {line.split('(', 1)[1].rsplit(')', 1)[0] if '(' in line else '?'}")
            elif line.startswith("/Producer"):
                print(f"  {'Producer':30} {line.split('(', 1)[1].rsplit(')', 1)[0] if '(' in line else '?'}")
        print(f"  {'MIME Type':30} application/pdf")
    except:
        pass
