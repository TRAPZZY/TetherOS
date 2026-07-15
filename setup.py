"""setup.py -- Tether OS installer
Cross-platform deployment via pip.
"""

from setuptools import setup

setup(
    name="tether-os",
    version="1.0.0",
    description="Tether OS -- Automatic IP rotation every 60 seconds",
    author="Trapzzy",
    packages=["kernel", "lib", "app"],
    package_dir={
        "kernel": "kernel",
        "lib": "lib",
        "app": "app",
    },
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "tether = app.shell:main",
            "tetherd = app.daemon:main",
        ],
    },
    install_requires=[
        "pysocks>=1.7.1",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": ["pytest"],
        "background": ["python-daemon>=2.3.0"],
    },
    python_requires=">=3.7",
)
