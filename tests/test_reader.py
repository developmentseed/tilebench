"""Tests for tilebench."""

from rio_tiler.io import COGReader

from tilebench import profile as profiler

COG_PATH = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif"


def test_simple():
    """simple test."""

    @profiler()
    def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
        with COGReader(src_path) as cog:
            return cog.tile(x, y, z, tilesize=tilesize)

    data, mask = _read_tile(COG_PATH, 2314, 1667, 12,)
    assert data.shape
    assert mask.shape


def test_output():
    """checkout profile output."""

    @profiler(
        kernels=True,
        add_to_return=True,
        quiet=True,
        config={"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"},
    )
    def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
        with COGReader(src_path) as cog:
            return cog.tile(x, y, z, tilesize=tilesize)

    (data, mask), stats = _read_tile(COG_PATH, 2314, 1667, 12,)
    assert data.shape
    assert mask.shape
    assert stats
    assert stats.get("LIST")
    assert stats.get("GET")
    assert stats.get("Timing")
    assert stats.get("WarpKernels")
