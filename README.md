# tilebench

<p align="center">
  <img src="https://user-images.githubusercontent.com/10407788/145784365-7ce635d1-3971-4a94-856f-cd8b081f10c1.png" style="max-width: 800px;" alt="tilebench"></a>
</p>
<p align="center">
  <em>Inspect HEAD/LIST/GET requests withing Rasterio</em>
</p>
<p align="center">
  <a href="https://github.com/developmentseed/tilebench/actions?query=workflow%3ACI" target="_blank">
      <img src="https://github.com/developmentseed/tilebench/workflows/CI/badge.svg" alt="Test">
  </a>
  <a href="https://codecov.io/gh/developmentseed/tilebench" target="_blank">
      <img src="https://codecov.io/gh/developmentseed/tilebench/branch/master/graph/badge.svg" alt="Coverage">
  </a>
  <a href="https://pypi.org/project/tilebench" target="_blank">
      <img src="https://img.shields.io/pypi/v/tilebench?color=%2334D058&label=pypi%20package" alt="Package version">
  </a>
  <a href="https://pypistats.org/packages/tilebench" target="_blank">
      <img src="https://img.shields.io/pypi/dm/tilebench.svg" alt="Downloads">
  </a>
  <a href="https://github.com/developmentseed/tilebench/blob/master/LICENSE" target="_blank">
      <img src="https://img.shields.io/github/license/developmentseed/tilebench.svg" alt="Downloads">
  </a>
</p>

---

**Source Code**: <a href="https://github.com/developmentseed/tilebench" target="_blank">https://github.com/developmentseed/tilebench</a>

---


Inspect HEAD/LIST/GET requests withing Rasterio.

