"""Setup file for lifecyle application"""

from setuptools import setup, find_packages

# Parse requirements files
with open("requirements.txt", "r", encoding="utf-8") as f:
    install_requirements = f.read().splitlines()

with open("requirements-dev.txt", "r", encoding="utf-8") as f:
    dev_requirements = f.read().splitlines()


setup(
    name="lifecycle",
    packages=find_packages(exclude=("tests", "tests.*")),
    install_requires=install_requirements,
    extras_require={
        "dev": dev_requirements,
    },
    python_requires=">3.4",
    package_dir={"lifecycle": "lifecycle"},
    entry_points={
        "console_scripts": [
            "lifecycle = lifecycle.cli:main",
        ],
    },
)
