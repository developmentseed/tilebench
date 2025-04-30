"""Tilebench."""

__version__ = "0.16.0"

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

fmt = "{time} | TILEBENCH | {message}"
log.remove()
log.add(sys.stderr, format=fmt)


def parse_rasterio_io_logs(logs: List[str]) -> Dict[str, Any]:
    """Parse Rasterio and CURL logs."""
    # HEAD
    head_requests = len([line for line in logs if "CURL_INFO_HEADER_OUT: HEAD" in line])
    head_summary = {
        "count": head_requests,
    }

    # GET
    all_get_requests = len([line for line in logs if "CURL_INFO_HEADER_OUT: GET" in line])

    get_requests = [
        line for line in logs if "CURL_INFO_HEADER_IN: Content-Range: bytes" in line
    ]
    get_values = [
        list(
            map(
                int,
                get.split("CURL_INFO_HEADER_IN: Content-Range: bytes ")[1]
                .split("/")[0]
                .split("-"),
            )
        )
        for get in get_requests
    ]
    get_values_str = [f"{start}-{end}" for (start, end) in get_values]
    data_transfer = sum([j - i + 1 for i, j in get_values])

    get_summary = {
        "count": all_get_requests,
        "bytes": data_transfer,
        "ranges": get_values_str,
    }

    warp_kernel = [line.split(" ")[-2:] for line in logs if "GDALWarpKernel" in line]

    return {
        "HEAD": head_summary,
        "GET": get_summary,
        "WarpKernels": warp_kernel,
    }


def parse_vsifile_io_logs(logs: List[str]) -> Dict[str, Any]:
    """Parse VSIFILE IO logs."""
    # HEAD
    head_requests = len([line for line in logs if "VSIFILE_INFO: HEAD" in line])
    head_summary = {
        "count": head_requests,
    }

    # GET
    all_get_requests = len([line for line in logs if "VSIFILE_INFO: GET" in line])

    get_requests = [line for line in logs if "VSIFILE: Downloading: " in line]

    get_values_str = []
    for get in get_requests:
        get_values_str.extend(get.split("VSIFILE: Downloading: ")[1].split(", "))

    get_values = [list(map(int, r.split("-"))) for r in get_values_str]
    data_transfer = sum([j - i + 1 for i, j in get_values])

    get_summary = {
        "count": all_get_requests,
        "bytes": data_transfer,
        "ranges": get_values_str,
    }

    warp_kernel = [line.split(" ")[-2:] for line in logs if "GDALWarpKernel" in line]

    return {
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
    io="rasterio",
):
    """Profiling."""
    if io not in ["rasterio", "vsifile"]:
        raise ValueError(f"Unsupported {io} IO backend")

    def wrapper(func: Callable):
        """Wrap a function."""

        def wrapped_f(*args, **kwargs):
            """Wrapped function."""
            io_stream = StringIO()
            logger = logging.getLogger(io)
            logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler(io_stream)
            logger.addHandler(handler)

            gdal_config = config or {}
            gdal_config.update({"CPL_DEBUG": "ON", "CPL_CURL_VERBOSE": "YES"})

            with rasterio.Env(**gdal_config):
                with Timer() as t:
                    prof = cProfile.Profile()
                    retval = prof.runcall(func, *args, **kwargs)
                    profile_stream = StringIO()
                    ps = pstats.Stats(prof, stream=profile_stream)
                    ps.strip_dirs().sort_stats("time", "ncalls").print_stats()

            logger.removeHandler(handler)
            handler.close()

            logs = io_stream.getvalue().splitlines()
            profile_lines = [p for p in profile_stream.getvalue().splitlines() if p]

            results = {}
            if io == "vsifile":
                results.update(parse_vsifile_io_logs(logs))
            else:
                results.update(parse_rasterio_io_logs(logs))

            results["Timing"] = t.elapsed

            if cprofile:
                stats_to_print = [
                    p for p in profile_lines[3:] if float(p.split()[1]) > 0.0
                ]
                results["cprofile"] = [profile_lines[2], *stats_to_print]

            if not kernels:
                results.pop("WarpKernels")

            if raw:
                results["logs"] = logs

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
