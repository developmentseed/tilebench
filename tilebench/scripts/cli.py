"""tilebench CLI."""

import click
import json
from random import sample

import mercantile
import rasterio
from rasterio.rio import options
from rasterio.warp import transform_bounds
from rio_tiler.constants import WGS84_CRS
from rio_tiler import utils
from rio_tiler import mercator
from rio_tiler.io import cogeo as COGReader
from supermercado.burntiles import tile_extrema

from tilebench import profile as profiler


# The CLI command group.
@click.group(help="Command line interface for the tilebench Python package.")
def cli():
    """Execute the main morecantile command"""


@cli.command()
@options.file_in_arg
@click.option("--ensure-global-maxzoom", default=False, is_flag=True)
@click.option("--tilesize", type=int, default=256)
def get_zooms(input, ensure_global_maxzoom, tilesize):
    """Get Mercator Zoom levels."""
    with rasterio.open(input) as src_dst:
        min_zoom, max_zoom = mercator.get_zooms(
            src_dst, ensure_global_max_zoom=ensure_global_maxzoom, tilesize=tilesize
        )
        click.echo(json.dumps(dict(minzoom=min_zoom, maxzoom=max_zoom)))


@cli.command()
@options.file_in_arg
@click.argument("tile", type=str)
@click.option("--tilesize", type=int, default=256)
def get_overview_level(input, tile, tilesize):
    """Get internal Overview level."""
    tile_z, tile_x, tile_y = list(map(int, tile.split("-")))
    mercator_tile = mercantile.Tile(x=tile_x, y=tile_y, z=tile_z)
    tile_bounds = mercantile.xy_bounds(mercator_tile)

    with rasterio.open(input) as src_dst:
        level = utils.get_overview_level(src_dst, tile_bounds, tilesize, tilesize)
        click.echo(level)


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
    """Get internal Overview level."""
    tile_z, tile_x, tile_y = list(map(int, tile.split("-")))

    @profiler(config=config)
    def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
        COGReader.tile(src_path, x, y, z, tilesize=tilesize)

    _read_tile(input, tile_x, tile_y, tile_z, tilesize)


@cli.command()
@options.file_in_arg
@click.argument("zoom", type=int)
def random(input, zoom):
    """Get random tile."""

    with rasterio.open(input) as src_dst:
        bounds = transform_bounds(
            src_dst.crs, WGS84_CRS, *src_dst.bounds, densify_pts=21
        )
        extrema = tile_extrema(bounds, zoom)

    def _get_tiles(extrema):
        for _, x in enumerate(range(extrema["x"]["min"], extrema["x"]["max"])):
            for _, y in enumerate(range(extrema["y"]["min"], extrema["y"]["max"])):
                yield [x, y, zoom]

    tiles = list(_get_tiles(extrema))

    tile = sample(tiles, 1)[0]
    click.echo(json.dumps(tile))
