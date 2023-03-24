""" Basic functionality tests for SuiteCRM target

This checks the logic of config settings and mocks an SuiteCRM server connection.
"""
import pytest

from lifecycle.model_diff import ModelDifference
from lifecycle.models import Group, User
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


def test_fetch_multi_email(basic_target, suitecrm_server):
    """Get a user with multiple E-mail addresses"""

    server = suitecrm_server([])
    user_id = server.create_user(
        {
            "user_name": "foobar",
            "first_name": "Foo",
            "last_name": "Bar",
            "full_name": "Foo Bar",
            "status": "Active",
        }
    )
    server.assign_emails(user_id, ["foo.bar@example.org", "foo.bar@example.com"])
    users = basic_target.fetch_users()
    assert list(users.values())[0].email == (
        "foo.bar@example.org",
        "foo.bar@example.com",
    )


def test_create_multi_email(basic_target, suitecrm_server):
    """Create a user with multiple E-mail addresses"""
    emails = ("foo.bar@example.org", "foo.bar@example.com")
    user = User(
        "foobar",
        forename="Foo",
        surname="Bar",
        fullname="Foo Bar",
        email=emails,
    )
    server = suitecrm_server([])

    diff = ModelDifference(
        source_users={"foobar": user},
        target_users={},
        added_users={"foobar": user},
        removed_users={},
        unchanged_users={},
        changed_users={},
    )
    basic_target.users_create(diff)
    found_emails = server.search_by_type("EmailAddress")
    assert len(found_emails) == 2
    for email_entry in found_emails:
        assert email_entry["attributes"]["email_address"] in emails


def test_sync_multi_email(basic_target, suitecrm_server):
    """Update a user's E-mail addresses with multiple, completely different ones"""
    before_emails = ("foo.bar@example.org",)
    after_emails = ("foo.bar@example.com", "foo.bar@example.biz")
    before_user = User(
        "foobar",
        forename="Foo",
        surname="Bar",
        email=before_emails,
    )
    after_user = User(
        "foobar",
        forename="Foo",
        surname="Bar",
        email=after_emails,
    )
    diff = ModelDifference(
        source_users={"foobar": after_user},
        target_users={"foobar": before_user},
        added_users={},
        removed_users={},
        unchanged_users={},
        changed_users={"foobar": after_user},
    )
    # Note: default user in the server matches before_user
    server = suitecrm_server()
    basic_target.users_sync(diff)
    user_id = server.get_entry_by_attribute("user_name", "foobar")["id"]
    for entry in server.get_related_entries_for_module(user_id, "email_addresses"):
        assert entry["attributes"]["email_address"] in after_emails


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


def test_groups_fetch(basic_target, suitecrm_server):
    """Check security groups on the server are fetched to the user"""
    server = suitecrm_server()
    assert (
        server.data[0]["type"] == "User"
    ), "First entry in the server is not a User, this test needs updating"
    user_id = server.data[0]["id"]  # Assumes server has only one user
    group_id = server.create_record(
        {
            "data": {
                "type": "SecurityGroup",
                "attributes": {
                    "name": "TestGroup",
                    "description": "Testy Test Group",
                },
            }
        }
    )
    server.create_relationship("User", user_id, "SecurityGroup", group_id)
    fetched_users = basic_target.fetch_users()
    assert fetched_users["foobar"].groups == (
        Group("TestGroup", description="Testy Test Group"),
    )


def test_groups_sync(basic_config, suitecrm_server):
    """Replace a user's security groups with a completely different set of groups"""
    # Create a single user on the server, with a single group
    server = suitecrm_server()
    user_id = "0"
    group_id = server.create_record(
        {
            "data": {
                "type": "SecurityGroup",
                "attributes": {
                    "name": "TestGroup",
                },
            }
        }
    )
    server.create_relationship("User", user_id, "SecurityGroup", group_id)

    # Create a target whose source config has a user identical except for having different groups
    target = TargetSuiteCRM(
        basic_config,
        SourceStaticConfig(
            config={
                "groups": [
                    {"name": "bargroup"},
                    {"name": "bazgroup"},
                ],
                "users": [
                    {
                        "username": "foobar",
                        "forename": "Foo",
                        "surname": "Bar",
                        "fullname": "Foo Bar",
                        "email": ("foo.bar@example.org",),
                        "groups": ("bargroup", "bazgroup"),
                    }
                ],
            }
        ),
    )

    diff = target.calculate_difference(target.compile_groups_patterns([".*"]))
    target.users_sync(diff)

    group_entries = server.get_related_entries_for_module(user_id, "SecurityGroups")
    for group in group_entries:
        assert group["attributes"]["name"] in ("bargroup", "bazgroup")


def test_users_create(basic_target, suitecrm_server):
    """Create some users"""
    server = suitecrm_server([])
    diff = basic_target.calculate_difference([])
    old_users = server.search_by_type("User")
    basic_target.users_create(diff)
    new_users = server.search_by_type("User")
    assert len(new_users) > len(old_users)
    assert len(new_users[0]["_relationships"]["SecurityGroups"]) > 0


def test_users_update(basic_config, suitecrm_server):
    """Update the attributes of an existing user and check the changes have
    been made
    """
    server = suitecrm_server([])
    server.create_user(
        {
            "user_name": "basicuser",
            "first_name": "Basic",
            "last_name": "Bob",
            "full_name": "Basic Bob",
            "email1": "basic.bob@example.org",
            "status": "Active",
        }
    )
    target = TargetSuiteCRM(basic_config, None)
    diff = ModelDifference(
        source_users={
            "basicuser": User(
                "basicuser",
                forename="Basic",
                surname="Bob",
                email=("basic.bob@example.org",),
            ),
        },
        target_users={
            "basicuser": User(
                "basicuser",
                forename="Deluxe",
                surname="Bob",
                email=("basic.bob@example.org",),
            ),
        },
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
    server = suitecrm_server([])
    server.create_user(
        {
            "user_name": "basicuser",
            "first_name": "Basic",
            "last_name": "Bob",
            "full_name": "Basic Bob",
            "email1": "basic.bob@example.org",
            "status": "Active",
        }
    )
    target = TargetSuiteCRM(basic_config, None)
    user = User(
        "basicuser", forename="Basic", surname="Bob", email=("basic.bob@example.org",)
    )
    diff = ModelDifference(
        source_users={"basicuser": user},
        target_users={},
        added_users={},
        changed_users={},
        unchanged_users={},
        removed_users={"basicuser": user},
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
            if method == "DELETE":
                return server.mock_delete(endpoint, **kwargs)

            raise MethodException(f"Invalid method used '{method}'")

        mocker.patch("requests.request", side_effect=_suitecrm_request)
        return server

    return _request_server


@pytest.fixture(name="basic_target")
def fixture_basic_target(basic_config, basic_source):
    """Create a TargetSuiteCRM with default config"""
    target = TargetSuiteCRM(basic_config, basic_source)
    return target
