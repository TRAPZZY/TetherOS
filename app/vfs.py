"""vfs.py -- Virtual filesystem with Linux-style paths for Tether OS shell"""

import os as real_os
import shutil
import stat
import time
import fnmatch
from datetime import datetime

from app.version import __version__


class VirtualFS:
    def __init__(self):
        self._home = "/home/root"
        self.cwd = self._home
        self._nodes = {}

        self._init_standard_tree()

    def _init_standard_tree(self):
        now = datetime.now()
        base = {
            "/":              {"type": "dir", "mode": "drwxr-xr-x"},
            "/home":          {"type": "dir", "mode": "drwxr-xr-x"},
            "/home/root":     {"type": "dir", "mode": "drwx------"},
            "/tmp":           {"type": "dir", "mode": "drwxrwxrwt"},
            "/etc":           {"type": "dir", "mode": "drwxr-xr-x"},
            "/bin":           {"type": "dir", "mode": "drwxr-xr-x"},
            "/usr":           {"type": "dir", "mode": "drwxr-xr-x"},
            "/usr/bin":       {"type": "dir", "mode": "drwxr-xr-x"},
            "/var":           {"type": "dir", "mode": "drwxr-xr-x"},
            "/var/log":       {"type": "dir", "mode": "drwxr-xr-x"},
            "/proc":          {"type": "dir", "mode": "dr-xr-xr-x"},
            "/proc/net":      {"type": "dir", "mode": "dr-xr-xr-x"},
            "/dev":           {"type": "dir", "mode": "drwxr-xr-x"},
            "/dev/null":      {"type": "dev",  "mode": "crw-rw-rw-"},
            "/root":          {"type": "dir", "mode": "drwx------"},
            "/boot":          {"type": "dir", "mode": "drwxr-xr-x"},
            "/mnt":           {"type": "dir", "mode": "drwxr-xr-x"},
            "/opt":           {"type": "dir", "mode": "drwxr-xr-x"},
            "/sbin":          {"type": "dir", "mode": "drwxr-xr-x"},
            "/run":           {"type": "dir", "mode": "drwxr-xr-x"},
            "/sys":           {"type": "dir", "mode": "drwxr-xr-x"},
            "/lost+found":    {"type": "dir", "mode": "drwx------"},
        }
        for path, attrs in base.items():
            self._nodes[path] = {
                **attrs,
                "owner": "root",
                "group": "root",
                "mtime": now,
                "size": 4096 if attrs["type"] == "dir" else 0,
                "children": [] if attrs["type"] == "dir" else None,
            }

        for path in base:
            if path == "/":
                continue
            parent, name = self.split_path(path)
            if parent in self._nodes:
                self._nodes[parent]["children"].append(name)

        etc_files = {
            "/etc/hostname":    "trap-hub\n",
            "/etc/hosts":       "127.0.0.1 localhost trap-hub\n::1 localhost trap-hub\n",
            "/etc/resolv.conf": "nameserver 127.0.0.1\nnameserver 1.1.1.1\n",
            "/etc/passwd":      "root:x:0:0:root:/home/root:/bin/bash\n",
            "/etc/shadow":      "root:!:19876:0:99999:7:::\n",
            "/etc/group":       "root:x:0:\nwheel:x:10:root\n",
            "/etc/fstab":       "# Tether OS virtual filesystem\nproc /proc proc defaults 0 0\n",
            "/etc/os-release":  f"NAME=\"Tether OS\"\nVERSION=\"{__version__}\"\nID=tether\nID_LIKE=buildroot\nPRETTY_NAME=\"Tether OS {__version__} (Trap Hub)\"\n",
        }
        for path, content in etc_files.items():
            self._nodes[path] = {
                "type": "file", "mode": "-rw-r--r--",
                "owner": "root", "group": "root",
                "mtime": now, "size": len(content),
                "content": content, "children": None,
            }
            parent = path.rstrip("/").rsplit("/", 1)[0]
            if parent in self._nodes and self._nodes[parent]["children"] is not None:
                self._nodes[parent]["children"].append(path.rsplit("/", 1)[1])

        proc_files = {
            "/proc/version": f"Tether OS version {__version__} (Python shell runtime)\n",
            "/proc/cpuinfo": "processor\t: 0\nvendor_id\t: Trap Hub\nmodel name\t: Tether OS Virtual CPU\ncpu MHz\t\t: 2400.000\ncache size\t: 4096 KB\n",
            "/proc/meminfo": "MemTotal:       16248560 kB\nMemFree:         8932456 kB\nMemAvailable:   12345678 kB\nSwapTotal:       8388608 kB\nSwapFree:        8388608 kB\n",
            "/proc/uptime": "12345.67 67890.12\n",
            "/proc/loadavg": "0.00 0.01 0.05 1/42 31337\n",
            "/proc/modules": "tether_rotator 24576 0 - Live 0xffffffffc0000000\ntor_proxy 16384 1 - Live 0xffffffffc0002000\n",
            "/proc/net/tor": "  sl  local_address rem_address   st tx_queue rx_queue\n   0: 00000000:235C 00000000:0000 0A 00000000:00000000\n",
        }
        for path, content in proc_files.items():
            self._nodes[path] = {
                "type": "file", "mode": "-r--r--r--",
                "owner": "root", "group": "root",
                "mtime": now, "size": len(content),
                "content": content, "children": None,
            }
            parent = path.rstrip("/").rsplit("/", 1)[0]
            if parent in self._nodes and self._nodes[parent]["children"] is not None:
                self._nodes[parent]["children"].append(path.rsplit("/", 1)[1])

        for d in ["/home/root", "/tmp", "/var/log"]:
            self._nodes[d]["children"] = []

    def resolve(self, path):
        if not path:
            return self.cwd
        if path == "~":
            return self._home
        if not path.startswith("/"):
            path = self.cwd.rstrip("/") + "/" + path
        parts = path.split("/")
        resolved = []
        for p in parts:
            if p == "..":
                if resolved:
                    resolved.pop()
            elif p == "." or p == "":
                continue
            else:
                resolved.append(p)
        return "/" + "/".join(resolved)

    def split_path(self, path):
        path = path.rstrip("/")
        parent = path.rsplit("/", 1)[0] if "/" in path else "/"
        name = path.rsplit("/", 1)[1] if "/" in path else path
        return parent or "/", name

    def abspath(self, path=None):
        return self.resolve(path or self.cwd)

    def exists(self, path):
        return self.resolve(path) in self._nodes

    def is_dir(self, path):
        p = self.resolve(path)
        return p in self._nodes and self._nodes[p]["type"] == "dir"

    def is_file(self, path):
        p = self.resolve(path)
        return p in self._nodes and self._nodes[p]["type"] == "file"

    def is_dev(self, path):
        p = self.resolve(path)
        return p in self._nodes and self._nodes[p]["type"] == "dev"

    def listdir(self, path):
        p = self.resolve(path)
        if p not in self._nodes or self._nodes[p]["type"] != "dir":
            return None
        return self._nodes[p].get("children", [])

    def read(self, path):
        p = self.resolve(path)
        if p in self._nodes and self._nodes[p]["type"] in ("file", "dev"):
            return self._nodes[p].get("content", "")
        return None

    def write(self, path, content):
        p = self.resolve(path)
        now = datetime.now()
        parent, name = self.split_path(p)
        if parent not in self._nodes or self._nodes[parent]["type"] != "dir":
            return False
        is_new = p not in self._nodes
        self._nodes[p] = {
            "type": "file", "mode": "-rw-r--r--",
            "owner": "root", "group": "root",
            "mtime": now, "size": len(content),
            "content": content, "children": None,
        }
        if is_new and name not in self._nodes[parent].get("children", []):
            self._nodes[parent].setdefault("children", []).append(name)
        return True

    def mkdir(self, path, mode="drwxr-xr-x"):
        p = self.resolve(path)
        if p in self._nodes:
            return False
        parent, name = self.split_path(p)
        if parent not in self._nodes or self._nodes[parent]["type"] != "dir":
            return False
        now = datetime.now()
        self._nodes[p] = {
            "type": "dir", "mode": mode,
            "owner": "root", "group": "root",
            "mtime": now, "size": 4096,
            "children": [],
        }
        if name not in self._nodes[parent].get("children", []):
            self._nodes[parent].setdefault("children", []).append(name)
        return True

    def makedirs(self, path, mode="drwxr-xr-x"):
        target = self.resolve(path)
        if target == "/":
            return True
        current = ""
        for part in target.strip("/").split("/"):
            current += "/" + part
            if self.exists(current):
                if not self.is_dir(current):
                    return False
                continue
            if not self.mkdir(current, mode=mode):
                return False
        return True

    def remove(self, path):
        p = self.resolve(path)
        if p == "/":
            return False
        if p not in self._nodes:
            return False
        if self._nodes[p]["type"] == "dir" and self._nodes[p].get("children"):
            return False
        parent, name = self.split_path(p)
        if parent in self._nodes and self._nodes[parent].get("children"):
            if name in self._nodes[parent]["children"]:
                self._nodes[parent]["children"].remove(name)
        del self._nodes[p]
        return True

    def rmtree(self, path):
        p = self.resolve(path)
        if p == "/":
            return False
        if p not in self._nodes:
            return False
        to_remove = [k for k in self._nodes if k == p or k.startswith(p + "/")]
        for k in to_remove:
            del self._nodes[k]
        parent, name = self.split_path(p)
        if parent in self._nodes and self._nodes[parent].get("children"):
            if name in self._nodes[parent]["children"]:
                self._nodes[parent]["children"].remove(name)
        return True

    def touch(self, path):
        p = self.resolve(path)
        now = datetime.now()
        if p in self._nodes:
            self._nodes[p]["mtime"] = now
            return True
        parent, name = self.split_path(p)
        if parent not in self._nodes or self._nodes[parent]["type"] != "dir":
            return False
        self._nodes[p] = {
            "type": "file", "mode": "-rw-r--r--",
            "owner": "root", "group": "root",
            "mtime": now, "size": 0,
            "content": "", "children": None,
        }
        if name not in self._nodes[parent].get("children", []):
            self._nodes[parent].setdefault("children", []).append(name)
        return True

    def rename(self, src, dst):
        sp = self.resolve(src)
        dp = self.resolve(dst)
        if sp not in self._nodes:
            return False
        dparent, dname = self.split_path(dp)
        if dparent not in self._nodes or self._nodes[dparent]["type"] != "dir":
            return False
        if dp in self._nodes:
            return False
        sparent, sname = self.split_path(sp)
        moved = {
            key: value
            for key, value in self._nodes.items()
            if key == sp or key.startswith(sp + "/")
        }
        for key in sorted(moved, key=len, reverse=True):
            del self._nodes[key]
        for key, value in moved.items():
            new_key = dp + key[len(sp):]
            self._nodes[new_key] = value
        self._nodes[dp]["mtime"] = datetime.now()
        if sparent in self._nodes and self._nodes[sparent].get("children"):
            if sname in self._nodes[sparent]["children"]:
                self._nodes[sparent]["children"].remove(sname)
        if dname not in self._nodes[dparent].get("children", []):
            self._nodes[dparent].setdefault("children", []).append(dname)
        return True

    def chmod(self, path, mode):
        p = self.resolve(path)
        if p not in self._nodes:
            return False
        if not isinstance(mode, str) or not mode.isdigit() or len(mode) not in (3, 4):
            return False
        digits = mode[-3:]
        perms = ""
        for digit in digits:
            value = int(digit)
            perms += "r" if value & 4 else "-"
            perms += "w" if value & 2 else "-"
            perms += "x" if value & 1 else "-"
        prefix = "d" if self._nodes[p]["type"] == "dir" else "c" if self._nodes[p]["type"] == "dev" else "-"
        self._nodes[p]["mode"] = prefix + perms
        self._nodes[p]["mtime"] = datetime.now()
        return True

    def chown(self, path, owner, group=None):
        p = self.resolve(path)
        if p not in self._nodes or not owner:
            return False
        self._nodes[p]["owner"] = owner
        if group:
            self._nodes[p]["group"] = group
        self._nodes[p]["mtime"] = datetime.now()
        return True

    def stat(self, path):
        p = self.resolve(path)
        if p not in self._nodes:
            return None
        return {**self._nodes[p]}

    def walk(self, path):
        p = self.resolve(path)
        if p not in self._nodes or self._nodes[p]["type"] != "dir":
            return
        for child in self._nodes[p].get("children", []):
            cpath = p.rstrip("/") + "/" + child if p != "/" else "/" + child
            yield cpath, self._nodes[cpath]
            if self._nodes[cpath]["type"] == "dir":
                yield from self.walk(cpath)

    def du(self, path):
        p = self.resolve(path)
        if p not in self._nodes:
            return 0
        total = self._nodes[p].get("size", 0)
        if self._nodes[p]["type"] == "dir":
            for child in self._nodes[p].get("children", []):
                cpath = p.rstrip("/") + "/" + child if p != "/" else "/" + child
                if cpath in self._nodes:
                    total += self.du(cpath)
        return total

    def find(self, path, name):
        results = []
        p = self.resolve(path)
        if p not in self._nodes:
            return results
        if self._nodes[p]["type"] == "dir":
            for child in self._nodes[p].get("children", []):
                cpath = p.rstrip("/") + "/" + child if p != "/" else "/" + child
                if fnmatch.fnmatch(child, name):
                    results.append(cpath)
                if cpath in self._nodes and self._nodes[cpath]["type"] == "dir":
                    results.extend(self.find(cpath, name))
        return results

    def to_dict(self):
        nodes = {}
        for path, node in self._nodes.items():
            item = dict(node)
            if isinstance(item.get("mtime"), datetime):
                item["mtime"] = item["mtime"].isoformat()
            nodes[path] = item
        return {"home": self._home, "cwd": self.cwd, "nodes": nodes}

    def load_dict(self, state):
        if not isinstance(state, dict) or not isinstance(state.get("nodes"), dict):
            return False
        nodes = {}
        for path, node in state["nodes"].items():
            if not isinstance(path, str) or not path.startswith("/") or not isinstance(node, dict):
                return False
            item = dict(node)
            if isinstance(item.get("mtime"), str):
                try:
                    item["mtime"] = datetime.fromisoformat(item["mtime"])
                except ValueError:
                    item["mtime"] = datetime.now()
            nodes[path] = item
        if "/" not in nodes or nodes["/"].get("type") != "dir":
            return False
        self._nodes = nodes
        self._home = state.get("home", "/home/root")
        requested_cwd = state.get("cwd", self._home)
        self.cwd = requested_cwd if requested_cwd in nodes and nodes[requested_cwd].get("type") == "dir" else self._home
        return True
