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

        total_pages = _json["meta"]["total-pages"]
        while page != total_pages:
            page += 1
            yield from self._iter_pages(endpoint, page)
        logging.debug("Done iterating")

    def fetch_users(self, refresh: bool = False) -> Dict[str, User]:
        """Load the SuiteCRM users"""
        if not refresh and self.users:
            return self.users

        users = {}
        users_data = {}

        _json = list(self._iter_pages("/Api/V8/module/Users"))

        for obj in _json:
            attributes = obj["attributes"]
            username = attributes["user_name"]
            user = User(
                username=username,
                forename=attributes["first_name"],
                surname=attributes["last_name"],
                fullname=attributes["full_name"],
                email=(attributes["email1"],),
                groups=(),
                locked=attributes["status"].lower() != "active",
            )
            users[username] = user
            users_data[username] = obj

        logging.debug("Users fetched from server: '%s'", users)
        self.users = users
        self._users_data = users_data
        return users

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

    def users_cleanup(self, diff: ModelDifference):
        """Remove any users missing from the source"""
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
