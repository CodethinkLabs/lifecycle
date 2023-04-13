""" Basic functionality tests for base targets and sources """

from unittest.mock import patch

import pytest

import lifecycle.__init__


class DummyBase(lifecycle._Base):
    """Barebones lifecycle Base. Only exists to allow fields to be checked."""

    # pylint: disable=protected-access

    mandatory_fields = {"dummy_mandatory"}
    optional_fields = {"dummy_optional"}

    default_config = {
        "dummy_optional": "optional",
    }

    def fetch_users(self, refresh=False):
        pass


def test_bad_configure_function():
    """Ensure that we raise an exception when the configure function
    doesn't return the correct type
    """
    bad_return_value = ""

    class BadConfigureFunctionBase(DummyBase):
        """Base class with a configure function that doesn't return a supported type"""

        def configure(self, config):
            return bad_return_value

    config = {"dummy_mandatory": "4"}
    with pytest.raises(lifecycle.ConfigUnexpectedType) as excinfo:
        BadConfigureFunctionBase(config)
    assert excinfo.value.config == bad_return_value


def test_incorrect_config():
    """Ensure that we raise an exception when the config isn't a dict"""
    incorrect_config = ()
    with pytest.raises(lifecycle.ConfigUnexpectedInputType) as excinfo:
        DummyBase(incorrect_config)
    assert excinfo.value.config == incorrect_config


def test_check_fields():
    """Ensure that we do require mandatory fields"""
    mandatory_field_config = {"dummy_mandatory": "mandatory"}
    mandatory_base = DummyBase(mandatory_field_config)
    assert mandatory_base
    assert mandatory_base.config["dummy_mandatory"] == "mandatory"

    # Make sure that we also accept optional fields
    full_field_config = {
        "dummy_mandatory": "mandatory",
        "dummy_optional": "optional2",
    }

    full_field_base = DummyBase(full_field_config)
    assert full_field_base
    assert full_field_base.config["dummy_optional"] == "optional2"


def test_missing_fields():
    """Check that we raise an exception when missing a mandatory field"""
    missing_fields_config = {}
    with pytest.raises(lifecycle.ConfigMissingFields) as excinfo:
        DummyBase(missing_fields_config)
    assert excinfo.value.missing_fields == {"dummy_mandatory"}


def test_unexpected_fields():
    """Check that we raise an exception when given an unexpected field"""
    unexpected_fields_config = {
        "dummy_mandatory": "correct",
        "unexpected_field": "unexpected",
    }
    with pytest.raises(lifecycle.ConfigUnexpectedFields) as excinfo:
        DummyBase(unexpected_fields_config)
    assert excinfo.value.unexpected_fields == {"unexpected_field"}


class DummySource(lifecycle.SourceBase):
    """Need a dummy source so we can make an instance of it for testing"""

    def __init__(self, config=None):
        if config is None:
            config = {}
        super().__init__(config)

    def fetch_users(self, refresh=False):
        pass

    def fetch(self):
        pass


class DummyTarget(lifecycle.TargetBase):
    """Need a dummy target so we can make an instance of it for testing.
    Adds stages so that they can be tested"""

    optional_fields = {"stages"}

    default_config = {"stages": ["users_create", "users_sync", "users_cleanup"]}

    def __init__(self, config=None, source=DummySource()):
        if config is None:
            config = {}
        super().__init__(config, source)

    def fetch_users(self, refresh=False):
        pass

    def calculate_difference(self, groups_patterns=None):
        """We don't calculate a difference since we're only testing
        whether stages are run"""
        return ()


@patch("logging.warning")
def test_no_stages_set(mock_warning):
    """Check that we are warned if no stages are set"""
    no_stages_config = {"stages": []}

    no_stages_target = DummyTarget(no_stages_config)
    no_stages_target.process_stages([])
    assert "No stages" in mock_warning.call_args_list[0][0][0]


@patch("logging.warning")
@pytest.mark.parametrize(
    "implemented_stages, unimplemented_stage",
    [
        (["users_create", "users_cleanup"], "users_sync"),
        (["users_create", "users_sync"], "users_cleanup"),
        (["users_cleanup", "users_sync"], "users_create"),
    ],
)
def test_unimplented_stages(mock_warning, implemented_stages, unimplemented_stage):
    """Test that we do get warned if we miss out a stage"""

    class MissingFunctionBase(DummyTarget):
        """We want a target which has implemented all stages except for one.
        This is done in the following steps:
        - Create dud function with the same signature
        - Change dud function's name to match the stage that it's "implementing"
        """

        def __init__(self, *args):
            super().__init__(*args)
            for name in implemented_stages:
                passed_method = self.create_dud_method()
                setattr(MissingFunctionBase, name, passed_method)

        @staticmethod
        def create_dud_method():
            """We create a dud function with a signature that matches
            that of user_create, user_cleanup, and users_sync"""

            def _method(self, dud_difference):
                # pylint: disable=unused-argument
                pass

            return _method

    missing_base = MissingFunctionBase()
    missing_base.process_stages([])
    print(mock_warning.call_args_list)
    assert unimplemented_stage in mock_warning.call_args_list[0][0]
