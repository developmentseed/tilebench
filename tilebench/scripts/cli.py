"""tilebench CLI."""

import json
import os
from random import randint, sample

import click
from loguru import logger as log
from rasterio.rio import options
from rio_tiler.io import COGReader
from supermercado.burntiles import tile_extrema

from tilebench import profile as profiler
from tilebench.viz import TileDebug


# The CLI command group.
@click.group(help="Command line interface for the tilebench Python package.")
def cli():
    """Execute the main morecantile command"""


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
    "--add-stdout", is_flag=True, default=False, help="Print standard outputs.",
)
@click.option(
    "--config",
    "config",
    metavar="NAME=VALUE",
    multiple=True,
    callback=options._cb_key_val,
    help="GDAL configuration options.",
)
def profile(input, tile, tilesize, zoom, add_kernels, add_stdout, config):
    """Profile COGReader Mercator Tile read."""
    if not tile:
        with COGReader(input) as cog:
            if zoom is None:
                zoom = randint(cog.minzoom, cog.maxzoom)
            extrema = tile_extrema(cog.bounds, zoom)

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
        config=config,
    )
    def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
        with COGReader(src_path) as cog:
            return cog.tile(x, y, z, tilesize=tilesize)

    (_, _), stats = _read_tile(input, tile_x, tile_y, tile_z, tilesize)

    click.echo(json.dumps(stats))


@cli.command()
@options.file_in_arg
def get_zooms(input):
    """Get Mercator Zoom levels."""
    with COGReader(input) as cog:
        click.echo(json.dumps(dict(minzoom=cog.minzoom, maxzoom=cog.maxzoom)))


@cli.command()
@options.file_in_arg
@click.option("--zoom", "-z", type=int)
def random(input, zoom):
    """Get random tile."""
    with COGReader(input) as cog:
        if zoom is None:
            zoom = randint(cog.minzoom, cog.maxzoom)
        extrema = tile_extrema(cog.bounds, zoom)

    x = sample(range(extrema["x"]["min"], extrema["x"]["max"]), 1)[0]
    y = sample(range(extrema["y"]["min"], extrema["y"]["max"]), 1)[0]

    click.echo(f"{zoom}-{x}-{y}")


class MbxTokenType(click.ParamType):
    """Mapbox token type."""

    name = "token"

    def convert(self, value, param, ctx):
        """Validate token."""
        try:
            if not value:
                return ""

            assert value.startswith("pk")
            return value

        except (AttributeError, AssertionError):
            raise click.ClickException(
                "Mapbox access token must be public (pk). "
                "Please sign up at https://www.mapbox.com/signup/ to get a public token. "
                "If you already have an account, you can retreive your "
                "token at https://www.mapbox.com/account/."
            )


@cli.command()
@click.argument("src_path", type=str, nargs=1, required=True)
@click.option(
    "--style",
    type=click.Choice(["dark", "satellite", "basic"]),
    default="dark",
    help="Mapbox basemap",
)
@click.option("--port", type=int, default=8080, help="Webserver port (default: 8080)")
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Webserver host url (default: 127.0.0.1)",
)
@click.option(
    "--mapbox-token",
    type=MbxTokenType(),
    metavar="TOKEN",
    default=lambda: os.environ.get("MAPBOX_ACCESS_TOKEN", ""),
    help="Pass Mapbox token",
)
@click.option(
    "--server-only",
    is_flag=True,
    default=False,
    help="Launch API without opening the rio-viz web-page.",
)
@click.option(
    "--config",
    "config",
    metavar="NAME=VALUE",
    multiple=True,
    callback=options._cb_key_val,
    help="GDAL configuration options.",
)
def viz(
    src_path, style, port, host, mapbox_token, server_only, config,
):
    """WEB UI to visualize VSI statistics for a web mercator tile requests."""
    config = config or {}

    application = TileDebug(
        src_path=src_path,
        token=mapbox_token,
        port=port,
        host=host,
        style=style,
        config=config,
    )
    if not server_only:
        click.echo(f"Viewer started at {application.template_url}", err=True)
        click.launch(application.template_url)

    application.start()
