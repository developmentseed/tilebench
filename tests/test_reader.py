"""Tests for tilebench."""

import rasterio
from rio_tiler.io import Reader
from vsifile.rasterio import opener

from tilebench import profile as profiler

COG_PATH = "https://noaa-eri-pds.s3.amazonaws.com/2022_Hurricane_Ian/20221002a_RGB/20221002aC0795145w325100n.tif"


def test_simple():
    """Simple test."""

    @profiler()
    def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
        with Reader(src_path) as cog:
            return cog.tile(x, y, z, tilesize=tilesize)

    data, mask = _read_tile(COG_PATH, 36460, 52866, 17)
    assert data.shape
    assert mask.shape


def test_output():
    """Checkout profile output."""

    @profiler(
        kernels=True,
        add_to_return=True,
        quiet=True,
        config={"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"},
    )
    def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
        with Reader(src_path) as cog:
            return cog.tile(x, y, z, tilesize=tilesize)

    (data, mask), stats = _read_tile(COG_PATH, 36460, 52866, 17)
    assert data.shape
    assert mask.shape
    assert stats
    assert stats.get("HEAD")
    assert stats.get("GET")
    assert stats.get("Timing")
    assert stats.get("WarpKernels")


def test_vsifile():
    """Checkout profile output."""

    @profiler(
        kernels=True,
        add_to_return=True,
        quiet=True,
        config={"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"},
        io="vsifile",
    )
    def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
        with rasterio.open(src_path, opener=opener) as src:
            with Reader(None, dataset=src) as cog:
                return cog.tile(x, y, z, tilesize=tilesize)

    (data, mask), stats = _read_tile(COG_PATH, 36460, 52866, 17)
    assert data.shape
    assert mask.shape
    assert stats
    assert "HEAD" in stats
    assert stats.get("GET")
    assert stats.get("Timing")
    assert "WarpKernels" in stats
