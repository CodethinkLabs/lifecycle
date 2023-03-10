"""Basic functionality for the Static Config Source"""

from lifecycle.models import Group, User
from lifecycle.source_staticconfig import SourceStaticConfig


# What cases do I care about?
# Good config in, good user model out


def test_config_basic():
    """Test loading config doesn't totally fail"""

    source = SourceStaticConfig(
        config={
            "groups": [{"name": "foobar"}],
            "users": [
                {
                    "username": "johnsmith",
                    "groups": ["foobar"],
                }
            ],
        }
    )
    assert source.config["groups"][0]["name"] == "foobar"
    assert source.config["users"][0]["username"] == "johnsmith"
    assert source.config["users"][0]["groups"][0] == "foobar"


def test_fetch_basic():
    """Test that it fetches the right user model from a given config"""
    source = SourceStaticConfig(
        config={
            "groups": [{"name": "foobar"}],
            "users": [
                {
                    "username": "johnsmith",
                    "groups": ["foobar"],
                }
            ],
        }
    )
    source.fetch()
    expected_model = {
        "johnsmith": User("johnsmith", groups=(Group("foobar"),)),
    }
    assert source.users == expected_model


def test_fetch_multiple_users():
    "Test that it works correctly with multiple users"
    source = SourceStaticConfig(
        config={
            "groups": [{"name": "foobar"}],
            "users": [
                {
                    "username": "johnsmith",
                    "groups": ["foobar"],
                },
                {
                    "username": "alicesmith",
                    "groups": ["foobar"],
                },
                {
                    "username": "freddy",
                    "groups": ["foobar"],
                },
            ],
        }
    )
    source.fetch()
    expected_model = {
        "johnsmith": User("johnsmith", groups=(Group("foobar"),)),
        "alicesmith": User("alicesmith", groups=(Group("foobar"),)),
        "freddy": User("freddy", groups=(Group("foobar"),)),
    }
    assert source.users == expected_model


def test_fetch_multiple_groups():
    """Test that the source works correctly with a non 1 number of groups"""
    source = SourceStaticConfig(
        config={
            "groups": [{"name": "foobar"}, {"name": "bazqux"}, {"name": "blank"}],
            "users": [
                {
                    "username": "johnsmith",
                    "groups": [],
                },
                {
                    "username": "alicesmith",
                    "groups": ["foobar", "bazqux", "blank"],
                },
            ],
        }
    )
    source.fetch()
    expected_model = {
        "johnsmith": User("johnsmith", groups=()),
        "alicesmith": User(
            "alicesmith",
            groups=(
                Group("foobar"),
                Group("bazqux"),
                Group("blank"),
            ),
        ),
    }
    assert source.users == expected_model


def test_fetch_all_user_fields():
    """Make sure that we handle all user fields correctly"""
    source = SourceStaticConfig(
        config={
            "groups": [{"name": "foobar"}],
            "users": [
                {
                    "username": "johnsmith",
                    "forename": "john",
                    "surname": "smith",
                    "email": ["john@smith.com"],
                    "groups": ["foobar"],
                },
            ],
        }
    )
    source.fetch()
    expected_model = {
        "johnsmith": User(
            "johnsmith",
            forename="john",
            surname="smith",
            fullname="john smith",
            email=["john@smith.com"],
            locked=False,
            groups=(Group("foobar"),),
        ),
    }
    assert source.users == expected_model


def test_fetch_all_group_fields():
    """Make sure that we handle all group fields correctly"""
    source = SourceStaticConfig(
        config={
            "groups": [
                {"name": "foobar", "description": "test group", "email": "foo@bar.com"}
            ],
            "users": [
                {
                    "username": "johnsmith",
                    "groups": ["foobar"],
                }
            ],
        }
    )
    source.fetch()
    expected_groups = (
        Group(name="foobar", description="test group", email="foo@bar.com"),
    )
    assert source.users["johnsmith"].groups == expected_groups
