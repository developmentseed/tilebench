
## 0.8.2 (2022-11-21)

* update hatch config

## 0.8.1 (2022-10-31)

* fix issue with min/max zoom when there is no overviews
* calculate windows from block_shapes

## 0.8.0 (2022-10-25)

* update rio-tiler/rasterio dependencies
* remove python 3.7 support
* add python 3.10 support
* add image endpoint to show the data footprint
* switch from mapbox to maplibre

## 0.7.0 (2022-06-14)

* add `cProfile` stats

## 0.6.1 (2022-04-19)

* Remove usage of `VSIStatsMiddleware` in `tilebench viz`

## 0.6.0 (2022-04-19)

* switch to pyproject.toml

## 0.5.1 (2022-03-04)

* make sure we don't cache previous request when using `tilebench profile` without `--tile` option

## 0.5.0 (2022-02-28)

* update rio-tiler requirement
* add `reader` option

## 0.4.1 (2022-02-14)

* update Fastapi requirement
* use WarpedVRT to get dataset bounds in epsg:4326

## 0.4.0 (2021-12-13)

* update rio-tiler's version requirement
* add more information about the raster in the Viz web page (author @drnextgis, https://github.com/developmentseed/tilebench/pull/14)
* fix bug for latest GDAL/rasterio version
* add default STAMEN basemap in *viz* and remove mapbox token/style options.
* update fastapi requirement

## 0.3.0 (2021-03-05)

* add `exclude_paths` options in `VSIStatsMiddleware` to exclude some endpoints (author @drnextgis, https://github.com/developmentseed/tilebench/pull/10)
* renamed `ressources`  to `resources`

## 0.2.1 (2021-02-19)

* fix typo in UI

## 0.2.0 (2021-01-28)

* add warp-kernels in output in `profile` CLI
* add rasterio/curl stdout in output
* add dataread time in Viz

## 0.1.1 (2021-01-27)

* update requirements

## 0.1.0 (2021-01-04)

* add web UI for VSI stats visualization
* add starlette middleware

## 0.0.2 (2020-12-15)

* Update for rio-tiler==2.0.0rc3

## 0.1.0 (2020-07-13)

* Initial release
