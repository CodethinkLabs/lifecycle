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
