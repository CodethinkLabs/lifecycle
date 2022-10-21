"""Target for pushing users and groups to LDAP"""

import ldap3

from lifecycle.models import User
from lifecycle.model_diff import ModelDifference
from lifecycle.source_ldap3 import SourceLDAP3


# Inherits from LDAP source because we want to reuse their user and group fetching
class TargetLDAP3(SourceLDAP3):
    """Given an LDAP Server config, will provide an interface to push users and groups to said LDAP Server"""

    def reconfigure(self, config: dict):
        """Apply new configuration to object.

        The newly supplied config entry will be merged over the existing config.
        """
        super().reconfigure(self, config)

        extra_default_config = {
            "target_operations": [
                "add_users",
                "remove_users",
                "modify_users",
            ],
            "new_user_cn_field": "fullname", # username also a good candidate
            "new_user_group_path": "cn=users,cn=accounts"
        }
        self.config = extra_default_config | self.config

    @staticmethod
    def _user_to_ldap_changes(user: User) -> dict:
        # 'uid' is also a field that could go into ldap changes, but we don't expect that to ever change

        # XXX: HOW DO I SET WHICH USERS ARE MEMBERS OF GROUPS?
        lock_status = "TRUE" if user.locked else "FALSE"
        return {
            "givenName": [(ldap3.MODIFY_REPLACE, [user.forename])],
            "surName": [(ldap3.MODIFY_REPLACE, [user.surname])],
            "nsAccountLock": [(ldap3.MODIFY_REPLACE, [lock_status])],
            "mail": [(ldap3.MODIFY_REPLACE, sorted(user.email))],
        }


    def _find_user_by_uid(self, connection: ldap3.Connection, uid: str) -> str:
        """Searches for a user by its unique uid and returns its dn"""

        # "uid", the key to the users dict, is the only part that's guaranteed to be unique
            connection.search(
                search_base=self.config["base_dn"],
                search_filter=f"(uid={uid})",
                search_scope=ldap3.SUBTREE,
                attributes=[
                    "uid",
                ],
            )
            assert len(connection.entries) == 1, f"UID {uid} is not unique! Lifecycle can't handle this!"
            return connection.entries[0].entry_dn

    def add_users(self, users: dict[str, User]):
        """Adds the listed users to the starget"""
        # XXX: Not 100% sure what a new user's cn should be. configurable??

    def remove_users(self, users: dict[str, User]):
        """Removes the listed users from the target"""

        connection = self.connect()
        for uid, user in users.items():
            user_dn = self._find_user_by_uid(self, connection, uid)
            connection.delete(user_dn)

    def modify_users(self, users: dict[str, User]):
        """Modifies all listed users in the target"""

        connection = self.connect()
        for uid, user in users.items():
            user_dn = self._find_user_by_uid(self, connection, uid)
            changes = _user_to_ldap_changes(user)
            connection.modify(user_dn, changes)

    def sync_users_changes(self, changes: ModelDifference):
        """Synchronises the difference in the users model with the server"""
        operations = self.config["target_operations"]
        if "add_users" in operations:
            self.add_users(changes.added_users)
        if "remove_users" in operations:
            self.remove_users(changes.removed_users)
        if "modify_users" in operations:
            self.modify_users(changes.changed_users)

