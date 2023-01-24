"""Setup file for lifecyle application"""

from setuptools import setup, find_packages


setup(
    name="lifecycle",
    packages=find_packages(exclude=("tests", "tests.*")),
    install_requires=[
        "addict",
        "ldap3",
        "pyyaml"
    ],
    extras_require={
        "dev": [
            "black",
            "pylint",
            "pytest",
            "pytest-cov",
            "pytest-mock",
            "pytest-pylint"
        ],
    },
    python_requires=">3.4",
    package_dir={"lifecycle": "lifecycle"},
    entry_points={
        "console_scripts": [
            "lifecycle = lifecycle.cli:main",
        ],
    },
)
