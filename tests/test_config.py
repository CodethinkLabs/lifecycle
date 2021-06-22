""" Basic functionality tests for config reader """

import pytest
from lifecycle.config_reader import ConfigReader


def test_config_folder():
    """Test a folder full of working config files"""
    config = ConfigReader("tests/config/working", raw=True)
    assert config.config_raw["test"]["working"]
    assert config.config_raw["test2"]["working"]


def test_config_file():
    """Test a single working config file"""
    config = ConfigReader("tests/config/working/0.yml", raw=True)
    assert config.config_raw["test"]["working"]


def test_config_broken():
    """Test a single broken config file"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        ConfigReader("tests/config/broken.yml")
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_config_environment_variable(monkeypatch):
    """Test replacing an environment variable in a config file"""
    monkeypatch.setenv("TEST_VARIABLE", "banana")
    config = ConfigReader("tests/config/working/1.yml")
    assert config.config["test2"]["banana"] == "banana"


def test_config_environment_variable_not_provided():
    """Test replacing an nonexistant environment variable in a config file"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        ConfigReader("tests/config/working/1.yml")
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
