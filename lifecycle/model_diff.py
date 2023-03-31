"""Tools for calculating the difference between the source and the target models"""

from collections.abc import Iterable
import copy
import dataclasses
import re
from typing import Dict, List

from .models import Group, User


class ModelDifferenceError(Exception):
    """An error that originates from the ModelDifference module"""


class InvalidUserField(ModelDifferenceError):
    """A field listed in the config is not part of the User class"""

    message: str
    field: str

    def __init__(self, field):
        super().__init__(self, f"Field '{field}' not found in the 'User' class")
        self.field = field


class InvalidGroupField(ModelDifferenceError):
    """A field listed in the config is not part of the Group class"""

    message: str
    field: str

    def __init__(self, field):
        super().__init__(self, f"Field '{field}' not found in the 'Group' class")
        self.field = field


class InvalidRegex(re.error, ModelDifferenceError):
    """As `re.error`, but a subset of ModelDifferenceError"""

    message: str
    pattern: str

    def __init__(self, message, pattern):
        super().__init__(message, pattern)


@dataclasses.dataclass
class ModelDifferenceConfig:
    r"""An object holding the config used by the ModelDifference class

    This defines the fields that will be considered when comparing two Users
    to decide whether they meaningfully differ, e.g.

    * We only care if users have changed their names when syncing HR systems

    * we only care about a subset of all groups when adding users to project
      groups.

    """

    fields: List[str]
    """fields: The fields in the User that matter if they differ

    e.g. ``["username", "forename", "groups"]``
    """

    groups_patterns: List[re.Pattern]
    r"""groups_patterns: a list of regex patterns, a group must match against
    at least one of these patterns to matter if it differs.

    e.g. ``[re.compile(r'^everyone$'), re.compile(r'^\w\w\d\d\d$')]``
    """

    group_fields: List[str] = dataclasses.field(default_factory=Group.supported_fields)
    """groups_fields: The fields in the Group that matter if they differ

    e.g. ``["name", "description"]``
    """

    @staticmethod
    def from_dict(config_dict: Dict):
        r"""Parses a dict of possible config values, validates and returns a
        ModelDifferenceConfig

        The Dict expects to have an entry called "fields" that is a list of
        fields for a User, e.g::

            fields:
            - username
            - forename
            - groups

        It may also have an entry called "groups" that is a list of regular
        expression patterns, e.g.::

            groups_patterns:
            - '^everyone$'
            - '^\w\w\d\d\d$'

        It may also have an entry called "groups_fields" that is a list of
        fields for a Group, e.g.::

            group_fields:
            - name
            - description
        """

        config_fields = config_dict["fields"]
        groups_patterns = []
        for field in config_fields:
            if field not in User.supported_fields():
                raise InvalidUserField(field)

        group_fields = config_dict.get("group_fields", None)
        if group_fields:
            for field in group_fields:
                if field not in Group.supported_fields():
                    raise InvalidGroupField(field)

        try:
            if "groups" in config_fields:
                patterns = config_dict.get("groups_patterns", [".*"])
                groups_patterns = [re.compile(pattern) for pattern in patterns]
        except re.error as error:
            raise InvalidRegex(error.msg, error.pattern) from error

        if group_fields:
            return ModelDifferenceConfig(config_fields, groups_patterns, group_fields)

        return ModelDifferenceConfig(config_fields, groups_patterns)


# pylint: disable-msg=too-few-public-methods
@dataclasses.dataclass
class ModelDifference:
    """A class representing the difference between two dicts of Users"""

    source_users: Dict[str, User]
    """source_users: Dict of users as they exist in the source"""

    target_users: Dict[str, User]
    """target_users: Doct of users as they exist in the target"""

    added_users: Dict[str, User]
    """added_users: Dict of users that have been added to the source."""

    removed_users: Dict[str, User]
    """removed_users: Dict of users that have been removed from the source."""

    changed_users: Dict[str, User]
    """changed_users: Dict of users that have been changed in the source.
    These users are merged together from source and target based on the config
    provided.
    """

    unchanged_users: Dict[str, User]
    """unchanged_users: Dict of users that have not been changed in the source."""

    @staticmethod
    def _list_group_matches(user: User, config: ModelDifferenceConfig) -> tuple[Group]:
        """Generates a tuple of all groups in a User that match the configured patterns"""
        matched = tuple(
            group
            for group in user.groups
            if any(
                re.fullmatch(pattern, group.name) for pattern in config.groups_patterns
            )
        )
        return matched

    @staticmethod
    def _values_differ(source_value, target_value):
        if isinstance(source_value, Iterable):
            source_value = sorted(source_value)
            target_value = sorted(target_value)
        return source_value != target_value

    @staticmethod
    def _users_differ(
        source_user: User, target_user: User, config: ModelDifferenceConfig
    ) -> bool:
        """Checks whether two Users differ using the given config rules"""

        for field in config.fields:
            if field == "groups":
                if ModelDifference._groups_differ(
                    source_user.groups, target_user.groups, config
                ):
                    return True
            elif ModelDifference._values_differ(
                getattr(source_user, field), getattr(target_user, field)
            ):
                return True

        return False

    @staticmethod
    def _groups_differ(
        source_groups: set[Group],
        target_groups: set[Group],
        config: ModelDifferenceConfig,
    ) -> bool:
        """Checks whether two Groups differ using the given config rules"""

        # These obviously differ if one is missing
        if len(source_groups) != len(target_groups):
            return True

        target_by_name = {g.name: g for g in target_groups}

        for source_group in source_groups:
            # Also obviously differ if one is missing from the other
            if source_group.name not in target_by_name:
                return True

            target_group = target_by_name[source_group.name]
            # Also differ if any field in the list is different
            for field in config.group_fields:
                if ModelDifference._values_differ(
                    getattr(source_group, field), getattr(target_group, field)
                ):
                    return True
        return False

    @staticmethod
    def _merge_users(
        source_user: User, target_user: User, config: ModelDifferenceConfig
    ) -> User:
        """Returns a User that inherits the configured fields from the source user
        and all other fields from the target user
        """

        merged_user = copy.deepcopy(target_user)
        for field in config.fields:
            setattr(merged_user, field, getattr(source_user, field))

        return merged_user

    @staticmethod
    def calculate(
        source_users: Dict[str, User],
        target_users: Dict[str, User],
        config: ModelDifferenceConfig,
    ):
        """Calculates the differences between the source_users and target_users
        and returns that as a ModelDifference
        """

        if config.groups_patterns:
            for user in source_users.values():
                user.groups = ModelDifference._list_group_matches(user, config)

        added_users = {
            user: data
            for user, data in source_users.items()
            if user not in target_users
        }
        removed_users = {
            user: data
            for user, data in target_users.items()
            if user not in source_users
        }
        changed_users = {}
        unchanged_users = {}

        # For every user in both source and target, split them into users
        # that are the same and users that are different,
        # merging the fields from source and target into the changed users
        for user, data in source_users.items():
            if user in target_users:
                source_user = data
                target_user = target_users[user]
                if ModelDifference._users_differ(source_user, target_user, config):
                    changed_users[user] = ModelDifference._merge_users(
                        source_user, target_user, config
                    )
                else:
                    unchanged_users[user] = source_user

        return ModelDifference(
            source_users,
            target_users,
            added_users,
            removed_users,
            changed_users,
            unchanged_users,
        )
