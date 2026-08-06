"""setup.py -- Tether OS installer
Cross-platform deployment via pip.
"""

import ast
from glob import glob
from pathlib import Path
from setuptools import find_packages, setup


def read_version():
    """Read version metadata without importing the package during builds."""
    version_file = Path(__file__).parent / "app" / "version.py"
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__ ="):
            value = ast.literal_eval(line.split("=", 1)[1].strip())
            if isinstance(value, str) and value:
                return value
    raise RuntimeError(f"Unable to read __version__ from {version_file}")


__version__ = read_version()

setup(
    name="tether-os",
    version=__version__,
    description="Tether OS -- Automatic IP rotation every 60 seconds",
    author="Trapzzy",
    packages=find_packages(include=("app", "app.*", "kernel", "lib")),
    include_package_data=True,
    data_files=[
        ("share/tether-os/wordlists", glob("wordlists/*.txt")),
        ("share/tether-os/etc", glob("etc/*")),
    ],
    entry_points={
        "console_scripts": [
            "tether = app.entrypoint:main",
            "tetherd = app.daemon:main",
        ],
    },
    install_requires=[
        "pysocks>=1.7.1",
    ],
    extras_require={
        "dev": ["pytest", "pexpect; platform_system != 'Windows'"],
        "background": ["python-daemon>=2.3.0"],
        "ssh": ["paramiko>=2.12.0"],
    },
    python_requires=">=3.7",
)
