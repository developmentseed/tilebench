"""Tilebench middlewares."""

import logging
from io import StringIO
from typing import Dict, Optional

import rasterio
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp
from wurlitzer import pipes

from tilebench import analyse_logs


class VSIStatsMiddleware(BaseHTTPMiddleware):
    """MiddleWare to add VSI stats in response headers."""

    def __init__(self, app: ASGIApp, config: Optional[Dict] = None) -> None:
        """Init Middleware."""
        super().__init__(app)
        self.config: Dict = config or {}

    async def dispatch(self, request: Request, call_next):
        """Add VSI stats in headers."""

        rio_stream = StringIO()
        logger = logging.getLogger("rasterio")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(rio_stream)
        logger.addHandler(handler)

        gdal_config = {"CPL_DEBUG": "ON", "CPL_CURL_VERBOSE": "TRUE"}
        with pipes() as (_, curl_stream):
            with rasterio.Env(**gdal_config, **self.config):
                response = await call_next(request)

        logger.removeHandler(handler)
        handler.close()

        if rio_stream or curl_stream:
            rio_lines = rio_stream.getvalue().splitlines()
            curl_lines = curl_stream.read().splitlines()

            results = analyse_logs(rio_lines, curl_lines)
            head_results = "head;count={count}".format(**results["HEAD"])
            list_results = "list;count={count}".format(**results["LIST"])
            get_results = "get;count={count};size={bytes}".format(**results["GET"])
            ranges_results = "ranges; values={}".format(
                "|".join(results["GET"]["ranges"])
            )
            response.headers[
                "VSI-Stats"
            ] = f"{list_results}, {head_results}, {get_results}, {ranges_results}"

        return response


class NoCacheMiddleware(BaseHTTPMiddleware):
    """MiddleWare to add CacheControl in response headers."""

    async def dispatch(self, request: Request, call_next):
        """Add cache-control."""
        response = await call_next(request)
        if (
            not response.headers.get("Cache-Control")
            and request.method in ["HEAD", "GET"]
            and response.status_code < 500
        ):
            response.headers["Cache-Control"] = "no-cache"
        return response
