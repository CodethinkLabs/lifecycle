"""Tools for calculating the difference between the source and the target models"""

import copy
import dataclasses
import re
from typing import Dict, List

from .models import Group, User


class ModelDifferenceError(Exception):
    """An error that originates from the ModelDifference module"""


class InvalidField(ModelDifferenceError):
    """A field listed in the config is not part of the User class"""

    message: str
    field: str

    def __init__(self, field):
        super().__init__(self, f"Field '{field}' not found in the 'User' class")
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

    @staticmethod
    def from_dict(config_dict: Dict):
        r"""Parses a dict of possible config values, validates and returns a
        ModelDifferenceConfig

        The Dict expects to have an entry called "fields" that is a list of
        fields, e.g::

            fields:
            - username
            - forename
            - groups

        It may also have an entry called "groups" that is a list of regular
        expression patterns, e.g.::

            groups_patterns:
            - '^everyone$'
            - '^\w\w\d\d\d$'
        """

        config_fields = config_dict["fields"]
        groups_patterns = []
        user_fields = [f.name for f in dataclasses.fields(User)]
        for field in config_fields:
            if field not in user_fields:
                raise InvalidField(field)

        try:
            if "groups" in config_fields and "groups_patterns" in config_dict:
                for pattern in config_dict["groups_patterns"]:
                    groups_patterns.append(re.compile(pattern))
        except re.error as error:
            raise InvalidRegex(error.msg, error.pattern) from error

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
    def _list_groups(
        user: User, config: ModelDifferenceConfig
    ) -> tuple[set[Group], set[Group]]:
        """Generates a tuple of all groups in a User that match the configured patterns,
        and all groups that don't match
        """
        matched = set(
            group
            for group in user.groups
            if any(
                re.fullmatch(pattern, group.name) for pattern in config.groups_patterns
            )
        )

        unmatched = set(user.groups) - matched
        return matched, unmatched

    @staticmethod
    def _list_group_matches(user: User, config: ModelDifferenceConfig) -> set[Group]:
        matched, _ = ModelDifference._list_groups(user, config)
        return matched

    @staticmethod
    def _users_differ(
        source_user: User, target_user: User, config: ModelDifferenceConfig
    ) -> bool:
        """Checks whether two Users differ using the given config rules"""

        for field in config.fields:
            if field == "groups" and config.groups_patterns:
                # If the list of matches to the source_user *doesn't* equal the
                # list of matches to the target_user, it differs.
                source_matches = ModelDifference._list_group_matches(
                    source_user, config
                )
                target_matches = ModelDifference._list_group_matches(
                    target_user, config
                )
                if source_matches != target_matches:
                    return True
            elif getattr(source_user, field) != getattr(target_user, field):
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
            if field == "groups" and config.groups_patterns:
                # Include all matched patterns from the source
                # and all unmatched patterns from the target
                source_groups, _ = ModelDifference._list_groups(source_user, config)
                _, target_groups = ModelDifference._list_groups(target_user, config)
                merged_user.groups = sorted(source_groups | target_groups)
            else:
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
