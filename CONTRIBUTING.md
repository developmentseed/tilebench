# Development - Contributing

Issues and pull requests are more than welcome: https://github.com/developmentseed/tilebench/issues

We recommand using [`uv`](https://docs.astral.sh/uv) as project manager for development.

See https://docs.astral.sh/uv/getting-started/installation/ for installation 

### dev install

```bash
git clone https://github.com/developmentseed/tilebench.git
cd tilebench

uv sync
```

You can then run the tests with the following command:

```sh
uv run pytest --cov tilebench --cov-report term-missing -s -vv
```

This repo is set to use `pre-commit` to run *isort*, *flake8*, *pydocstring*, *black* ("uncompromising Python code formatter") and mypy when committing new code.

```bash
uv run pre-commit install
uv run pre-commit run --all-files 
```
