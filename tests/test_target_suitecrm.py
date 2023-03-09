""" Basic functionality tests for SuiteCRM target

This checks the logic of config settings and mocks an SuiteCRM server connection.
"""

from unittest.mock import MagicMock, PropertyMock

import jwt
import pytest

from lifecycle import LifecycleException, SourceBase
from lifecycle.models import Group, User
from lifecycle.source_staticconfig import SourceStaticConfig
from lifecycle.target_suitecrm import TargetSuiteCRM


class MethodException(LifecycleException):
    """Called when a method is called incorrectly or isn't valid"""


@pytest.fixture(name="basicConfig")
def fixture_config():
    """Create a config"""
    config = {
        "url": "127.0.0.1:8080",
        "api_username": "user",
        "api_password": "bitnami",
        "api_client_id": "asd",
        "api_client_secret": "secret",
    }
    return config


"""Make sure that a target can be created from a basic config"""


def test_basic_config_creation():
    target = TargetSuiteCRM(basicConfig, None)
    assert target


@pytest.fixture(name="basicSource")
def fixture_source():
    """We need a source to set up a proper SuiteCRM target"""
    source = SourceStaticConfig(
        config={
            "groups": [{"name": "foobar"}],
            "users": [
                {
                    "username": "admin",
                    "forename": "admin",
                    "surname": "alice",
                    "email": ["admin@test.com"],
                    "groups": ["foobar"],
                },
                {
                    "username": "basicuser",
                    "forename": "basic",
                    "surname": "bob",
                    "groups": ["foobar"],
                },
            ],
        }
    )
    return source


@pytest.fixture(name="suitecrm_request")
def fixture_request(mock):
    def _request_server(data: json):
        def _suitecrm_request(method, url, **kwargs):
            """We have to stimulate requests.request.
            There's way too much to cover though if we try to mock the whole thing.
            Thankfully we only need certain methods with certain URLs"""

            # Assuming we have a valid server we only need to pass through the endpoints
            # The endpoint is the section of the url starting with "/Api"
            endpoints = "".join(url.partition("/Api")[1:])

            # Ensure that we don't allow redirects
            if not kwargs["allow_redirects"] or allow_redirects == True:
                raise LifecycleException(
                    "Unexpected redirect. (Redirecting is true by default)"
                )

            if method == "DELETE":
                raise MethodException("Unexpected use of method DELETE")
            elif method == "GET":
                mock_result = _suitecrm_GET(data, endpoint, **kwargs)
            elif method == "PATCH":
                mock_result = _suitecrm_PATCH(data, endpoint, **kwargs)
            elif method == "POST":
                mock_result = _suitecrm_POST(data, endpoint, **kwargs)
            else:
                raise MethodException("Invalid method used")

        mocker.patch("requests.request", side_effect=_suite_request)

    return _request_server


def _suitecrm_GET(data, endpoint, **kwargs):
    """Thankfully GET isn't so bad. We're just returning a json. Life is good"""
    if endpoint == "/Api/V8/module/Users":
        return data


def _suitecrm_PATCH(data, endpoint, **kwargs):
    """Patching needs a json. So that makes all our lives easier"""
    if not kwargs["json"]:
        raise MethodException("PATCH requires a json")

    ### This is where I'm up to


def _suitecrm_POST(data, endpoint, **kwargs):
    """Posting is a mixed bag. Sometimes we need a json, sometimes we don't"""
    if endpoint == "/Api/access_token":
        # Handle this one first. We're checking that the token type is a string
        return str

    if not kwargs["json"]:
        raise MethodException("Can't POST without a json unless authenticating")

    if endpoint == "Api/V8/Module":
        new_user = kwargs["json"]


@pytest.fixture(name="basicTarget")
def test_config_source_creation(basicConfig, basicSource):
    target = TargetSuiteCRM(basicConfig, basicSource)
    return target
