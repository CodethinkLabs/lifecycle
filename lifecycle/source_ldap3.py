"""Source for pulling users and groups from LDAP """

import logging
from typing import Dict

import ldap3

from . import LifecycleException, SourceBase
from .models import Group, User


class AuthenticationException(LifecycleException):
    """Raised when the binding fails"""


class SourceLDAP3(SourceBase):
    """Given an ldap server config, will collect user and groups from said LDAP server"""

    def configure(self, config: Dict):
        """Apply new configuration to object.

        The newly supplied config entry will be merged over the existing config.
        """
        errors = []

        if not isinstance(config, dict):
            errors.append("You must provide a configuration dict to use this function")
        if "url" not in config:
            errors.append("'url' must be specified")
        if "base_dn" not in config:
            errors.append("Base DN must be specified")
        if not ("bind_dn" in config and "bind_password" in config) and not config.get(
            "anonymous_bind", False
        ):
            errors.append(
                "Please either specify a user DN & password, or set anonymous_bind to true"
            )
        if errors:
            raise LifecycleException("\n".join(errors))

        default_config = {
            "anonymous_bind": False,
            "use_ssl": True,
        }
        return default_config | config

    def connect(self):
        """Connect to LDAP server using current configuration and return the connection"""
        server = ldap3.Server(self.config["url"])
        connection = ldap3.Connection(
            server, user=self.config["bind_dn"], password=self.config["bind_password"]
        )

        # We want to ensure that if incorrect credentials are passed in
        # that we get some feedback about it
        # Ensuring that a password is passed in is already handled elsewhere
        if not connection.bind():
            raise AuthenticationException("Username or Password not valid")
        return connection

    def fetch(self):
        """Fetch users / groups from LDAP into lifecycle user and group objects"""
        self.fetch_users()
        self.fetch_groups()

    def fetch_users(self, refresh: bool = False) -> Dict[str, User]:
        """Load the LDAP users"""
        if not refresh and self.users:
            return self.users

        users = {}
        connection = self.connect()

        connection.search(
            search_base=self.config["base_dn"],
            search_filter="(objectclass=organizationalPerson)",
            search_scope=ldap3.SUBTREE,
            attributes=[
                "description",
                "uid",
                "mail",
                "surName",
                "givenName",
                "nsAccountLock",
            ],
        )

        if connection.entries:
            for ldap_entry in connection.entries:
                user_account = ldap_entry.entry_attributes_as_dict

                if len(user_account["uid"]) > 0 and len(user_account["mail"]) > 0:
                    uid = user_account["uid"][0]
                    ns_account_lock = user_account["nsAccountLock"]
                    locked = len(ns_account_lock) > 0 and ns_account_lock[0] == "TRUE"
                    user = User(
                        uid,
                        forename=user_account["givenName"][0],
                        surname=user_account["surName"][0],
                        email=user_account["mail"],
                        groups=[],
                        locked=locked,
                    )
                    users[uid] = user
            self.users = users
            logging.debug(users)
            return users

        logging.debug("No user accounts found")
        return {}

    def fetch_groups(self):
        """Load the LDAP groups"""
        connection = self.connect()

        connection.search(
            search_base=self.config["base_dn"],
            search_filter="(objectClass=groupOfNames)",
            search_scope=ldap3.SUBTREE,
            attributes=["description", "mail", "member", "cn"],
        )

        if connection.entries:
            for ldap_entry in connection.entries:
                ldap_group = ldap_entry.entry_attributes_as_dict

                if len(ldap_group["cn"]) > 0:
                    name = ldap_group["cn"][0]
                    if len(ldap_group["description"]) > 0:
                        description = ldap_group["description"][0]
                    else:
                        description = ""
                    group = Group(name, description, ldap_group["mail"])

                    for member in ldap_group["member"]:
                        components = member.split(",")
                        uid = components[0].split("=")[1]
                        if uid in self.users:
                            self.users[uid].groups.append(group)
        else:
            logging.debug("No groups found")
