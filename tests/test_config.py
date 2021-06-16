""" Basic functionality tests """

import pytest
from lib.ConfigReader import ConfigReader


def test_config_folder():
    config = ConfigReader("tests/config/working", raw=True)
    assert config.config_raw["test"]["working"]
    assert config.config_raw["test2"]["working"]


def test_config_file():
    config = ConfigReader("tests/config/working/0.yml", raw=True)
    assert config.config_raw["test"]["working"]


def test_config_broken():
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        ConfigReader("tests/config/broken.yml")
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_config_environment_variable(monkeypatch):
    monkeypatch.setenv("TEST_VARIABLE", "banana")
    config = ConfigReader("tests/config/working/1.yml")
    assert config.config["test2"]["banana"] == "banana"


def test_config_environment_variable_not_provided(monkeypatch):
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        ConfigReader("tests/config/working/1.yml")
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
