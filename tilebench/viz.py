"""Tilebench."""

import math
import pathlib
from typing import Dict, Optional, Tuple, Type

import attr
import morecantile
import numpy
import rasterio
import uvicorn
from fastapi import APIRouter, FastAPI, Query
from fastapi.staticfiles import StaticFiles
from geojson_pydantic.features import Feature, FeatureCollection
from rasterio import windows
from rasterio._path import _parse_path as parse_path
from rasterio.crs import CRS
from rasterio.vrt import WarpedVRT
from rasterio.warp import calculate_default_transform, transform_geom
from rio_tiler.io import BaseReader, Reader
from rio_tiler.utils import render
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates

from tilebench import Timer
from tilebench import profile as profiler
from tilebench.middleware import NoCacheMiddleware
from tilebench.resources.responses import GeoJSONResponse, PNGResponse

template_dir = str(pathlib.Path(__file__).parent.joinpath("templates"))
static_dir = str(pathlib.Path(__file__).parent.joinpath("static"))
templates = Jinja2Templates(directory=template_dir)

tms = morecantile.tms.get("WebMercatorQuad")
WGS84_CRS = CRS.from_epsg(4326)


def bbox_to_feature(
    bbox: Tuple[float, float, float, float],
    properties: Optional[Dict] = None,
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


def dims(total: int, chop: int):
    """Given a total number of pixels, chop into equal chunks.

    yeilds (offset, size) tuples
    >>> list(dims(512, 256))
    [(0, 256), (256, 256)]
    >>> list(dims(502, 256))
    [(0, 256), (256, 246)]
    >>> list(dims(522, 256))
    [(0, 256), (256, 256), (512, 10)]
    """
    for a in range(int(math.ceil(total / chop))):
        offset = a * chop
        yield offset, chop


@attr.s
class TileDebug:
    """Creates a very minimal server using fastAPI + Uvicorn."""

    src_path: str = attr.ib()
    reader: Type[BaseReader] = attr.ib(default=Reader)

    app: FastAPI = attr.ib(default=attr.Factory(FastAPI))

    port: int = attr.ib(default=8080)
    host: str = attr.ib(default="127.0.0.1")
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
        self.app.add_middleware(NoCacheMiddleware)

    def register_routes(self):
        """Register routes to the FastAPI app."""

        @self.router.get(r"/tiles/{z}/{x}/{y}.png", response_class=PNGResponse)
        def image(response: Response, z: int, x: int, y: int):
            """Handle /image requests."""
            with self.reader(self.src_path) as src_dst:
                img = src_dst.tile(x, y, z)
            return PNGResponse(
                render(
                    numpy.zeros((1, 256, 256), dtype="uint8"),
                    img.mask,
                    img_format="PNG",
                    zlevel=6,
                )
            )

        @self.router.get(r"/tiles/{z}/{x}/{y}")
        def tile(response: Response, z: int, x: int, y: int):
            """Handle /tiles requests."""

            @profiler(
                kernels=False,
                quiet=True,
                add_to_return=True,
                raw=False,
                config=self.config,
            )
            def _read_tile(src_path: str, x: int, y: int, z: int):
                with self.reader(src_path) as src_dst:
                    return src_dst.tile(x, y, z)

            with Timer() as t:
                (_, _), stats = _read_tile(self.src_path, x, y, z)

            head_results = "head;count={count}".format(**stats["HEAD"])
            list_results = "list;count={count}".format(**stats["LIST"])
            get_results = "get;count={count};size={bytes}".format(**stats["GET"])
            ranges_results = "ranges; values={}".format(
                "|".join(stats["GET"]["ranges"])
            )
            response.headers[
                "VSI-Stats"
            ] = f"{list_results}, {head_results}, {get_results}, {ranges_results}"

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
            """Return a geojson."""
            with rasterio.open(self.src_path) as src_dst:
                width, height = src_dst.width, src_dst.height

                info = {
                    "width": width,
                    "height": height,
                }

                with WarpedVRT(src_dst, crs="epsg:4326") as vrt:
                    geographic_bounds = list(vrt.bounds)

                info["bounds"] = geographic_bounds

                info["crs"] = src_dst.crs.to_epsg()
                ovr = src_dst.overviews(1)
                info["overviews"] = len(ovr)
                dst_affine, _, _ = calculate_default_transform(
                    src_dst.crs,
                    tms.crs,
                    width,
                    height,
                    *src_dst.bounds,
                )
                resolution = max(abs(dst_affine[0]), abs(dst_affine[4]))
                zoom = tms.zoom_for_res(resolution)
                info["maxzoom"] = zoom

                ifd = [
                    {
                        "Level": 0,
                        "Width": width,
                        "Height": height,
                        "Blocksize": src_dst.block_shapes[0],
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
            info["minzoom"] = zoom  # either the same has maxzoom or last IFD

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
                blockxsize, blockysize = src_dst.block_shapes[0]
                winds = (
                    windows.Window(col_off=col_off, row_off=row_off, width=w, height=h)
                    for row_off, h in dims(src_dst.height, blockysize)
                    for col_off, w in dims(src_dst.width, blockxsize)
                )
                for window in winds:
                    geom = bbox_to_feature(
                        windows.bounds(window, src_dst.transform)
                    ).geometry.dict()
                    geom = transform_geom(src_dst.crs, WGS84_CRS, geom)
                    feats.append(
                        {
                            "type": "Feature",
                            "geometry": geom,
                            "properties": {"window": str(window)},
                        }
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
                    "image_endpoint": request.url_for(
                        "image", z="{z}", x="{x}", y="{y}"
                    ),
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
