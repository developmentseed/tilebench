"""Tilebench."""

__version__ = "0.8.2"

import cProfile
import json
import logging
import pstats
import sys
import time
from io import StringIO
from typing import Any, Callable, Dict, List, Optional

import rasterio
from loguru import logger as log
from wurlitzer import pipes

fmt = "{time} | TILEBENCH | {message}"
log.remove()
log.add(sys.stderr, format=fmt)


def analyse_logs(rio_lines: List[str], curl_lines: List[str]) -> Dict[str, Any]:
    """Analyse Rasterio and CURL logs."""
    # LIST
    list_requests = [line for line in rio_lines if " VSICURL: GetFileList" in line]
    list_summary = {
        "count": len(list_requests),
    }

    # HEAD
    curl_head_requests = [line for line in curl_lines if line.startswith("> HEAD")]
    head_summary = {
        "count": len(curl_head_requests),
    }

    # CURL GET
    # CURL logs failed requests
    curl_get_requests = [line for line in curl_lines if line.startswith("> GET")]

    # Rasterio GET
    # Rasterio only log successfull requests
    get_requests = [line for line in rio_lines if ": Downloading" in line]
    get_values = [map(int, get.split(" ")[4].split("-")) for get in get_requests]
    get_values_str = [get.split(" ")[4] for get in get_requests]
    data_transfer = sum([j - i + 1 for i, j in get_values])

    get_summary = {
        "count": len(curl_get_requests),
        "bytes": data_transfer,
        "ranges": get_values_str,
    }

    warp_kernel = [
        line.split(" ")[-2:] for line in rio_lines if "GDALWarpKernel" in line
    ]

    return {
        "LIST": list_summary,
        "HEAD": head_summary,
        "GET": get_summary,
        "WarpKernels": warp_kernel,
    }


def profile(
    kernels: bool = False,
    add_to_return: bool = False,
    quiet: bool = False,
    raw: bool = False,
    cprofile: bool = False,
    config: Optional[Dict] = None,
):
    """Profiling."""

    def wrapper(func: Callable):
        """Wrap a function."""

        def wrapped_f(*args, **kwargs):
            """Wrapped function."""
            rio_stream = StringIO()
            logger = logging.getLogger("rasterio")
            logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler(rio_stream)
            logger.addHandler(handler)

            gdal_config = config or {}
            gdal_config.update({"CPL_DEBUG": "ON", "CPL_CURL_VERBOSE": "TRUE"})

            with pipes() as (_, curl_stream):
                with rasterio.Env(**gdal_config):
                    with Timer() as t:
                        prof = cProfile.Profile()
                        retval = prof.runcall(func, *args, **kwargs)
                        profile_stream = StringIO()
                        ps = pstats.Stats(prof, stream=profile_stream)
                        ps.strip_dirs().sort_stats("time", "ncalls").print_stats()

            logger.removeHandler(handler)
            handler.close()

            rio_lines = rio_stream.getvalue().splitlines()
            curl_lines = curl_stream.read().splitlines()
            profile_lines = [p for p in profile_stream.getvalue().splitlines() if p]

            results = analyse_logs(rio_lines, curl_lines)
            results["Timing"] = t.elapsed

            if cprofile:
                stats_to_print = [
                    p for p in profile_lines[3:] if float(p.split()[1]) > 0.0
                ]
                results["cprofile"] = [profile_lines[2], *stats_to_print]

            if not kernels:
                results.pop("WarpKernels")

            if raw:
                results["curl"] = curl_lines
                results["rasterio"] = rio_lines

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
        """Start timer."""
        self.start = time.time()
        return self

    def __exit__(self, ty, val, tb):
        """Stop timer."""
        self.end = time.time()
        self.elapsed = self.end - self.start
