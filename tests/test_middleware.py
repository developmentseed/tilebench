"""Tests for tilebench."""

from fastapi import FastAPI
from rio_tiler.io import COGReader
from starlette.testclient import TestClient

from tilebench.middleware import NoCacheMiddleware, VSIStatsMiddleware

COG_PATH = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif"


def test_middleware():
    """Simple test."""
    app = FastAPI()
    app.add_middleware(NoCacheMiddleware)
    app.add_middleware(VSIStatsMiddleware, config={}, exclude_paths=["/skip"])

    @app.get("/info")
    def head():
        """Get info."""
        with COGReader(COG_PATH) as cog:
            cog.info()
            return "I got info"

    @app.get("/tile")
    def tile():
        """Read tile."""
        with COGReader(COG_PATH) as cog:
            cog.tile(2314, 1667, 12)
            return "I got tile"

    @app.get("/skip")
    def skip():
        return "I've been skipped"

    client = TestClient(app)

    response = client.get("/info")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["VSI-Stats"]
    stats = response.headers["VSI-Stats"]
    assert "list;count=" in stats
    assert "head;count=" in stats
    assert "get;count=" in stats

    response = client.get("/tile")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["VSI-Stats"]
    stats = response.headers["VSI-Stats"]
    assert "list;count=" in stats
    assert "head;count=" in stats
    assert "get;count=" in stats

    response = client.get("/skip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "VSI-Stats" not in response.headers
