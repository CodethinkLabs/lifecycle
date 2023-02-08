"""Target for synchronising users and groups to SuiteCRM"""

from datetime import datetime
import logging
from typing import Dict
from urllib.parse import urljoin

import jwt
import requests

from . import LifecycleException, TargetBase
from .model_diff import ModelDifference
from .models import User


class TargetSuiteCRM(TargetBase):
    """Interface for synchronising users and groups to SuiteCRM target"""

    def __init__(self, *args):
        super().__init__(*args)

        self._token = None
        self._token_expiry = 0

    def configure(self, config: Dict):
        """Apply new configuration to object.

        The newly supplied config entry will be merged over the existing config.
        """
        errors = []
        for key in (
            "url",
            "api_client_id",
            "api_client_secret",
            "api_username",
            "api_password",
        ):
            if key not in config:
                errors.append(f"Required key '{key}' missing from {config['module']}")
        if errors:
            raise LifecycleException("\n".join(errors))

        defaults = {
            "api_page_size": 20,
            "stages": ["users_create", "users_sync", "users_disable", "users_cleanup"],
            "excluded_usernames": [],
        }
        return defaults | config

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

        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response

    def _iter_pages(self, endpoint: str, page: int = 1):
        """Generator for handling paginated responses from the SuiteCRM API"""
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

    def fetch_users(self, refresh: bool = False) -> Dict[str, User]:
        """Load the SuiteCRM users"""
        if not refresh and self.users:
            return self.users

        users = {}

        _json = list(self._iter_pages("/Api/V8/module/Users"))

        for obj in _json:
            attributes = obj["attributes"]
            user = User(
                username=attributes["user_name"],
                forename=attributes["first_name"],
                surname=attributes["last_name"],
                fullname=attributes["full_name"],
                email=attributes["email1"],
                groups=[],
                locked=attributes["status"].lower() != "active",
            )
            users[obj["id"]] = user

        self.users = users
        return users

    def users_create(self, diff: ModelDifference):
        """Create any users missing from the target"""
        for user in diff.added_users.values():
            new_user = {
                "data": {
                    "type": "User",
                    "attributes": {
                        "user_name": user.username,
                        "last_name": user.surname,
                        "full_name": user.fullname,
                        "name": user.fullname,
                        "external_auth_only": 1,
                        "email1": user.email,
                        "status": "Inactive" if user.locked else "Active",
                    },
                }
            }
            logging.info("Creating user: %s", user.username)
            self._request("/Api/V8/module", method="POST", json=new_user)

    def users_cleanup(self, diff: ModelDifference):
        """Remove any users missing from the source"""
        for _id, user in diff.removed_users.items():
            if user.username not in self.config["excluded_usernames"]:
                logging.info("Deleting user: %s", user.username)
            self._request(f"/Api/v8/module/Users/{_id}", method="DELETE")
