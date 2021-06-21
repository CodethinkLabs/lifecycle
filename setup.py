from setuptools import setup, find_packages

setup(
    name="lifecycle",
    packages=find_packages(exclude=("tests", "tests.*")),
    package_dir={"lifecycle": "lifecycle"},
    entry_points={
        "console_scripts": [
            "lifecycle = lifecycle.cli:main",
        ],
    },
)
