"""setup.py -- Tether OS installer
Cross-platform deployment via pip.
"""

from glob import glob
from setuptools import find_packages, setup

from app.version import __version__

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
        "dev": ["pytest"],
        "background": ["python-daemon>=2.3.0"],
        "ssh": ["paramiko>=2.12.0"],
    },
    python_requires=">=3.7",
)
