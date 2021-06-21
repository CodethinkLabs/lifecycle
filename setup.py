from setuptools import setup, find_packages

# Parse requirements files
with open("requirements.txt") as f:
    install_requirements = f.read().splitlines()

with open("requirements-dev.txt") as f:
    dev_requirements = f.read().splitlines()


setup(
    name="lifecycle",
    packages=find_packages(exclude=("tests", "tests.*")),
    install_requires=install_requirements,
    extras_require={
        "dev": dev_requirements,
    },
    package_dir={"lifecycle": "lifecycle"},
    entry_points={
        "console_scripts": [
            "lifecycle = lifecycle.cli:main",
        ],
    },
)
