"""Fake tilebench setup.py for github."""
import sys

from setuptools import setup

sys.stderr.write(
    """
===============================
Unsupported installation method
===============================
tilebench no longer supports installation with `python setup.py install`.
Please use `python -m pip install .` instead.
"""
)
sys.exit(1)


# The below code will never execute, however GitHub is particularly
# picky about where it finds Python packaging metadata.
# See: https://github.com/github/feedback/discussions/6456
#
# To be removed once GitHub catches up.

setup(
    name="tilebench",
    install_requires=[
        "aiofiles",
        "fastapi>=0.73",
        "jinja2>=3.0,<4.0.0",
        "geojson-pydantic",
        "loguru",
        "rasterio>=1.3.0",
        "rio-tiler>=4.0.0a0,<5.0",
        "wurlitzer",
        "uvicorn[standard]",
    ],
)
