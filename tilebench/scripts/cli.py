"""tilebench CLI."""

import importlib
import json
import warnings
from random import randint, sample

import click
import morecantile
import rasterio
from loguru import logger as log
from rasterio._path import _parse_path as parse_path
from rasterio.rio import options
from rio_tiler.io import BaseReader, MultiBandReader, MultiBaseReader, Reader

from tilebench import profile as profiler
from tilebench.viz import TileDebug

default_tms = morecantile.tms.get("WebMercatorQuad")


def options_to_dict(ctx, param, value):
    """
    click callback to validate `--opt KEY1=VAL1 --opt KEY2=VAL2` and collect
    in a dictionary like the one below, which is what the CLI function receives.
    If no value or `None` is received then an empty dictionary is returned.

        {
            'KEY1': 'VAL1',
            'KEY2': 'VAL2'
        }

    Note: `==VAL` breaks this as `str.split('=', 1)` is used.
    """

    if not value:
        return {}
    else:
        out = {}
        for pair in value:
            if "=" not in pair:
                raise click.BadParameter(f"Invalid syntax for KEY=VAL arg: {pair}")
            else:
                k, v = pair.split("=", 1)
                out[k] = v

        return out


# The CLI command group.
@click.group(help="Command line interface for the tilebench Python package.")
def cli():
    """Execute the main morecantile command."""


@cli.command()
@options.file_in_arg
@click.option("--tile", type=str)
@click.option("--tilesize", type=int, default=256)
@click.option("--zoom", type=int)
@click.option(
    "--add-kernels",
    is_flag=True,
    default=False,
    help="Add GDAL WarpKernels to the output.",
)
@click.option(
    "--add-stdout",
    is_flag=True,
    default=False,
    help="Print standard outputs.",
)
@click.option(
    "--add-cprofile",
    is_flag=True,
    default=False,
    help="Print cProfile stats.",
)
@click.option(
    "--reader",
    type=str,
    help="rio-tiler Reader (BaseReader). Default is `rio_tiler.io.Reader`",
)
@click.option(
    "--tms",
    help="Path to TileMatrixSet JSON file.",
    type=click.Path(),
)
@click.option(
    "--config",
    "config",
    metavar="NAME=VALUE",
    multiple=True,
    callback=options._cb_key_val,
    help="GDAL configuration options.",
)
@click.option(
    "--reader-params",
    "-p",
    "reader_params",
    metavar="NAME=VALUE",
    multiple=True,
    callback=options_to_dict,
    help="Reader Options.",
)
@click.option(
    "--io",
    "io_backend",
    type=click.Choice(["vsifile", "rasterio"], case_sensitive=True),
    help="IO Backend Options.",
    default="rasterio",
)
def profile(
    input,
    tile,
    tilesize,
    zoom,
    add_kernels,
    add_stdout,
    add_cprofile,
    reader,
    tms,
    config,
    reader_params,
    io_backend,
):
    """Profile Reader Tile read."""
    tilematrixset = default_tms
    if tms:
        with open(tms, "r") as f:
            tilematrixset = morecantile.TileMatrixSet(**json.load(f))

    if reader:
        module, classname = reader.rsplit(".", 1)
        reader = getattr(importlib.import_module(module), classname)  # noqa
        if not issubclass(reader, (BaseReader, MultiBandReader, MultiBaseReader)):
            warnings.warn(f"Invalid reader type: {type(reader)}", stacklevel=1)

    DstReader = reader or Reader

    if not tile:
        with rasterio.Env(CPL_VSIL_CURL_NON_CACHED=parse_path(input).as_vsi()):
            with Reader(input, tms=tilematrixset, **reader_params) as cog:
                if zoom is None:
                    zoom = randint(cog.minzoom, cog.maxzoom)

                w, s, e, n = cog.get_geographic_bounds(
                    tilematrixset.rasterio_geographic_crs
                )
                # Truncate BBox to the TMS bounds
                w = max(tilematrixset.bbox.left, w)
                s = max(tilematrixset.bbox.bottom, s)
                e = min(tilematrixset.bbox.right, e)
                n = min(tilematrixset.bbox.top, n)

                ul_tile = tilematrixset.tile(w, n, zoom)
                lr_tile = tilematrixset.tile(e, s, zoom)
                extrema = {
                    "x": {"min": ul_tile.x, "max": lr_tile.x + 1},
                    "y": {"min": ul_tile.y, "max": lr_tile.y + 1},
                }

        tile_x = sample(range(extrema["x"]["min"], extrema["x"]["max"]), 1)[0]
        tile_y = sample(range(extrema["y"]["min"], extrema["y"]["max"]), 1)[0]
        tile_z = zoom
        log.debug(f"reading tile: {tile_z}-{tile_x}-{tile_y}")
    else:
        tile_z, tile_x, tile_y = list(map(int, tile.split("-")))

    @profiler(
        kernels=add_kernels,
        quiet=True,
        add_to_return=True,
        raw=add_stdout,
        cprofile=add_cprofile,
        config=config,
        io=io_backend,
    )
    def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
        with DstReader(src_path, tms=tilematrixset, **reader_params) as cog:
            return cog.tile(x, y, z, tilesize=tilesize)

    (_, _), stats = _read_tile(input, tile_x, tile_y, tile_z, tilesize)

    click.echo(json.dumps(stats))


