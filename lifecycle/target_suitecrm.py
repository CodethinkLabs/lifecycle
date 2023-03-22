"""Target for synchronising users and groups to SuiteCRM"""

from datetime import datetime
import logging
from typing import Dict
from urllib.parse import urljoin

import jwt
import requests

from . import TargetBase
from .model_diff import ModelDifference
from .models import User


class TargetSuiteCRM(TargetBase):
    """Interface for synchronising users and groups to SuiteCRM target"""

    def __init__(self, *args):
        super().__init__(*args)

        self._token = None
        self._token_expiry = 0
        self._users_data = {}
        self._emails_to_id = {}

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
        "locked",  # also groups once supported
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
            while page != total_pages:
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
            user = User(
                username=username,
                forename=attributes["first_name"],
                surname=attributes["last_name"],
                fullname=attributes["full_name"],
                groups=(),
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

    def _add_missing_emails(self, emails):
        emails_to_id = self._fetch_all_emails(refresh=True)
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

        # Finish now if none of our new users have more than one E-mail address
        if not any(len(user.email) > 1 for user in diff.added_users.values()):
            return

        added_emails = set()
        for user in diff.added_users.values():
            for mail in user.email[1:]:
                added_emails.add(mail)
        self._add_missing_emails(added_emails)

        # Refresh E-mails so we have the new E-mails' IDs.
        self._fetch_all_emails(refresh=True)
        # Refresh users so we have the new users' IDs.
        self.fetch_users(refresh=True)
        # Link E-mail addresses to our new users
        for user in diff.added_users.values():
            for mail in user.email[1:]:
                self._assign_email(mail, user.username)

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

    def users_sync(self, diff: ModelDifference):
        """Sync the existing users with their values from the source"""
        self.fetch_users()
        all_source_emails = set()
        all_target_emails = set()
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

                all_source_emails |= set(diff.source_users[user.username].email)
                all_target_emails |= set(diff.target_users[user.username].email)

        # Add to suitecrm all E-mail addresses that have been added but don't exist
        added_emails = all_source_emails - all_target_emails
        self._add_missing_emails(added_emails)

        # Refresh E-mails so we have the new E-mails' IDs.
        self._fetch_all_emails(refresh=True)

        # For each updated user, assign that user's added E-mails and unassign removed E-mails.
        for user in diff.changed_users.values():
            if user.username not in self.config["excluded_usernames"]:
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
