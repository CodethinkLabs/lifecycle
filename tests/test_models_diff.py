""" Tests for the model diffing engine"""

import pytest

from lifecycle.model_diff import (
    InvalidGroupField,
    InvalidRegex,
    InvalidUserField,
    ModelDifference,
    ModelDifferenceConfig,
)
from lifecycle.models import Group, User


# what to test:
# bad config


def test_basic_diff():
    """Test a simple model diff"""
    source_data = {
        "test1": User("test1"),
        "test2": User("test2"),
    }
    target_data = {
        "test2": User("test2"),
        "test3": User("test3"),
    }
    config = {
        "fields": ["username"],
    }

    diff = ModelDifference.calculate(
        source_data, target_data, ModelDifferenceConfig.from_dict(config)
    )
    assert "test1" in diff.added_users
    assert "test3" in diff.removed_users
    assert "test2" in diff.unchanged_users


def test_diff_changed_user():
    """Test diffs where a User has changed"""
    source_data = {
        "test1": User("test1"),
        "test2": User("test2", groups=[Group("group1")]),
    }
    target_data = {
        "test2": User("test2", groups=[Group("group2")]),
        "test3": User("test3"),
    }
    config = {
        "fields": [
            "username",
            "groups",
        ],
    }

    diff = ModelDifference.calculate(
        source_data, target_data, ModelDifferenceConfig.from_dict(config)
    )
    assert "test2" in diff.changed_users


def test_diff_only_specified_fields():
    """Test diffs where a User has changed, but not in a way the config cares about"""
    source_data = {
        "test1": User("test1"),
        "test2": User("test2", groups=[Group("group1")]),
    }
    target_data = {
        "test2": User("test2", groups=[Group("group2")]),
        "test3": User("test3"),
    }
    config = {
        "fields": [
            "username",
        ],
    }

    diff = ModelDifference.calculate(
        source_data, target_data, ModelDifferenceConfig.from_dict(config)
    )
    assert "test2" in diff.unchanged_users


def test_config_field_no_exist():
    """Test that it catches config using fields that don't exist"""
    source_data = {
        "test1": User("test1"),
        "test2": User("test2"),
    }
    target_data = {
        "test2": User("test2"),
        "test3": User("test3"),
    }
    config = {
        "fields": ["foobarbaz"],
    }

    with pytest.raises(InvalidUserField):
        ModelDifference.calculate(
            source_data, target_data, ModelDifferenceConfig.from_dict(config)
        )


def test_config_group_field_no_exist():
    """Test that it catches config using group fields that don't exist"""

    source_data = {
        "test1": User("test1"),
    }
    target_data = {
        "test2": User("test2"),
    }
    config = {
        "fields": ["username"],
        "group_fields": ["foobarbaz"],
    }

    with pytest.raises(InvalidGroupField):
        ModelDifference.calculate(
            source_data, target_data, ModelDifferenceConfig.from_dict(config)
        )


def test_config_bad_regex():
    """Test that it catches config with malformed regular expressions"""
    source_data = {
        "test1": User("test1"),
        "test2": User("test2"),
    }
    target_data = {
        "test2": User("test2"),
        "test3": User("test3"),
    }
    config = {
        "fields": [
            "username",
            "groups",
        ],
        "groups_patterns": [
            r"",
            r"**",
            r"\\",
        ],
    }

    with pytest.raises(InvalidRegex):
        ModelDifference.calculate(
            source_data, target_data, ModelDifferenceConfig.from_dict(config)
        )


def test_diff_unmatched_group_removed():
    """Tests that when a group exists on the target but doesn't match
    any patterns, the diff removes it
    """
    source_data = {
        "test1": User("test1", groups=(Group("division1"), Group("project1"))),
    }
    target_data = {
        "test1": User("test1", groups=(Group("division1"), Group("project1"))),
    }
    config = {
        "fields": [
            "username",
            "groups",
        ],
        "groups_patterns": [r"^project\d+$"],
    }

    diff = ModelDifference.calculate(
        source_data, target_data, ModelDifferenceConfig.from_dict(config)
    )
    assert (
        "test1" in diff.changed_users
    ), "Removing a group pattern failed to cause lifecycle to update a user"
    assert diff.changed_users["test1"].groups == (Group("project1"),)


def test_groups_ignore_ordering():
    """Tests that having groups in a different order doesn't count as a changed user"""
    source_data = {
        "test1": User("test1", groups=(Group("FooGroup"), Group("BarGroup"))),
    }
    target_data = {
        "test1": User("test1", groups=(Group("BarGroup"), Group("FooGroup"))),
    }
    config = {
        "fields": [
            "username",
            "groups",
        ]
    }
    diff = ModelDifference.calculate(
        source_data, target_data, ModelDifferenceConfig.from_dict(config)
    )
    assert "test1" in diff.unchanged_users


def test_email_ignore_ordering():
    """Tests that having emails in a different order doesn't count as a changed user"""
    source_data = {
        "test1": User("test1", email=("foo.bar@example.org", "foo.bar@example.com")),
    }
    target_data = {
        "test1": User("test1", email=("foo.bar@example.com", "foo.bar@example.org")),
    }
    config = {
        "fields": [
            "username",
            "email",
        ]
    }
    diff = ModelDifference.calculate(
        source_data, target_data, ModelDifferenceConfig.from_dict(config)
    )
    assert "test1" in diff.unchanged_users


def test_group_email_ignore_ordering():
    """Tests that having E-mail addresses inside a group in a different order
    doesn't count as a changed user
    """
    source_data = {
        "test1": User(
            "test1",
            groups=(
                Group("FooGroup", email=("foo.bar@example.org", "foo.bar@example.com")),
            ),
        ),
    }
    target_data = {
        "test1": User(
            "test1",
            groups=(
                Group("FooGroup", email=("foo.bar@example.com", "foo.bar@example.org")),
            ),
        ),
    }
    config = {
        "fields": [
            "username",
            "email",
        ]
    }
    diff = ModelDifference.calculate(
        source_data, target_data, ModelDifferenceConfig.from_dict(config)
    )
    assert "test1" in diff.unchanged_users