@cli.command()
@options.file_in_arg
@click.option(
    "--reader",
    type=str,
    help="rio-tiler Reader (BaseReader). Default is `rio_tiler.io.Reader`",
)
@click.option(
    "--tms",
    help="Path to TileMatrixSet JSON file.",
    type=click.Path(),
)
@click.option(
    "--reader-params",
    "-p",
    "reader_params",
    metavar="NAME=VALUE",
    multiple=True,
    callback=options_to_dict,
    help="Reader Options.",
)
def get_zooms(input, reader, tms, reader_params):
    """Get Mercator Zoom levels."""
    tilematrixset = default_tms
    if tms:
        with open(tms, "r") as f:
            tilematrixset = morecantile.TileMatrixSet(**json.load(f))

    if reader:
        module, classname = reader.rsplit(".", 1)
        reader = getattr(importlib.import_module(module), classname)  # noqa
        if not issubclass(reader, (BaseReader, MultiBandReader, MultiBaseReader)):
            warnings.warn(f"Invalid reader type: {type(reader)}", stacklevel=1)

    DstReader = reader or Reader

    with DstReader(input, tms=tilematrixset, **reader_params) as cog:
        click.echo(json.dumps({"minzoom": cog.minzoom, "maxzoom": cog.maxzoom}))


@cli.command()
@options.file_in_arg
@click.option("--zoom", "-z", type=int)
@click.option(
    "--reader",
    type=str,
    help="rio-tiler Reader (BaseReader). Default is `rio_tiler.io.Reader`",
)
@click.option(
    "--tms",
    help="Path to TileMatrixSet JSON file.",
    type=click.Path(),
)
@click.option(
    "--reader-params",
    "-p",
    "reader_params",
    metavar="NAME=VALUE",
    multiple=True,
    callback=options_to_dict,
    help="Reader Options.",
)
def random(input, zoom, reader, tms, reader_params):
    """Get random tile."""
    tilematrixset = default_tms
    if tms:
        with open(tms, "r") as f:
            tilematrixset = morecantile.TileMatrixSet(**json.load(f))

    if reader:
        module, classname = reader.rsplit(".", 1)
        reader = getattr(importlib.import_module(module), classname)  # noqa
        if not issubclass(reader, (BaseReader, MultiBandReader, MultiBaseReader)):
            warnings.warn(f"Invalid reader type: {type(reader)}", stacklevel=1)

    DstReader = reader or Reader

    with DstReader(input, tms=tilematrixset, **reader_params) as cog:
        if zoom is None:
            zoom = randint(cog.minzoom, cog.maxzoom)
        w, s, e, n = cog.get_geographic_bounds(tilematrixset.rasterio_geographic_crs)

    # Truncate BBox to the TMS bounds
    w = max(tilematrixset.bbox.left, w)
    s = max(tilematrixset.bbox.bottom, s)
    e = min(tilematrixset.bbox.right, e)
    n = min(tilematrixset.bbox.top, n)

    ul_tile = tilematrixset.tile(w, n, zoom)
    lr_tile = tilematrixset.tile(e, s, zoom)
    extrema = {
        "x": {"min": ul_tile.x, "max": lr_tile.x + 1},
        "y": {"min": ul_tile.y, "max": lr_tile.y + 1},
    }

    x = sample(range(extrema["x"]["min"], extrema["x"]["max"]), 1)[0]
    y = sample(range(extrema["y"]["min"], extrema["y"]["max"]), 1)[0]

    click.echo(f"{zoom}-{x}-{y}")


@cli.command()
@click.argument("src_path", type=str, nargs=1, required=True)
@click.option("--port", type=int, default=8080, help="Webserver port (default: 8080)")
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Webserver host url (default: 127.0.0.1)",
)
@click.option(
    "--server-only",
    is_flag=True,
    default=False,
    help="Launch API without opening the rio-viz web-page.",
)
@click.option(
    "--reader",
    type=str,
    help="rio-tiler Reader (BaseReader). Default is `rio_tiler.io.Reader`",
)
@click.option(
    "--config",
    "config",
    metavar="NAME=VALUE",
    multiple=True,
    callback=options._cb_key_val,
    help="GDAL configuration options.",
)
@click.option(
    "--reader-params",
    "-p",
    "reader_params",
    metavar="NAME=VALUE",
    multiple=True,
    callback=options_to_dict,
    help="Reader Options.",
)
@click.option(
    "--io",
    "io_backend",
    type=click.Choice(["vsifile", "rasterio"], case_sensitive=True),
    help="IO Backend Options.",
    default="rasterio",
)
def viz(src_path, port, host, server_only, reader, config, reader_params, io_backend):
    """WEB UI to visualize VSI statistics for a web mercator tile requests."""
    if reader:
        module, classname = reader.rsplit(".", 1)
        reader = getattr(importlib.import_module(module), classname)  # noqa
        if not issubclass(reader, (BaseReader, MultiBandReader, MultiBaseReader)):
            warnings.warn(f"Invalid reader type: {type(reader)}", stacklevel=1)

    DstReader = reader or Reader

    config = config or {}

    application = TileDebug(
        src_path=src_path,
        reader=DstReader,
        reader_params=reader_params,
        port=port,
        host=host,
        config=config,
        io_backend=io_backend,
    )
    if not server_only:
        click.echo(f"Viewer started at {application.template_url}", err=True)
        click.launch(application.template_url)

    application.start()
