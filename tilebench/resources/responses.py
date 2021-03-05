"""Common response models."""

from starlette.responses import JSONResponse


class GeoJSONResponse(JSONResponse):
    """GeoJSON Response"""

    media_type = "application/geo+json"
