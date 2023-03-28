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


def test_groups_differ_by_pattern():
    """Tests that differences in the 'groups' field obey groups_patterns"""
    source_data = {
        "test1": User("test1", groups=[Group("division1"), Group("project1")]),
        "test2": User("test2", groups=[Group("division1"), Group("project1")]),
    }
    target_data = {
        "test1": User("test1", groups=[Group("division2"), Group("project1")]),
        "test2": User("test2", groups=[Group("division1"), Group("project2")]),
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
    assert "test1" in diff.unchanged_users
    assert "test2" in diff.changed_users
