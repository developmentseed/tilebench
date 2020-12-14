"""tilebench CLI."""

import json
from random import randint, sample

import click
from rasterio.rio import options
from rio_tiler.io import COGReader
from supermercado.burntiles import tile_extrema

from tilebench import profile as profiler


# The CLI command group.
@click.group(help="Command line interface for the tilebench Python package.")
def cli():
    """Execute the main morecantile command"""


@cli.command()
@options.file_in_arg
@click.argument("tile", type=str)
@click.option("--tilesize", type=int, default=256)
@click.option(
    "--config",
    "config",
    metavar="NAME=VALUE",
    multiple=True,
    callback=options._cb_key_val,
    help="GDAL configuration options.",
)
def profile(input, tile, tilesize, config):
    """Profile COGReader Mercator Tile read."""
    tile_z, tile_x, tile_y = list(map(int, tile.split("-")))

    @profiler(quiet=True, add_to_return=True, config=config)
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
