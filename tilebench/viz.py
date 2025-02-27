"""Tilebench."""

import math
import pathlib
from typing import Dict, Optional, Tuple, Type

import attr
import morecantile
import numpy
import rasterio
import uvicorn
from fastapi import APIRouter, FastAPI, Path, Query
from fastapi.staticfiles import StaticFiles
from rasterio import windows
from rasterio._path import _parse_path as parse_path
from rasterio.crs import CRS
from rasterio.warp import calculate_default_transform, transform_geom
from rio_tiler.io import BaseReader, Reader
from rio_tiler.utils import render
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates
from typing_extensions import Annotated

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
) -> Dict:
    """Create a GeoJSON feature polygon from a bounding box."""
    # Dateline crossing dataset
    if bbox[0] > bbox[2]:
        bounds_left = [-180, bbox[1], bbox[2], bbox[3]]
        bounds_right = [bbox[0], bbox[1], 180, bbox[3]]

        features = [
            {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [bounds_left[0], bounds_left[3]],
                            [bounds_left[0], bounds_left[1]],
                            [bounds_left[2], bounds_left[1]],
                            [bounds_left[2], bounds_left[3]],
                            [bounds_left[0], bounds_left[3]],
                        ]
                    ],
                },
                "properties": properties or {},
                "type": "Feature",
            },
            {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [bounds_right[0], bounds_right[3]],
                            [bounds_right[0], bounds_right[1]],
                            [bounds_right[2], bounds_right[1]],
                            [bounds_right[2], bounds_right[3]],
                            [bounds_right[0], bounds_right[3]],
                        ]
                    ],
                },
                "properties": properties or {},
                "type": "Feature",
            },
        ]
    else:
        features = [
            {
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
                "properties": properties or {},
                "type": "Feature",
            },
        ]

    return {"type": "FeatureCollection", "features": features}


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
    reader_params: Dict = attr.ib(factory=dict)

    app: FastAPI = attr.ib(default=attr.Factory(FastAPI))

    port: int = attr.ib(default=8080)
    host: str = attr.ib(default="127.0.0.1")
    config: Dict = attr.ib(default=dict)
    io_backend: str = attr.ib(default="rasterio")

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
        def image(
            response: Response,
            z: Annotated[
                int,
                Path(
                    description="Identifier (Z) selecting one of the scales defined in the TileMatrixSet and representing the scaleDenominator the tile.",
                ),
            ],
            x: Annotated[
                int,
                Path(
                    description="Column (X) index of the tile on the selected TileMatrix. It cannot exceed the MatrixHeight-1 for the selected TileMatrix.",
                ),
            ],
            y: Annotated[
                int,
                Path(
                    description="Row (Y) index of the tile on the selected TileMatrix. It cannot exceed the MatrixWidth-1 for the selected TileMatrix.",
                ),
            ],
        ):
            """Handle /image requests."""
            with self.reader(self.src_path, **self.reader_params) as src_dst:
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
        def tile(
            response: Response,
            z: Annotated[
                int,
                Path(
                    description="Identifier (Z) selecting one of the scales defined in the TileMatrixSet and representing the scaleDenominator the tile.",
                ),
            ],
            x: Annotated[
                int,
                Path(
                    description="Column (X) index of the tile on the selected TileMatrix. It cannot exceed the MatrixHeight-1 for the selected TileMatrix.",
                ),
            ],
            y: Annotated[
                int,
                Path(
                    description="Row (Y) index of the tile on the selected TileMatrix. It cannot exceed the MatrixWidth-1 for the selected TileMatrix.",
                ),
            ],
        ):
            """Handle /tiles requests."""

            @profiler(
                kernels=False,
                quiet=True,
                add_to_return=True,
                raw=False,
                config=self.config,
                io=self.io_backend,
            )
            def _read_tile(src_path: str, x: int, y: int, z: int):
                with self.reader(src_path, **self.reader_params) as src_dst:
                    return src_dst.tile(x, y, z)

            with Timer() as t:
                (_, _), stats = _read_tile(self.src_path, x, y, z)

            head_results = "head;count={count}".format(**stats["HEAD"])
            get_results = "get;count={count};size={bytes}".format(**stats["GET"])
            ranges_results = "ranges; values={}".format("|".join(stats["GET"]["ranges"]))
            response.headers["VSI-Stats"] = (
                f"{head_results}, {get_results}, {ranges_results}"
            )

            response.headers["server-timing"] = (
                f"dataread; dur={round(t.elapsed * 1000, 2)}"
            )
            return "OK"

        @self.router.get(
            r"/info.geojson",
            response_model_exclude_none=True,
            response_class=GeoJSONResponse,
        )
        def info():
            """Return a geojson."""
            with self.reader(self.src_path, **self.reader_params) as src_dst:
                bounds = src_dst.get_geographic_bounds(
                    src_dst.tms.rasterio_geographic_crs
                )

                width, height = src_dst.width, src_dst.height
                if not all([width, height]):
                    return bbox_to_feature(
                        bounds,
                        properties={
                            "bounds": bounds,
                            "crs": src_dst.crs.to_epsg(),
                            "ifd": [],
                        },
                    )

                info = {
                    "width": width,
                    "height": height,
                    "bounds": bounds,
                    "crs": src_dst.crs.to_epsg(),
                }

                dst_affine, _, _ = calculate_default_transform(
                    src_dst.crs,
                    tms.crs,
                    width,
                    height,
                    *src_dst.bounds,
                )

                # Raw resolution Zoom and IFD info
                resolution = max(abs(dst_affine[0]), abs(dst_affine[4]))
                zoom = tms.zoom_for_res(resolution)
                info["maxzoom"] = zoom

                try:
                    blocksize = src_dst.dataset.block_shapes[0]
                except Exception:
                    blocksize = src_dst.width

                ifd = [
                    {
                        "Level": 0,
                        "Width": width,
                        "Height": height,
                        "Blocksize": blocksize,
                        "Decimation": 0,
                        "MercatorZoom": zoom,
                        "MercatorResolution": resolution,
                    }
                ]

                try:
                    ovr = src_dst.dataset.overviews(1)
                except Exception:
                    ovr = []

            info["overviews"] = len(ovr)

            # Overviews Zooms and IFD info
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
            response_model_exclude_none=True,
            response_class=GeoJSONResponse,
        )
        def grid(ovr_level: Annotated[int, Query(description="Overview Level")]):
            """return geojson."""
            # Will only work with Rasterio compatible dataset
            try:
                options = {"OVERVIEW_LEVEL": ovr_level - 1} if ovr_level else {}
                with rasterio.open(self.src_path, **options) as src_dst:
                    feats = []
                    blockxsize, blockysize = src_dst.block_shapes[0]
                    winds = (
                        windows.Window(
                            col_off=col_off, row_off=row_off, width=w, height=h
                        )
                        for row_off, h in dims(src_dst.height, blockysize)
                        for col_off, w in dims(src_dst.width, blockxsize)
                    )
                    for window in winds:
                        fc = bbox_to_feature(windows.bounds(window, src_dst.transform))
                        for feat in fc.get("features", []):
                            geom = transform_geom(
                                src_dst.crs, WGS84_CRS, feat["geometry"]
                            )
                            feats.append(
                                {
                                    "type": "Feature",
                                    "geometry": geom,
                                    "properties": {"window": str(window)},
                                }
                            )

            except Exception:
                feats = []

            return {"type": "FeatureCollection", "features": feats}

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
                    "geojson_endpoint": str(request.url_for("info")),
                    "grid_endpoint": str(request.url_for("grid")),
                    "tile_endpoint": str(
                        request.url_for("tile", z="${z}", x="${x}", y="${y}")
                    ),
                    "image_endpoint": str(
                        request.url_for("image", z="{z}", x="{x}", y="{y}")
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
