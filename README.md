# tilebench

[![Packaging status](https://badge.fury.io/py/tilebench.svg)](https://badge.fury.io/py/tilebench)
[![CircleCI](https://circleci.com/gh/developmentseed/tilebench.svg?style=svg)](https://circleci.com/gh/developmentseed/tilebench)
[![codecov](https://codecov.io/gh/developmentseed/tilebench/branch/master/graph/badge.svg)](https://codecov.io/gh/developmentseed/tilebench)


Get LIST/GET requests statistics withing Rasterio. 

Note: This will be covered in NEXT GDAL release https://github.com/OSGeo/gdal/pull/2742

### API

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
from rio_tiler.io import cogeo as COGReader

@profile()
def _read_tile(src_path: str, x: int, y: int, z: int, tilesize: int = 256):
    return COGReader.tile(src_path, x, y, z, tilesize=tilesize)

data, mask = _read_tile(
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif",
    2314,
    1667,
    12,
)

> 2020-07-13T16:59:42.654071-0400 | TILEBENCH | {"LIST": {"count": 0}, "HEAD": {"count": 1}, "GET": {"count": 3, "bytes": 1464479, "ranges": ["0-16383", "33328080-34028784", "36669144-37416533"]}, "Timing": 3.007672071456909}
```

### CLI

```
$ tilebench --help
Usage: tilebench [OPTIONS] COMMAND [ARGS]...

  Command line interface for the tilebench Python package.

Options:
  --help  Show this message and exit.

Commands:
  get-overview-level  Get internal Overview level.
  get-zooms           Get Mercator Zoom levels.
  profile             Get internal Overview level.
  random              Get random tile.
```

```
$ tilebench get-zooms https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif | jq
{
  "minzoom": 8,
  "maxzoom": 12
}

$ tilebench random https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif 12                
[2314, 1667, 12]

$ tilebench profile https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif 12-2314-1667 --config GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR | jq
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

$ tilebench profile https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif 12-2314-1667 --config GDAL_DISABLE_READDIR_ON_OPEN=FALSE | jq
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

## More

#### aiocogeo
Using the great [aiocogeo](https://github.com/geospatial-jeff/aiocogeo) we can get more info about the COG internal structure.

```
$ aiocogeo info https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif

        FILE INFO: https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif

          PROFILE
            Width:            5490
            Height:           5490
            Bands:            1
            Dtype:            uint16
            Crs:              EPSG:32634
            Origin:           (699960.0, 3600000.0)
            Resolution:       (20.0, -20.0)
            BoundingBox:      (699960.0, 3490200.0, 809760.0, 3600000.0)
            Compression:      deflate
            Internal mask:    False
        
          IFD
                Id      Size           BlockSize     MinTileSize (KB)     MaxTileSize (KB)     MeanTileSize (KB)    
                0       5490x5490      512x512       0.531                414.187              261.824                       
                1       2745x2745      256x256       0.149                105.182              67.362                        
                2       1373x1373      256x256       0.149                105.244              58.2                          
                3       687x687        256x256       15.938               106.996              60.686                        
                4       344x344        256x256       13.559               66.76                36.114  
```

#### morecantile

Combining aiocogeo + [morecantile](https://github.com/developmentseed/morecantile) we can create a geojson of the internal tiles and compare with the mercator grid.

```
$ aiocogeo create-tms https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif

{
 "title": "Tile matrix for https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif",
 "identifier": "902b0312-2da6-4873-92f7-7a8b3480cef2",
 "supportedCRS": "http://www.opengis.net/def/crs/EPSG/0/32634",
 "tileMatrix": [
  {
   "identifier": "0",
   "topLeftCorner": [
    699960.0,
    3600000.0
   ],
   "tileWidth": 256,
   "tileHeight": 256,
   "matrixWidth": 2,
   "matrixHeight": 2,
   "scaleDenominator": 1139950.166112957
  },
  {
   "identifier": "1",
   "topLeftCorner": [
    699960.0,
    3600000.0
   ],
   "tileWidth": 256,
   "tileHeight": 256,
   "matrixWidth": 3,
   "matrixHeight": 3,
   "scaleDenominator": 570804.741110418
  },
  {
   "identifier": "2",
   "topLeftCorner": [
    699960.0,
    3600000.0
   ],
   "tileWidth": 256,
   "tileHeight": 256,
   "matrixWidth": 6,
   "matrixHeight": 6,
   "scaleDenominator": 285610.23826865054
  },
  {
   "identifier": "3",
   "topLeftCorner": [
    699960.0,
    3600000.0
   ],
   "tileWidth": 256,
   "tileHeight": 256,
   "matrixWidth": 11,
   "matrixHeight": 11,
   "scaleDenominator": 142857.14285714287
  },
  {
   "identifier": "4",
   "topLeftCorner": [
    699960.0,
    3600000.0
   ],
   "tileWidth": 512,
   "tileHeight": 512,
   "matrixWidth": 11,
   "matrixHeight": 11,
   "scaleDenominator": 71428.57142857143
  }
 ]
}
```

TMS levels are ordered from lower to higher, thus the `raw` tiles are the last TMS level (`4`)

```
# Internal raw tiles grids
$ aiocogeo create-tms https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif | morecantile tms-to-geojson --level 4 --collect > B05_raw.geojson

# Mercator grid at zoom 12
$ rio bounds https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/2020/S2A_34SGA_20200318_0_L2A/B05.tif  | supermercado burn 12 | mercantile shapes --collect > B05_zoom12.geojson
```

![](https://user-images.githubusercontent.com/10407788/84295959-4ba72a00-ab19-11ea-977f-726f37121dfb.png)

## Contribution & Development

Issues and pull requests are more than welcome.

**dev install**

```bash
$ git clone https://github.com/developmentseed/tilebench.git
$ cd tilebench
$ pip install -e .[dev]
```

**Python >=3.7 only**

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