"""Test profiler with S3 and HTTPS files."""

import pytest
from rio_tiler.io import Reader

from tilebench import profile as profiler


@pytest.mark.parametrize(
    "src_path,head,get",
    [
        (
            "s3://sentinel-cogs/sentinel-s2-l2a-cogs/15/T/VK/2023/10/S2B_15TVK_20231008_0_L2A/TCI.tif",
            0,
            3,
        ),
        (
            "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/15/T/VK/2023/10/S2B_15TVK_20231008_0_L2A/TCI.tif",
            1,
            3,
        ),
    ],
)
def test_profiler(src_path, head, get):
    """Test profiler."""
    config = {
        "AWS_NO_SIGN_REQUEST": True,
        "AWS_DEFAULT_REGION": "us-west-2",
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    }

    @profiler(
        quiet=True,
        add_to_return=True,
        config=config,
    )
    def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
        with Reader(src_path) as cog:
            return cog.tile(x, y, z, tilesize=tilesize)

    (_, _), stats = _read_tile(src_path, 121, 185, 9)
    assert stats["HEAD"]["count"] == head
    assert stats["GET"]["count"] == get
    assert stats["GET"]["bytes"] == 386677
