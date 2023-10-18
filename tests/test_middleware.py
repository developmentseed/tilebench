"""Tests for tilebench."""

from fastapi import FastAPI
from rio_tiler.io import Reader
from starlette.testclient import TestClient

from tilebench.middleware import NoCacheMiddleware, VSIStatsMiddleware

COG_PATH = "https://noaa-eri-pds.s3.amazonaws.com/2022_Hurricane_Ian/20221002a_RGB/20221002aC0795145w325100n.tif"


def test_middleware():
    """Simple test."""
    app = FastAPI()
    app.add_middleware(NoCacheMiddleware)
    app.add_middleware(VSIStatsMiddleware, config={}, exclude_paths=["/skip"])

    @app.get("/info")
    def head():
        """Get info."""
        with Reader(COG_PATH) as cog:
            cog.info()
            return "I got info"

    @app.get("/tile")
    def tile():
        """Read tile."""
        with Reader(COG_PATH) as cog:
            cog.tile(36460, 52866, 17)
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
    assert "head;count=" in stats
    assert "get;count=" in stats

    response = client.get("/tile")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["VSI-Stats"]
    stats = response.headers["VSI-Stats"]
    assert "head;count=" in stats
    assert "get;count=" in stats

    response = client.get("/skip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "VSI-Stats" not in response.headers
