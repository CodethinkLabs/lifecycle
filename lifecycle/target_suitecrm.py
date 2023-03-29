"""Target for synchronising users and groups to SuiteCRM"""

from datetime import datetime
import logging
from typing import Dict
from urllib.parse import urljoin

import jwt
import requests

from . import TargetBase
from .model_diff import ModelDifference
from .models import Group, User


class TargetSuiteCRM(TargetBase):
    """Interface for synchronising users and groups to SuiteCRM target"""

    def __init__(self, *args):
        super().__init__(*args)

        self._token = None
        self._token_expiry = 0
        self._users_data = {}
        self._emails_to_id = {}
        self._groups_to_id = {}
        self._groups_to_attributes = {}

    mandatory_fields = {
        "url",
        "api_client_id",
        "api_client_secret",
        "api_username",
        "api_password",
    }

    optional_fields = {
        "api_page_size",
        "stages",
        "users_cleanup",
        "excluded_usernames",
    }

    supported_user_fields = {
        "username",
        "forename",
        "surname",
        "email",
        "locked",
        "groups",
    }

    supported_group_fields = {
        "name",
        "description",
    }

    default_config = {
        "api_page_size": 20,
        "stages": ["users_create", "users_sync", "users_disable", "users_cleanup"],
        "excluded_usernames": [],
    }

    def _authenticate(self):
        """Authenticate with SuiteCRM and acquire an access token"""
        response = self._request(
            "/Api/access_token",
            method="POST",
            auth=False,
            data={
                "grant_type": "password",
                "client_id": self.config["api_client_id"],
                "client_secret": self.config["api_client_secret"],
                "username": self.config["api_username"],
                "password": self.config["api_password"],
            },
        )
        logging.debug("Authentication response '%s'", response.text)

        self._token = response.json()["access_token"]
        self._token_expiry = jwt.decode(
            self._token, options={"verify_signature": False}
        )["exp"]
        return self._token

    def _token_invalid(self):
        """Check token expiration is not imminent"""
        # Invalidate a minute prior to expiration.
        return (
            self._token is None or self._token_expiry + 60 < datetime.now().timestamp()
        )

    def _get_token(self):
        """Return a valid access token for the SuiteCRM API"""
        if self._token_invalid():
            return self._authenticate()
        return self._token

    def _request(self, endpoint: str, method: str = "GET", auth: bool = True, **kwargs):
        """Wrapper around request for interacting with the SuiteCRM API"""
        url = urljoin(self.config["url"], endpoint)
        headers = kwargs.pop("headers", {})
        if auth:
            headers.update(
                {
                    "Content-type": "application/vnd.api+json",
                    "Accept": "application/vnd.api+json",
                    "Authorization": f"Bearer {self._get_token()}",
                }
            )
        logging.debug("HTTP Request JSON (if any):  %s", kwargs.get("json", ""))
        logging.debug("SuiteCRM url is: '%s'", url)
        response = requests.request(
            method, url, headers=headers, timeout=30, **kwargs, allow_redirects=False
        )
        response.raise_for_status()
        return response

    def _iter_pages(self, endpoint: str, page: int = 1):
        """Generator for handling paginated responses from the SuiteCRM API"""
        logging.debug("Iterating through entries")
        params = {
            "page[size]": self.config["api_page_size"],
            "page[number]": page,
        }
        _json = self._request(endpoint, params=params).json()
        yield from _json["data"]

        if "total-pages" in _json["meta"]:
            # if you request something that's empty, you get nothing
            # but it's hard to guess ahead-of-time whether it'll be empty
            total_pages = _json["meta"]["total-pages"]
            while page < total_pages:
                page += 1
                yield from self._iter_pages(endpoint, page)
        logging.debug("Done iterating")

    def _user_relationship_endpoint(self, username: str, relationship_type: str) -> str:
        """Returns the API endpoint for the relationship of a given type to a given user"""

        assert username in self._users_data
        data = self._users_data[username]
        if relationship_type in data["relationships"]:
            return (
                "/Api/" + data["relationships"][relationship_type]["links"]["related"]
            )

        return ""

    def _fetch_raw_relations_for_user(
        self, username: str, relationship_type: str
    ) -> dict:
        """Returns the raw entries of a given type related to a given user"""

        endpoint = self._user_relationship_endpoint(username, relationship_type)
        if endpoint:
            return list(self._iter_pages(endpoint))

        return {}

    def _fetch_raw_emails_for_user(self, username: str) -> dict:
        """Takes a username and fetches any extra E-mail addresses, returning the raw dict"""

        return self._fetch_raw_relations_for_user(username, "EmailAddress")

    def _fetch_emails_for_user(self, username: str) -> tuple[str]:
        """Takes a username and fetches any extra E-mail addresses,
        returning only the E-mail addresses.
        """

        emails = tuple(
            ent["attributes"]["email_address"]
            for ent in self._fetch_raw_emails_for_user(username)
        )
        logging.debug("E-mails fetched for user '%s': '%s'", username, emails)

        return emails

    def _fetch_emails_with_id_for_user(self, username: str) -> dict[str, str]:
        """Takes a username and fetches any extra E-mail addresses,
        returning a dict of email address to ID
        """
        return {
            ent["attributes"]["email_address"]: ent["id"]
            for ent in self._fetch_raw_emails_for_user(username)
        }

    def _fetch_groups_for_user(self, username: str) -> tuple[Group]:
        """Generates a tuple of all the Groups associated with a user,
        generated from the SecurityGroups in SuiteCRM
        """

        groups = tuple(
            Group(
                ent["attributes"]["name"],
                description=ent["attributes"].get("description", None),
            )
            for ent in self._fetch_raw_relations_for_user(username, "SecurityGroups")
        )
        return groups

    def _fetch_groups_with_id_for_user(self, username: str) -> dict[str, str]:
        return {
            ent["attributes"]["name"]: ent["id"]
            for ent in self._fetch_raw_relations_for_user(username, "SecurityGroups")
        }

    def fetch_users(self, refresh: bool = False) -> Dict[str, User]:
        """Load the SuiteCRM users"""
        if not refresh and self.users:
            return self.users

        users = {}
        self._users_data = {}

        _json = list(self._iter_pages("/Api/V8/module/Users"))

        for obj in _json:
            attributes = obj["attributes"]
            username = attributes["user_name"]
            self._users_data[username] = obj
            emails = self._fetch_emails_for_user(username)
            groups = self._fetch_groups_for_user(username)
            user = User(
                username=username,
                forename=attributes["first_name"],
                surname=attributes["last_name"],
                fullname=attributes["full_name"],
                groups=groups,
                email=emails,
                locked=attributes["status"].lower() != "active",
            )
            users[username] = user

        logging.debug("Users fetched from server: '%s'", users)
        self.users = users
        return users

    def _fetch_all_emails(self, refresh=False):
        if not refresh and self._emails_to_id:
            return self._emails_to_id

        emails_json = list(self._iter_pages("/Api/V8/module/EmailAddress"))
        self._emails_to_id = {}
        for ent in emails_json:
            address = ent["attributes"]["email_address"]
            _id = ent["id"]
            if address in self._emails_to_id:
                logging.warning(
                    (
                        "Duplicate E-mail address entries found in suitecrm server:"
                        "Address '%s' has IDs '%s' and '%s'. Using the first one only."
                    ),
                    address,
                    self._emails_to_id[address],
                    _id,
                )
            else:
                self._emails_to_id[address] = _id
        return self._emails_to_id

    def _fetch_all_groups(self, refresh=False):
        if not refresh and self._groups_to_id:
            return self._groups_to_id

        groups_json = list(self._iter_pages("/Api/V8/module/SecurityGroup"))

        self._groups_to_id = {}
        self._groups_to_attributes = {}
        for ent in groups_json:
            groupname = ent["attributes"]["name"]
            _id = ent["id"]
            if groupname in self._groups_to_id:
                logging.warning(
                    (
                        "Duplicate Group entries found in suitecrm server:"
                        "Group '%s' has IDs '%s' and '%s'. Using the first one only."
                    ),
                    groupname,
                    self._groups_to_id[groupname],
                    _id,
                )
            else:
                self._groups_to_id[groupname] = _id
                self._groups_to_attributes[groupname] = ent["attributes"]
        return self._groups_to_id

    def _create_group(self, group: Group):
        logging.debug("Creating new Security Group for group named '%s'", group.name)
        new_group = {
            "data": {
                "type": "SecurityGroup",
                "attributes": {
                    "name": group.name,
                    "description": group.description,
                },
            }
        }
        self._request("/Api/V8/module", method="POST", json=new_group)

    def _update_group(self, group: Group):
        logging.debug("Updating Security Group named '%s'", group.name)
        crm_groups = self._fetch_all_groups()
        group_id = crm_groups[group.name]
        # How do I get the group ID?
        updated_group = {
            "data": {
                "type": "SecurityGroup",
                "id": group_id,
                "attributes": {
                    # name can't be changed because that's our primary key
                    "description": group.description
                    # SecurityGroups don't have an E-mail field
                },
            }
        }
        self._request("/Api/V8/module", method="PATCH", json=updated_group)

    @staticmethod
    def _group_differs(lifecycle_group: Group, crm_group_attributes: dict) -> bool:
        assert lifecycle_group.name == crm_group_attributes["name"]
        if lifecycle_group.description != crm_group_attributes["description"]:
            return True
        return False

    def _sync_groups(self, users: list[User]):
        """Sync (add missing and update changed) groups for a list of Users"""

        # Fortunately, since we fetched and diffed, we already know which groups are missing

        names_to_ids = self._fetch_all_groups()
        all_groups = set()
        for user in users:
            if user.groups:
                all_groups |= set(user.groups)

        for group in all_groups:
            if group.name in names_to_ids:
                if self._group_differs(group, self._groups_to_attributes[group.name]):
                    self._update_group(group)
            else:
                self._create_group(group)

        self._fetch_all_groups(refresh=True)

    def _add_missing_emails(self, users: list[User]):
        emails_to_id = self._fetch_all_emails()

        emails = set()
        for user in users:
            emails |= set(user.email)

        missing_emails = set(emails) - set(emails_to_id.keys())

        for mail in missing_emails:
            logging.debug("Creating new E-mail entry for address '%s'", mail)
            new_mail = {
                "data": {
                    "type": "EmailAddress",
                    "attributes": {
                        "email_address": mail,
                    },
                }
            }
            self._request("/Api/V8/module", method="POST", json=new_mail)

        self._fetch_all_emails(refresh=True)

    def _assign_group(self, username, group: Group):
        logging.debug("Assigning Group '%s' to user '%s'", group.name, username)
        user_id = self._users_data[username]["id"]
        new_relationship = {
            "data": {
                "type": "SecurityGroup",
                "id": self._groups_to_id[group.name],
            }
        }
        self._request(
            f"/Api/V8/module/Users/{user_id}/relationships",
            method="POST",
            json=new_relationship,
        )

    def _unassign_group(self, group_id, username):
        logging.debug("Unassigning Group '%s' from user '%s'", group_id, username)
        user_id = self._users_data[username]["id"]
        self._request(
            f"/Api/V8/module/Users/{user_id}/relationships/SecurityGroups/{group_id}",
            method="DELETE",
        )

    def _assign_email(self, mail, username):
        logging.debug("Assigning E-mail '%s' to user '%s'", mail, username)
        # Create relationship, this user to that E-mail address.
        user_id = self._users_data[username]["id"]
        new_relationship = {
            "data": {
                "type": "EmailAddress",
                "id": self._emails_to_id[mail],
            }
        }
        self._request(
            f"/Api/V8/module/Users/{user_id}/relationships",
            method="POST",
            json=new_relationship,
        )

    def _unassign_email(self, mail_id, username):
        logging.debug("Unassigning E-mail '%s' from user '%s'", mail_id, username)
        user_id = self._users_data[username]["id"]
        self._request(
            f"/Api/V8/module/Users/{user_id}/relationships/email_addresses/{mail_id}",
            method="DELETE",
        )

    def users_create(self, diff: ModelDifference):
        """Create any users missing from the target"""

        for user in diff.added_users.values():
            new_user = {
                "data": {
                    "type": "User",
                    "attributes": {
                        "user_name": user.username,
                        "first_name": user.forename,
                        "last_name": user.surname,
                        "external_auth_only": 1,
                        "email1": user.email[0] if user.email else "",
                        "status": "Inactive" if user.locked else "Active",
                    },
                }
            }
            logging.debug("Creating user: '%s'", user)
            self._request("/Api/V8/module", method="POST", json=new_user)
            logging.debug("User created successfully")

        # Refresh users so we have the new users' IDs.
        self.fetch_users(refresh=True)

        self._sync_groups(diff.added_users.values())

        self._add_missing_emails(diff.added_users.values())
        for user in diff.added_users.values():
            # Link E-mail addresses to our new users
            for mail in user.email[1:]:
                self._assign_email(mail, user.username)

            # Link SecurityGroups to our new users
            for group in user.groups:
                self._assign_group(user.username, group)

    def users_cleanup(self, diff: ModelDifference):
        """Remove any users missing from the source

        Note: When it deletes a User it doesn't delete the E-mail addresses
        associated with that user, as there's no guarantee that E-mail address
        isn't also used elsewhere.
        """

        self.fetch_users()
        logging.debug("Started cleaning users")
        logging.debug("Excluded usernames: %s", self.config["excluded_usernames"])
        for user in diff.removed_users.values():
            _id = self._users_data[user.username]["id"]
            logging.debug(
                "Attempting to delete: %s. Is user excluded: %s",
                user.username,
                user.username in self.config["excluded_usernames"],
            )
            if user.username not in self.config["excluded_usernames"]:
                deletion_record = {
                    "data": {
                        "type": "User",
                        "id": _id,
                        "attributes": {
                            "deleted": 1,
                        },
                    }
                }
                logging.debug("Deleting user: %s", user.username)
                self._request("/Api/V8/module", method="PATCH", json=deletion_record)

    def _sync_emails_for_users(self, diff: ModelDifference):
        for user in diff.changed_users.values():
            if user.username in self.config["excluded_usernames"]:
                continue

            source_emails = set(diff.source_users[user.username].email)
            target_emails = set(diff.target_users[user.username].email)
            if source_emails == target_emails:
                # Nothing to do
                continue

            added_emails = source_emails - target_emails
            for mail in added_emails:
                self._assign_email(mail, user.username)

            removed_emails = target_emails - source_emails
            # It's possible to have multiple entries in the EmailAddress module
            # that have the same E-mail address but different ID. Use the list
            # of E-mails for this user to get the right ID.
            mails_to_ids = self._fetch_emails_with_id_for_user(user.username)
            for mail in removed_emails:
                self._unassign_email(mails_to_ids[mail], user.username)

    def _sync_group_membership_for_users(self, diff: ModelDifference):
        for user in diff.changed_users.values():
            if user.username in self.config["excluded_usernames"]:
                continue

            changed_groups = set(diff.changed_users[user.username].groups)
            target_groups = set(diff.target_users[user.username].groups)
            # target_groups is already merged based on groups_patterns
            if changed_groups == target_groups:
                # Nothing about group membership changed in this User
                continue

            # Remove all then re-add to enforce ordering
            groups_to_ids = self._fetch_groups_with_id_for_user(user.username)
            for group in target_groups:
                self._unassign_group(groups_to_ids[group.name], user.username)

            for group in changed_groups:
                self._assign_group(user.username, group)

    def users_sync(self, diff: ModelDifference):
        """Sync the existing users with their values from the source"""

        self.fetch_users()
        for user in diff.changed_users.values():
            _id = self._users_data[user.username]["id"]
            if user.username not in self.config["excluded_usernames"]:
                updated_record = {
                    "data": {
                        "type": "User",
                        "id": _id,
                        "attributes": {
                            "user_name": user.username,
                            "first_name": user.forename,
                            "last_name": user.surname,
                            "email1": user.email[0] if user.email else "",
                            "status": "Inactive" if user.locked else "Active",
                        },
                    }
                }
                logging.info("Updating user '%s'", user.username)
                self._request("/Api/V8/module", method="PATCH", json=updated_record)

        # Add to suitecrm all E-mail addresses that have been added but don't exist
        self._add_missing_emails(diff.changed_users.values())

        self._sync_emails_for_users(diff)

        self._sync_groups(diff.changed_users.values())
        self._sync_group_membership_for_users(diff)