Note: In GDAL 3.2, logging capabilities for /vsicurl, /vsis3 and the like was added (ref: https://github.com/OSGeo/gdal/pull/2742).

## Install

You can install `tilebench` using pip

```bash
$ pip install -U pip
$ pip install -U tilebench
```

or install from source:

```bash
$ git clone https://github.com/developmentseed/tilebench.git
$ cd tilebench
$ pip install -U pip
$ pip install -e .
```

## API

```python
from tilebench import profile
import rasterio

@profile()
def info(src_path: str):
    with rasterio.open(src_path) as src_dst:
        return src_dst.meta

meta = info("https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif")

> 2020-07-13T16:59:05.685976-0400 | TILEBENCH | {"LIST": {"count": 0}, "HEAD": {"count": 1}, "GET": {"count": 1, "bytes": 16384, "ranges": ["0-16383"]}, "Timing": 0.8030309677124023}
```

```python
from tilebench import profile
from rio_tiler.io import COGReader

@profile()
def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
    with COGReader(src_path) as cog:
        return cog.tile(x, y, z, tilesize=tilesize)

data, mask = _read_tile(
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif",
    2314,
    1667,
    12,
)

> 2020-07-13T16:59:42.654071-0400 | TILEBENCH | {"LIST": {"count": 0}, "HEAD": {"count": 1}, "GET": {"count": 3, "bytes": 1464479, "ranges": ["0-16383", "33328080-34028784", "36669144-37416533"]}, "Timing": 3.007672071456909}
```

## Command Line Interface (CLI)

```
$ tilebench --help
Usage: tilebench [OPTIONS] COMMAND [ARGS]...

  Command line interface for the tilebench Python package.

Options:
  --help  Show this message and exit.

Commands:
  get-zooms  Get Mercator Zoom levels.
  profile    Profile COGReader Mercator Tile read.
  random     Get random tile.
  viz        WEB UI to visualize VSI statistics for a web mercator tile request
```

#### Examples
```
$ tilebench get-zooms https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif | jq
{
  "minzoom": 7,
  "maxzoom": 12
}

$ tilebench random https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif --zoom 12
12-2314-1667

$ tilebench profile https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif --tile 12-2314-1667 --config GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR | jq
{
  "LIST": {
    "count": 0
  },
  "HEAD": {
    "count": 1
  },
  "GET": {
    "count": 3,
    "bytes": 1464479,
    "ranges": [
      "0-16383",
      "33328080-34028784",
      "36669144-37416533"
    ]
  },
  "Timing": 2.377608060836792
}

$ tilebench profile https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif --tile 12-2314-1667 --config GDAL_DISABLE_READDIR_ON_OPEN=FALSE | jq
{
  "LIST": {
    "count": 1
  },
  "HEAD": {
    "count": 8
  },
  "GET": {
    "count": 11,
    "bytes": 1464479,
    "ranges": [
      "0-16383",
      "33328080-34028784",
      "36669144-37416533"
    ]
  },
  "Timing": 7.09281587600708
}
```


## Starlette Middleware

**Warning**: This is highly experimental and should not be used in production (https://github.com/developmentseed/tilebench/issues/6)

In addition of the `viz` CLI we added a starlette middleware to easily integrate VSI statistics in your web services.

```python
from fastapi import FastAPI

from tilebench.middleware import VSIStatsMiddleware

app = FastAPI()
app.add_middleware(VSIStatsMiddleware)
```

The middleware will add a `vsi-stats` entry in the response `headers` in form of:

```
vsi-stats: list;count=1, head;count=1, get;count=2;size=196608, ranges; values=0-65535|65536-196607
```

Some paths may be excluded from being handeld by the middleware by the `exclude_paths` argument:

```python
app.add_middleware(VSIStatsMiddleware, exclude_paths=["/foo", "/bar"])
```

## GDAL config options

- **GDAL_DISABLE_READDIR_ON_OPEN**: Allow or Disable listing of files in the directory (e.g external overview)
- **GDAL_INGESTED_BYTES_AT_OPEN**: Control how many bytes GDAL will ingest when opening a dataset (useful when a file has a big header)
- **CPL_VSIL_CURL_ALLOWED_EXTENSIONS**: Limit valid external files
- **GDAL_CACHEMAX**: Cache size
- **GDAL_HTTP_MERGE_CONSECUTIVE_RANGES**
- **VSI_CACHE**
- **VSI_CACHE_SIZE**

See the full list at https://gdal.org/user/configoptions.html

## Internal tiles Vs Mercator grid

```
$ tilebench viz https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif --config GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR
```

![](https://user-images.githubusercontent.com/10407788/103528918-17180880-4e85-11eb-91b3-d60659b15e80.png)

Blue lines represent the mercator grid for a specific zoom level and the red lines represent the internal tiles bounds

We can then click on a mercator tile and see how much requests GDAL/RASTERIO does.

![](https://user-images.githubusercontent.com/10407788/103529132-65c5a280-4e85-11eb-96e2-f59e915c8ed8.png)

## Docker

Ready to use docker image can be found on Github registry.

- https://github.com/developmentseed/tilebench/pkgs/container/tilebench

```bash
docker run \
  --volume "$PWD":/data \
  --platform linux/amd64 \
  --rm -it -p 8080:8080 ghcr.io/developmentseed/tilebench:latest \
  tilebench viz --host 0.0.0.0 https://noaa-eri-pds.s3.us-east-1.amazonaws.com/2020_Nashville_Tornado/20200307a_RGB/20200307aC0865700w360900n.tif
```

## Contribution & Development

Issues and pull requests are more than welcome.

**dev install**

```bash
$ git clone https://github.com/developmentseed/tilebench.git
$ cd tilebench
$ pip install -e .[dev]
```

**pre-commit**

This repo is set to use `pre-commit` to run *isort*, *flake8*, *pydocstring*, *black* ("uncompromising Python code formatter") and mypy when committing new code.

```
$ pre-commit install

$ git add .

$ git commit -m'my change'
isort....................................................................Passed
black....................................................................Passed
Flake8...................................................................Passed
Verifying PEP257 Compliance..............................................Passed
mypy.....................................................................Passed

$ git push origin
```

## License

See [LICENSE](https://github.com//developmentseed/tilebench/blob/master/LICENSE)

## Authors

See [contributors](https://github.com/developmentseed/tilebench/graphs/contributors) for a listing of individual contributors.

## Changes

See [CHANGES.md](https://github.com/developmentseed/tilebench/blob/master/CHANGES.md).
