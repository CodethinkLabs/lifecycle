"""Source that pulls user models from a static config file"""

import dataclasses
import logging
from typing import Dict

from . import SourceBase
from .models import Group, User


class SourceStaticConfig(SourceBase):
    """Generates a user model out of the config passed to it

    An example source config would be::

        source:
          module: StaticConfig
          groups:
            - name: foobar
          users:
            - username: johnsmith
              fullname: "John Smith"
              groups: ["foobar"]
              email: ["john.smith@example.org", "john.smith@example.test"]
            - username: jimsmyth
              fullname: "Jim Smyth"
              email: ["jim.smyth@example.org"]

    """

    mandatory_fields = {"users", "groups"}

    @staticmethod
    def _mandatory_fields(data_class) -> set[str]:
        """A field in a dataclass is mandatory if it has no default"""
        return {
            field.name
            for field in dataclasses.fields(data_class)
            if field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING
        }

    @staticmethod
    def _optional_fields(data_class) -> set[str]:
        """A field in a dataclass is optional if it has a default"""
        return {
            field.name
            for field in dataclasses.fields(data_class)
            if field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        }

    def configure(self, config):
        # Calls _check_fields on the dict twice, but we need to check the fields exist
        # before we inspect their contents
        self._check_fields(config, self.mandatory_fields, self.optional_fields)

        for user in config["users"]:
            self._check_fields(
                user, self._mandatory_fields(User), self._optional_fields(User)
            )

        for group in config["groups"]:
            self._check_fields(
                group, self._mandatory_fields(Group), self._optional_fields(Group)
            )

        return super().configure(config)

    def fetch(self):
        """Load all config and generate a User model"""
        self.fetch_users()
        self.fetch_groups()
        logging.debug("Loaded users '%s'", self.users)

    def fetch_users(self, refresh: bool = False) -> Dict[str, User]:
        """Load users from config and map to the User model"""
        if not refresh and self.users:
            return self.users

        self.users = {}
        for config_user in self.config["users"]:
            username = config_user["username"]

            fields = {
                field: config_user[field]
                for field in self._optional_fields(User)
                if field in config_user and field != "groups"
            }
            self.users[username] = User(username, **fields)
        return self.users

    def fetch_groups(self):
        """Load groups from config and insert them into their relevant Users"""
        for config_group in self.config["groups"]:
            name = config_group["name"]
            fields = {
                field: config_group[field]
                for field in self._optional_fields(Group)
                if field in config_group
            }
            group = Group(name, **fields)

            # Insert this group into all users that list this group
            for config_user in self.config["users"]:
                username = config_user["username"]
                if name in config_user["groups"]:
                    self.users[username].groups += (group,)
