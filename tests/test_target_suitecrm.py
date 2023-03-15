""" Basic functionality tests for SuiteCRM target

This checks the logic of config settings and mocks an SuiteCRM server connection.
"""
import pytest

from lifecycle.model_diff import ModelDifference
from lifecycle.models import User
from lifecycle.source_staticconfig import SourceStaticConfig
from lifecycle.target_suitecrm import TargetSuiteCRM

from .mock_suitecrm_server import MethodException, MockSuiteCRMServer


@pytest.fixture(name="basic_config")
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


def test_basic_config_creation(basic_config):
    """Make sure that a target can be created from a basic config"""
    target = TargetSuiteCRM(basic_config, None)
    assert target


def test_basic_fetch(basic_target, suitecrm_server):
    """Get all users, shows some very basic users"""
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
    suitecrm_server()
    users = basic_target.fetch_users()
    assert users == expected_users


def test_users_create(basic_target, suitecrm_server):
    """Create some users"""
    server = suitecrm_server()
    diff = basic_target.calculate_difference()
    old_users = server.search_by_type("User")
    basic_target.users_create(diff)
    new_users = server.search_by_type("User")
    assert len(new_users) > len(old_users)


def test_users_update(basic_config, suitecrm_server):
    """Update the attributes of an existing user and check the changes have
    been made
    """
    suitecrm_data = [
        {
            "type": "User",
            "id": "c0ffee-cafe",
            "attributes": {
                "user_name": "basicuser",
                "first_name": "Basic",
                "last_name": "Bob",
                "full_name": "Basic Bob",
                "email1": "basic.bob@example.org",
                "status": "Active",
            },
        },
    ]
    server = suitecrm_server(suitecrm_data)
    target = TargetSuiteCRM(basic_config, None)
    diff = ModelDifference(
        added_users={},
        removed_users={},
        unchanged_users={},
        changed_users={
            "basicuser": User(
                "basicuser",
                forename="Deluxe",
                surname="Bob",
                email=("basic.bob@example.org",),
            )
        },
    )
    target.users_sync(diff)
    users = server.search_by_type("User")
    assert users[0]["attributes"]["first_name"] == "Deluxe"


def test_users_delete(basic_config, suitecrm_server):
    """Delete a user and check it's been deleted"""
    suitecrm_data = [
        {
            "type": "User",
            "id": "c0ffee-cafe",
            "attributes": {
                "user_name": "basicuser",
                "first_name": "Basic",
                "last_name": "Bob",
                "full_name": "Basic Bob",
                "email1": "basic.bob@example.org",
                "status": "Active",
            },
        },
    ]
    server = suitecrm_server(suitecrm_data)
    target = TargetSuiteCRM(basic_config, None)
    diff = ModelDifference(
        added_users={},
        changed_users={},
        unchanged_users={},
        removed_users={
            "basicuser": User(
                "basicuser",
                forename="Basic",
                surname="Bob",
                email=("basic.bob@example.org",),
            )
        },
    )
    target.users_cleanup(diff)
    users = server.search_by_type("User")
    assert len(users) == 0


@pytest.fixture(name="basic_source")
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


@pytest.fixture(name="suitecrm_server")
def fixture_suitecrm_server(mocker):
    """Patches requests.request so that it gets routed through a MockSuiteCRMServer"""

    def _request_server(server_data: dict = None):
        server = MockSuiteCRMServer(server_data)

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

            if method == "GET":
                return server.mock_get(endpoint, **kwargs)
            if method == "PATCH":
                return server.mock_patch(endpoint, **kwargs)
            if method == "POST":
                return server.mock_post(endpoint, **kwargs)

            raise MethodException(f"Invalid method used '{method}'")

        mocker.patch("requests.request", side_effect=_suitecrm_request)
        return server

    return _request_server


@pytest.fixture(name="basic_target")
def fixture_basic_target(basic_config, basic_source):
    """Create a TargetSuiteCRM with default config"""
    target = TargetSuiteCRM(basic_config, basic_source)
    return target
