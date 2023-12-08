"""Setup file for lifecyle application"""

from setuptools import find_packages, setup


setup(
    name="lifecycle",
    packages=find_packages(exclude=("tests", "tests.*")),
    install_requires=["addict", "ldap3", "PyJWT", "pyyaml", "requests"],
    extras_require={
        "dev": [
            "pre-commit",
            "pylint",
            "pytest",
            "pytest-cov",
            "pytest-mock",
            "pytest-pylint",
            "black",
        ],
    },
    python_requires=">=3.7",
    package_dir={"lifecycle": "lifecycle"},
    entry_points={
        "console_scripts": [
            "lifecycle = lifecycle.cli:main",
        ],
    },
)
