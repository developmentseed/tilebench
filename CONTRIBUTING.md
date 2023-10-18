# Development - Contributing

Issues and pull requests are more than welcome: https://github.com/developmentseed/tilebench/issues

**dev install**

```bash
git clone https://github.com/developmentseed/tilebench.git
cd tilebench
python -m pip install -e ".[dev,test]"
```

You can then run the tests with the following command:

```sh
python -m pytest --cov tilebench --cov-report term-missing -s -vv
```

This repo is set to use `pre-commit` to run *isort*, *flake8*, *pydocstring*, *black* ("uncompromising Python code formatter") and mypy when committing new code.

```bash
$ pre-commit install
```
