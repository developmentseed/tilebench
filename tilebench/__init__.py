"""tilebench"""

import json
import logging
import sys
import time
from io import StringIO
from typing import Callable, Dict, Optional

import pkg_resources
import rasterio
from loguru import logger as log

fmt = "{time} | TILEBENCH | {message}"
log.remove()
log.add(sys.stderr, format=fmt)

version = pkg_resources.get_distribution(__package__).version


def profile(
    kernels: bool = False,
    add_to_return: bool = False,
    quiet: bool = False,
    config: Optional[Dict] = None,
):
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

            gdal_config = config or {}
            gdal_config.update({"CPL_DEBUG": "ON"})

            with rasterio.Env(**gdal_config):
                with Timer() as t:
                    retval = func(*args, **kwargs)

            logger.removeHandler(handler)
            handler.close()

            lines = stream.getvalue().splitlines()

            # LIST
            list_requests = [line for line in lines if " VSICURL: GetFileList" in line]
            list_summary = {
                "count": len(list_requests),
            }

            # GET
            get_requests = [line for line in lines if "VSICURL: Downloading" in line]
            get_values = [
                map(int, get.split(" ")[4].split("-")) for get in get_requests
            ]
            get_values_str = [get.split(" ")[4] for get in get_requests]
            data_transfer = sum([j - i + 1 for i, j in get_values])

            get_summary = {
                "count": len(get_requests),
                "bytes": data_transfer,
                "ranges": get_values_str,
            }

            warp_kernel = [
                line.split(" ")[-2:] for line in lines if "GDALWarpKernel" in line
            ]

            results = {
                "LIST": list_summary,
                "GET": get_summary,
                "Timing": t.elapsed,
            }

            if kernels:
                results["WarpKernels"] = warp_kernel

            if not quiet:
                log.info(json.dumps(results))

            if add_to_return:
                return retval, results

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
