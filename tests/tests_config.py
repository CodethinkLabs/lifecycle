""" Basic functionality tests """

import pytest
from lib.ConfigReader import ConfigReader


def test_config_folder():
    config = ConfigReader("tests/config/working")
    assert config.config["test"]["working"]
    assert config.config["test2"]["working"]


def test_config_file():
    config = ConfigReader("tests/config/working/0.yml")
    assert config.config["test"]["working"]


def test_config_broken():
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        config = ConfigReader("tests/config/broken.yml")
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
