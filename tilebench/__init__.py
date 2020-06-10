"""cli"""

import time
import json
import logging
from io import StringIO
import rasterio

import click

from typing import Callable


def profile(kernels: bool = False, stderr: bool = False):
    """Profiling."""

    def wrapper(func: Callable):
        """Function Wrapper."""

        def wrapped_f(*args, **kwargs):
            """Wrapped functions."""
            stream = StringIO()
            logger = logging.getLogger()
            for handler in logger.handlers:
                logger.removeHandler(handler)

            logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler(stream)
            logger.addHandler(handler)

            config = dict(
                CPL_DEBUG="ON",
                VSI_CACHE="FALSE",
                GDAL_DISABLE_READDIR_ON_OPE="EMPTY_DIR",
                GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
                GDAL_HTTP_MULTIPLEX="YES",
                GDAL_HTTP_MULTIRANGE="YES",
            )
            with rasterio.Env(**config):
                with Timer() as t:
                    retval = func(*args, **kwargs)

            logger.removeHandler(handler)
            handler.close()

            lines = stream.getvalue().splitlines()

            get_requests = [line for line in lines if "VSICURL: Downloading " in line]
            get_values = [
                map(int, get.split(" ")[4].split("-")) for get in get_requests
            ]
            get_values_str = [get.split(" ")[4] for get in get_requests]
            data_transfer = sum([j - i for i, j in get_values])

            warp_kernel = [
                line.split(" ")[-2:] for line in lines if "GDALWarpKernel" in line
            ]

            results = {
                "GET_numbers": len(get_requests),
                "GET_ranges": get_values_str,
                "Bytes_transfered": data_transfer,
                "Timing": t.elapsed,
            }

            if kernels:
                results["warpkernels"] = warp_kernel

            click.echo(json.dumps(results), err=stderr)

            return retval

        return wrapped_f

    return wrapper


# This code is copied from marblecutter
#  https://github.com/mojodna/marblecutter/blob/master/marblecutter/stats.py
# License:
# Original work Copyright 2016 Stamen Design
# Modified work Copyright 2016-2017 Seth Fitzsimmons
# Modified work Copyright 2016 American Red Cross
# Modified work Copyright 2016-2017 Humanitarian OpenStreetMap Team
# Modified work Copyright 2017 Mapzen
class Timer(object):
    """Time a code block."""

    def __enter__(self):
        """Starts timer."""
        self.start = time.time()
        return self

    def __exit__(self, ty, val, tb):
        """Stops timer."""
        self.end = time.time()
        self.elapsed = self.end - self.start
