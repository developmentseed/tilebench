"""Test CLI."""

import json
from unittest.mock import patch

from click.testing import CliRunner

from tilebench.scripts.cli import cli

COG_PATH = "https://noaa-eri-pds.s3.amazonaws.com/2022_Hurricane_Ian/20221002a_RGB/20221002aC0795145w325100n.tif"


def test_profile():
    """Should work as expected."""
    runner = CliRunner()

    result = runner.invoke(cli, ["profile", COG_PATH])
    assert not result.exception
    assert result.exit_code == 0
    log = json.loads(result.output)
    assert ["HEAD", "GET", "Timing"] == list(log)
    # Make sure we didn't cache any request when `--tile` is not provided
    assert "0-" in log["GET"]["ranges"][0]

    result = runner.invoke(
        cli,
        [
            "profile",
            COG_PATH,
            "--tilesize",
            512,
            "--zoom",
            11,
            "--reader",
            "rio_tiler.io.Reader",
        ],
    )
    assert not result.exception
    assert result.exit_code == 0
    log = json.loads(result.output)
    assert ["HEAD", "GET", "Timing"] == list(log)

    result = runner.invoke(
        cli, ["profile", COG_PATH, "--tilesize", 512, "--tile", "16-18229-26433"]
    )
    assert not result.exception
    assert result.exit_code == 0
    log = json.loads(result.output)
    assert ["HEAD", "GET", "Timing"] == list(log)

    result = runner.invoke(
        cli, ["profile", COG_PATH, "--add-kernels", "--add-stdout", "--add-cprofile"]
    )
    assert not result.exception
    assert result.exit_code == 0
    log = json.loads(result.output)
    assert [
        "HEAD",
        "GET",
        "WarpKernels",
        "Timing",
        "cprofile",
        "logs",
    ] == list(log)


def test_get_zoom():
    """Should work as expected."""
    runner = CliRunner()

    result = runner.invoke(cli, ["get-zooms", COG_PATH])
    assert not result.exception
    assert result.exit_code == 0
    log = json.loads(result.output)
    assert ["minzoom", "maxzoom"] == list(log)

    result = runner.invoke(
        cli, ["get-zooms", COG_PATH, "--reader", "rio_tiler.io.Reader"]
    )
    assert not result.exception
    assert result.exit_code == 0
    log = json.loads(result.output)
    assert ["minzoom", "maxzoom"] == list(log)


def test_random():
    """Should work as expected."""
    runner = CliRunner()

    result = runner.invoke(cli, ["random", COG_PATH])
    assert not result.exception
    assert result.exit_code == 0
    assert "-" in result.output

    result = runner.invoke(
        cli, ["random", COG_PATH, "--zoom", 14, "--reader", "rio_tiler.io.Reader"]
    )
    assert not result.exception
    assert result.exit_code == 0
    assert "14-" in result.output


@patch("click.launch")
def test_viz(launch):
    """Should work as expected."""
    runner = CliRunner()

    launch.return_value = True

    result = runner.invoke(cli, ["random", COG_PATH])
    assert not result.exception
    assert result.exit_code == 0
    assert "-" in result.output

    result = runner.invoke(
        cli, ["random", COG_PATH, "--zoom", 14, "--reader", "rio_tiler.io.Reader"]
    )
    assert not result.exception
    assert result.exit_code == 0
    assert "14-" in result.output
