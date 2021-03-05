"""Tests for tilebench."""


from starlette.testclient import TestClient

from tilebench.viz import TileDebug

COG_PATH = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif"


def test_viz():
    """Should work as expected (create TileServer object)."""
    app = TileDebug(
        src_path=COG_PATH, config={"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"},
    )
    assert app.port == 8080
    assert app.endpoint == "http://127.0.0.1:8080"
    assert app.template_url == "http://127.0.0.1:8080"

    client = TestClient(app.app)

    response = client.get("/tiles/12/2314/1667")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["VSI-Stats"]
    stats = response.headers["VSI-Stats"]
    assert "head;count=" in stats
    assert "get;count=" in stats
    assert "list;count=" in stats

    response = client.get("/info.geojson")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/geo+json"
    assert "VSI-Stats" not in response.headers

    response = client.get("/tiles.geojson?ovr_level=0")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/geo+json"

    response = client.get("/tiles.geojson?ovr_level=1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/geo+json"
