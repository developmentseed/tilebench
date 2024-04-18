"""Tests for tilebench."""

from starlette.testclient import TestClient

from tilebench.viz import TileDebug

COG_PATH = "https://noaa-eri-pds.s3.amazonaws.com/2022_Hurricane_Ian/20221002a_RGB/20221002aC0795145w325100n.tif"


def test_viz():
    """Should work as expected (create TileServer object)."""
    app = TileDebug(
        src_path=COG_PATH,
        config={"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"},
    )
    assert app.port == 8080
    assert app.endpoint == "http://127.0.0.1:8080"
    assert app.template_url == "http://127.0.0.1:8080"

    client = TestClient(app.app)

    response = client.get("/tiles/17/36460/52866")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["VSI-Stats"]
    stats = response.headers["VSI-Stats"]
    assert "head;count=" in stats
    assert "get;count=" in stats

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
