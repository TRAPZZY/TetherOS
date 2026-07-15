"""vfs.py -- Virtual filesystem with Linux-style paths for Tether OS shell"""

import os as real_os
import shutil
import stat
import time
from datetime import datetime


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
                "mtime": now,
                "size": 4096 if attrs["type"] == "dir" else 0,
                "children": [] if attrs["type"] == "dir" else None,
            }

        etc_files = {
            "/etc/hostname":    "trap-hub\n",
            "/etc/hosts":       "127.0.0.1 localhost trap-hub\n::1 localhost trap-hub\n",
            "/etc/resolv.conf": "nameserver 127.0.0.1\nnameserver 1.1.1.1\n",
            "/etc/passwd":      "root:x:0:0:root:/home/root:/bin/bash\n",
            "/etc/shadow":      "root:!:19876:0:99999:7:::\n",
            "/etc/group":       "root:x:0:\nwheel:x:10:root\n",
            "/etc/fstab":       "# Tether OS virtual filesystem\nproc /proc proc defaults 0 0\n",
            "/etc/os-release":  "NAME=\"Tether OS\"\nVERSION=\"1.1.0\"\nID=tether\nID_LIKE=arch\nPRETTY_NAME=\"Tether OS 1.1.0 (Trap Hub)\"\n",
        }
        for path, content in etc_files.items():
            self._nodes[path] = {
                "type": "file", "mode": "-rw-r--r--",
                "mtime": now, "size": len(content),
                "content": content, "children": None,
            }
            parent = path.rstrip("/").rsplit("/", 1)[0]
            if parent in self._nodes and self._nodes[parent]["children"] is not None:
                self._nodes[parent]["children"].append(path.rsplit("/", 1)[1])

        proc_files = {
            "/proc/version": "Tether OS version 1.0.0 (trap-hub@localhost) (gcc (GCC) 13.2.0) #1 SMP PREEMPT_DYNAMIC\n",
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
            "mtime": now, "size": 4096,
            "children": [],
        }
        if name not in self._nodes[parent].get("children", []):
            self._nodes[parent].setdefault("children", []).append(name)
        return True

    def remove(self, path):
        p = self.resolve(path)
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
        self._nodes[dp] = self._nodes[sp]
        self._nodes[dp]["mtime"] = datetime.now()
        del self._nodes[sp]
        if sparent in self._nodes and self._nodes[sparent].get("children"):
            if sname in self._nodes[sparent]["children"]:
                self._nodes[sparent]["children"].remove(sname)
        if dname not in self._nodes[dparent].get("children", []):
            self._nodes[dparent].setdefault("children", []).append(dname)
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
        total = 0
        p = self.resolve(path)
        if p not in self._nodes:
            return 0
        total += self._nodes[p].get("size", 0)
        if self._nodes[p]["type"] == "dir":
            for child in self._nodes[p].get("children", []):
                cpath = p.rstrip("/") + "/" + child if p != "/" else "/" + child
                if cpath in self._nodes:
                    total += self._nodes[cpath].get("size", 0)
                    if self._nodes[cpath]["type"] == "dir":
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
                if name in child:
                    results.append(cpath)
                if cpath in self._nodes and self._nodes[cpath]["type"] == "dir":
                    results.extend(self.find(cpath, name))
        return results
