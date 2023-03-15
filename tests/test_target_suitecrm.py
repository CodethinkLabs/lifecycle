""" Basic functionality tests for SuiteCRM target

This checks the logic of config settings and mocks an SuiteCRM server connection.
"""

from datetime import datetime, timedelta
import json
import math
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


def test_basic_config_creation(basicConfig):
    target = TargetSuiteCRM(basicConfig, None)
    assert target


def test_basic_fetch(basicTarget, suitecrm_request):
    """Get all users, shows some very basic users"""
    suitecrm_data = [
        {
            "type": "User",
            "id": "c0ffee-cafe",
            "attributes": {
                "user_name": "foobar",
                "first_name": "Foo",
                "last_name": "Bar",
                "full_name": "Foo Bar",
                "email1": "foo.bar@example.org",
                "status": "Active",
            },
        },
    ]
    expected_users = {
        "foobar": User(
            "foobar",
            forename="Foo",
            surname="Bar",
            fullname="Foo Bar",
            email=("foo.bar@example.org",),
            locked=False,
        )
    }
    suitecrm_request(suitecrm_data)
    users = basicTarget.fetch_users()
    assert users == expected_users


def test_users_create(basicTarget, suitecrm_request):
    suitecrm_data = [
        {
            "type": "User",
            "id": "c0ffee-cafe",
            "attributes": {
                "user_name": "foobar",
                "first_name": "Foo",
                "last_name": "Bar",
                "full_name": "Foo Bar",
                "email1": "foo.bar@example.org",
                "status": "Active",
            },
        },
    ]
    suitecrm_request(suitecrm_data)
    users = basicTarget.fetch_users()
    diff = basicTarget.calculate_difference()
    basicTarget.users_create(diff)
    assert False


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
def fixture_request(mocker):
    def _request_server(server_data: dict):
        def _suitecrm_request(method, url, **kwargs):
            """We have to stimulate requests.request.
            There's way too much to cover though if we try to mock the whole thing.
            Thankfully we only need certain methods with certain URLs"""

            # Assuming we have a valid server we only need to pass through the endpoints
            # The endpoint is the section of the url starting with "/Api"
            endpoint = "".join(url.partition("/Api")[1:])

            ## Ensure that we don't allow redirects
            # if not kwargs["allow_redirects"] or allow_redirects == True:
            #    raise LifecycleException(
            #        "Unexpected redirect. (Redirecting is true by default)"
            #    )

            if method == "DELETE":
                raise MethodException("Unexpected use of method DELETE")
            elif method == "GET":
                mock_result = _suitecrm_GET(server_data, endpoint, **kwargs)
            elif method == "PATCH":
                mock_result = _suitecrm_PATCH(server_data, endpoint, **kwargs)
            elif method == "POST":
                mock_result = _suitecrm_POST(server_data, endpoint, **kwargs)
            else:
                raise MethodException("Invalid method used")

            return mock_result

        mocker.patch("requests.request", side_effect=_suitecrm_request)

    return _request_server


def _mock_response(data, exception=None):
    # Used in Response:
    # .text, .json(), .raise_for_status()
    print(f"Response Data: {data}")
    response = MagicMock()
    response.json.return_value = data
    response.text = json.dumps(data, indent=2)
    if exception:
        response.raise_for_status.side_effect = exception
    return response


def _data_json(data):
    return {
        "data": data,
    }


def _filter_data(data, data_type):
    return list([entry for entry in data if entry["type"] == data_type])


def _paginated_data(data, pagesize, page):
    # page index starts from 1
    start = pagesize * (page - 1)
    end = pagesize * page
    total_pages = math.ceil(len(data) / pagesize)
    returned_data = [data[i] for i in range(start, end) if i < len(data)]
    return {
        "meta": {
            "total-pages": total_pages,
        },
        "data": returned_data,
    }


def _suitecrm_GET(server_data, endpoint, **kwargs):
    """Thankfully GET isn't so bad. We're just returning a json. Life is good"""
    if endpoint == "/Api/V8/module/Users":
        # The request could be paginated
        if "params" in kwargs:
            pagesize = kwargs["params"]["page[size]"]
            page = kwargs["params"]["page[number]"]
            response_data = _paginated_data(
                _filter_data(server_data, "User"), pagesize, page
            )
        else:
            response_data = _data_json(_filter_data(server_data, "User"))
        return _mock_response(response_data)


def _suitecrm_PATCH(server_data, endpoint, **kwargs):
    """Patching needs a json. So that makes all our lives easier"""
    if not kwargs["json"]:
        raise MethodException("PATCH requires a json")

    ### This is where I'm up to


def _suitecrm_POST(server_data, endpoint, **kwargs):
    """Posting is a mixed bag. Sometimes we need a json, sometimes we don't"""
    if endpoint == "/Api/access_token":
        # Handle this one first. We're checking that the token type is a string
        token_expiry = (datetime.now() + timedelta(hours=1)).timestamp()
        access_token = jwt.encode(
            payload={
                "exp": token_expiry,
            },
            key="",
        )
        return _mock_response(
            {
                "access_token": access_token,
            }
        )
    if not kwargs["json"]:
        raise MethodException("Can't POST without a json unless authenticating")

    if endpoint == "Api/V8/Module":
        new_user = kwargs["json"]
        a = _mock_response(new_user)
        print(f"new_user: {a}")
        return a


@pytest.fixture(name="basicTarget")
def test_config_source_creation(basicConfig, basicSource):
    target = TargetSuiteCRM(basicConfig, basicSource)
    return target
