"""tilebench"""

import pathlib
from typing import Dict, Optional, Tuple

import attr
import morecantile
import rasterio
import uvicorn
from fastapi import APIRouter, FastAPI, Query
from fastapi.staticfiles import StaticFiles
from geojson_pydantic.features import Feature, FeatureCollection
from rasterio.crs import CRS
from rasterio.path import parse_path
from rasterio.warp import calculate_default_transform, transform_geom
from rio_tiler.io import COGReader
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates

from tilebench import Timer
from tilebench.middleware import NoCacheMiddleware, VSIStatsMiddleware
from tilebench.ressources.responses import GeoJSONResponse

template_dir = str(pathlib.Path(__file__).parent.joinpath("templates"))
static_dir = str(pathlib.Path(__file__).parent.joinpath("static"))
templates = Jinja2Templates(directory=template_dir)

tms = morecantile.tms.get("WebMercatorQuad")
WGS84_CRS = CRS.from_epsg(4326)


def bbox_to_feature(
    bbox: Tuple[float, float, float, float], properties: Optional[Dict] = None,
) -> Feature:
    """Create a GeoJSON feature polygon from a bounding box."""
    return Feature(
        **{
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [bbox[0], bbox[3]],
                        [bbox[0], bbox[1]],
                        [bbox[2], bbox[1]],
                        [bbox[2], bbox[3]],
                        [bbox[0], bbox[3]],
                    ]
                ],
            },
            "properties": {} or properties,
            "type": "Feature",
        }
    )


@attr.s
class TileDebug:
    """Creates a very minimal server using fastAPI + Uvicorn."""

    src_path: str = attr.ib()

    app: FastAPI = attr.ib(default=attr.Factory(FastAPI))

    token: Optional[str] = attr.ib(default=None)
    port: int = attr.ib(default=8080)
    host: str = attr.ib(default="127.0.0.1")
    style: str = attr.ib(default="basic")
    config: Dict = attr.ib(default=dict)

    router: Optional[APIRouter] = attr.ib(init=False)

    def __attrs_post_init__(self):
        """Update App."""
        # we force NO CACHE for our path
        self.config.update(
            {"CPL_VSIL_CURL_NON_CACHED": parse_path(self.src_path).as_vsi()}
        )

        self.router = APIRouter()
        self.register_routes()
        self.app.include_router(self.router)
        self.app.mount("/static", StaticFiles(directory=static_dir), name="static")
        self.app.add_middleware(VSIStatsMiddleware, config=self.config)
        self.app.add_middleware(NoCacheMiddleware)

    def register_routes(self):
        """Register routes to the FastAPI app."""

        @self.router.get(r"/tiles/{z}/{x}/{y}")
        def tile(response: Response, z: int, x: int, y: int):
            """Handle /tiles requests."""
            with Timer() as t:
                with COGReader(self.src_path) as src_dst:
                    _ = src_dst.tile(x, y, z)
            response.headers[
                "server-timing"
            ] = f"dataread; dur={round(t.elapsed * 1000, 2)}"
            return "OK"

        @self.router.get(
            r"/info.geojson",
            response_model=Feature,
            response_model_exclude_none=True,
            response_class=GeoJSONResponse,
        )
        def info():
            """return geojson."""
            with COGReader(self.src_path) as src_dst:
                info = src_dst.info().dict(exclude_none=True)
                ovr = src_dst.dataset.overviews(1)
                info["overviews"] = len(ovr)
                dst_affine, _, _ = calculate_default_transform(
                    src_dst.dataset.crs,
                    tms.crs,
                    src_dst.dataset.width,
                    src_dst.dataset.height,
                    *src_dst.dataset.bounds,
                )
                resolution = max(abs(dst_affine[0]), abs(dst_affine[4]))
                zoom = tms.zoom_for_res(resolution)
                ifd = [
                    {
                        "Level": 0,
                        "Width": src_dst.dataset.width,
                        "Height": src_dst.dataset.height,
                        "Blocksize": src_dst.dataset.block_shapes[0],
                        "Decimation": 0,
                        "MercatorZoom": zoom,
                        "MercatorResolution": resolution,
                    }
                ]

            for ix, decim in enumerate(ovr):
                with rasterio.open(self.src_path, OVERVIEW_LEVEL=ix) as ovr_dst:
                    dst_affine, _, _ = calculate_default_transform(
                        ovr_dst.crs,
                        tms.crs,
                        ovr_dst.width,
                        ovr_dst.height,
                        *ovr_dst.bounds,
                    )
                    resolution = max(abs(dst_affine[0]), abs(dst_affine[4]))
                    zoom = tms.zoom_for_res(resolution)

                    ifd.append(
                        {
                            "Level": ix + 1,
                            "Width": ovr_dst.width,
                            "Height": ovr_dst.height,
                            "Blocksize": ovr_dst.block_shapes[0],
                            "Decimation": decim,
                            "MercatorZoom": zoom,
                            "MercatorResolution": resolution,
                        }
                    )
                info["ifd"] = ifd

            return bbox_to_feature(info["bounds"], properties=info)

        @self.router.get(
            r"/tiles.geojson",
            response_model=FeatureCollection,
            response_model_exclude_none=True,
            response_class=GeoJSONResponse,
        )
        def grid(ovr_level: int = Query(...)):
            """return geojson."""
            options = {"OVERVIEW_LEVEL": ovr_level - 1} if ovr_level else {}
            with rasterio.open(self.src_path, **options) as src_dst:
                feats = []
                for _, window in list(src_dst.block_windows(1)):
                    geom = bbox_to_feature(src_dst.window_bounds(window))
                    geom = transform_geom(src_dst.crs, WGS84_CRS, geom.geometry.dict(),)
                    feats.append(
                        {"type": "Feature", "geometry": geom, "properties": {}}
                    )
            grids = {"type": "FeatureCollection", "features": feats}
            return grids

        @self.router.get(
            "/",
            responses={200: {"description": "Simple COG viewer."}},
            response_class=HTMLResponse,
        )
        async def viewer(request: Request):
            """Handle /index.html."""
            return templates.TemplateResponse(
                name="index.html",
                context={
                    "request": request,
                    "geojson_endpoint": request.url_for("info"),
                    "grid_endpoint": request.url_for("grid"),
                    "tile_endpoint": request.url_for(
                        "tile", z="${z}", x="${x}", y="${y}"
                    ),
                    "mapbox_access_token": self.token,
                    "mapbox_style": self.style,
                },
                media_type="text/html",
            )

    @property
    def endpoint(self) -> str:
        """Get endpoint url."""
        return f"http://{self.host}:{self.port}"

    @property
    def template_url(self) -> str:
        """Get simple app template url."""
        return f"http://{self.host}:{self.port}"

    @property
    def docs_url(self) -> str:
        """Get simple app template url."""
        return f"http://{self.host}:{self.port}/docs"

    def start(self):
        """Start tile server."""
        uvicorn.run(app=self.app, host=self.host, port=self.port, log_level="info")
