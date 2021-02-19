"""Setup tilebench."""

from setuptools import find_packages, setup

with open("README.md") as f:
    long_description = f.read()

inst_reqs = [
    "boto3",
    "fastapi[all]",
    "geojson-pydantic",
    "loguru",
    "rasterio",
    "rio-tiler>=2.0,<2.1",
    "supermercado",
    "wurlitzer",
]
extra_reqs = {
    "test": ["pytest", "pytest-cov", "pytest-asyncio"],
    "dev": ["pytest", "pytest-cov", "pytest-asyncio", "pre-commit"],
}


setup(
    name="tilebench",
    version="0.2.1",
    description=u"",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.6",
    keywords="",
    author=u"Vincent Sarago",
    author_email="vincent@developmentseed.org",
    url="https://github.com/developmentseed/tilebench",
    license="MIT",
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
    zip_safe=False,
    install_requires=inst_reqs,
    extras_require=extra_reqs,
    entry_points="""
      [console_scripts]
      tilebench=tilebench.scripts.cli:cli
      """,
)
