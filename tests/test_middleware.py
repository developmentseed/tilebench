"""Tests for tilebench."""

from fastapi import FastAPI
from rio_tiler.io import COGReader
from starlette.testclient import TestClient

from tilebench.middleware import NoCacheMiddleware, VSIStatsMiddleware

COG_PATH = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif"


def test_middleware():
    """simple test."""
    app = FastAPI()
    app.add_middleware(NoCacheMiddleware)
    app.add_middleware(VSIStatsMiddleware, config={})

    @app.get("/info")
    def head():
        """get info."""
        with COGReader(COG_PATH) as cog:
            cog.info()
            return "I got info"

    @app.get("/tile")
    def tile():
        """read tile."""
        with COGReader(COG_PATH) as cog:
            cog.tile(2314, 1667, 12)
            return "I got tile"

    client = TestClient(app)

    response = client.get("/info")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["VSI-Stats"]
    stats = response.headers["VSI-Stats"]
    assert "head;count=" in stats
    assert "get;count=" in stats

    response = client.get("/tile")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["VSI-Stats"]
    stats = response.headers["VSI-Stats"]
    assert "head;count=" in stats
    assert "get;count=" in stats
