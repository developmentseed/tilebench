"""Common response models."""

from starlette.responses import JSONResponse, Response


class GeoJSONResponse(JSONResponse):
    """GeoJSON Response."""

    media_type = "application/geo+json"


class PNGResponse(Response):
    """GeoJSON Response."""

    media_type = "image/png"
