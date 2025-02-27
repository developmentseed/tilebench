"""Tilebench middlewares."""

import logging
from io import StringIO
from typing import Dict, List, Optional

import rasterio
from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tilebench import parse_rasterio_io_logs, parse_vsifile_io_logs


class VSIStatsMiddleware(BaseHTTPMiddleware):
    """MiddleWare to add VSI stats in response headers."""

    def __init__(
        self,
        app: ASGIApp,
        config: Optional[Dict] = None,
        exclude_paths: Optional[List] = None,
        io: str = "rasterio",
    ) -> None:
        """Init Middleware."""
        super().__init__(app)
        self.config: Dict = config or {}
        self.exclude_paths: List = exclude_paths or []

        if io not in ["rasterio", "vsifile"]:
            raise ValueError(f"Unsupported {io} IO backend")

        self.io_backend = io

    async def dispatch(self, request: Request, call_next):
        """Add VSI stats in headers."""

        if request.scope["path"] in self.exclude_paths:
            return await call_next(request)

        io_stream = StringIO()
        logger = logging.getLogger(self.io_backend)
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(io_stream)
        logger.addHandler(handler)

        gdal_config = {"CPL_DEBUG": "ON", "CPL_CURL_VERBOSE": "TRUE"}
        with rasterio.Env(**gdal_config, **self.config):
            response = await call_next(request)

        logger.removeHandler(handler)
        handler.close()

        if io_stream:
            logs = io_stream.getvalue().splitlines()

            results = {}
            if self.io_backend == "vsifile":
                results.update(parse_vsifile_io_logs(logs))
            else:
                results.update(parse_rasterio_io_logs(logs))

            head_results = "head;count={count}".format(**results["HEAD"])
            get_results = "get;count={count};size={bytes}".format(**results["GET"])
            ranges_results = "ranges; values={}".format(
                "|".join(results["GET"]["ranges"])
            )
            response.headers["VSI-Stats"] = (
                f"{head_results}, {get_results}, {ranges_results}"
            )

        return response


class NoCacheMiddleware:
    """MiddleWare to add CacheControl in response headers."""

    def __init__(self, app: ASGIApp) -> None:
        """Init Middleware."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message):
            """Send Message."""
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)

                if (
                    not response_headers.get("Cache-Control")
                    and scope["method"] in ["HEAD", "GET"]
                    and message["status"] < 500
                ):
                    response_headers["Cache-Control"] = "no-cache"

            await send(message)

        await self.app(scope, receive, send_wrapper)
