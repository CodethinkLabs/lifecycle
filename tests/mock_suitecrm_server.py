"""Tools for a mock SuiteCRM server to use when testing"""


from datetime import datetime, timedelta
import json
import math
from unittest.mock import MagicMock

import jwt
import requests

from lifecycle import LifecycleException


class MethodException(LifecycleException):
    """Called when a method is called incorrectly or isn't valid"""


class MockSuiteCRMServer:
    """A substitute for a SuiteCRM server, useful in testing"""

    def __init__(self, data: list[dict] = None):
        if not data:
            self.data = [
                {
                    "type": "User",
                    "id": "c0ffee-cafe",
                    "attributes": {
                        "user_name": "foobar",
                        "first_name": "Foo",
                        "last_name": "Bar",
                        "full_name": "Foo Bar",
                        "email1": "foo.bar@example.org",
                        "status": "Active",
                    },
                },
            ]
        else:
            self.data = data

        self.id_index = 0

    def new_id(self):
        """Generates a new ID for entries"""
        id_str = f"{self.id_index:x}"
        self.id_index += 1
        return id_str

    def create_record(self, request_json: dict):
        """Generates a new record from the given request"""
        record_type = request_json["data"]["type"]
        attributes = request_json["data"]["attributes"]
        record_id = self.new_id()
        self.data.append(
            {
                "type": record_type,
                "id": record_id,
                "attributes": attributes,
            }
        )

    def search_by_type(self, entry_type):
        """Returns every entry that matches the type specified"""
        return list(entry for entry in self.data if entry["type"] == entry_type)

    def search_by_ids(self, ids: list[str]):
        """Returns every entry that matches one of the IDs specified

        It doesn't check that *every* ID is found, or if there are duplicate
        entries with the same ID.
        """
        return list(entry for entry in self.data if entry["id"] in ids)

    @staticmethod
    def module_response_data(module_data: list[dict], **kwargs):
        """Formats a list of data entries into a dict resembling a JSON
        response from a SuiteCRM server

        If the underlying request asks for paginated results, it will
        limit this to a subset of entries, as if a single page of results
        was viewed
        """
        if "params" not in kwargs:
            return {"data": module_data}

        pagesize = kwargs["params"]["page[size]"]
        page = kwargs["params"]["page[number]"]
        start = pagesize * (page - 1)
        end = pagesize * page
        total_pages = math.ceil(len(module_data) / pagesize)
        returned_data = [
            module_data[i] for i in range(start, end) if i < len(module_data)
        ]
        return {
            "meta": {
                "total-pages": total_pages,
            },
            "data": returned_data,
        }

    @staticmethod
    def mock_response(data=None, exception=None):
        """Generates a MagicMock that can be treated as a ``requests.response``"""
        # Used in Response:
        # .text, .json(), .raise_for_status()
        response = MagicMock()
        if data:
            response.json.return_value = data
            response.text = json.dumps(data, indent=2)
        else:
            response.json.side_effect = ValueError()
            response.text = ""

        if exception:
            response.raise_for_status.side_effect = exception
        return response

    def mock_get(self, endpoint, **kwargs):
        """Simulates a GET request to the SuiteCRM server"""
        if endpoint == "/Api/V8/module/Users":
            # The request could be paginated
            return self.mock_response(
                self.module_response_data(self.search_by_type("User"), **kwargs)
            )

        raise MethodException(f"Unhandled endpoint {endpoint}")

    def mock_patch(self, endpoint, **kwargs):
        """Simulates a PATCH request to the SuiteCRM server"""
        if not kwargs["json"]:
            raise MethodException("PATCH requires a json")

        if endpoint == "/Api/V8/module":
            entry_id = kwargs["json"]["data"]["id"]
            entry_type = kwargs["json"]["data"]["type"]
            entry_attributes = kwargs["json"]["data"]["attributes"]
            found_entries = self.search_by_ids([entry_id])
            if not found_entries:
                return self.mock_response(
                    exception=requests.HTTPError(
                        "can't patch an entry that doesn't exist, 404 probably"
                    )
                )
            assert len(found_entries) == 1
            assert found_entries[0]["type"] == entry_type

            if int(entry_attributes.get("deleted", "0")):
                # We actually want to delete this user
                self.data.remove(found_entries[0])
                return self.mock_response()

            # User not deleted, do an ordinary update
            # We didn't copy any dicts when searching, so can just amend the
            # one returned by searching
            found_entries[0]["attributes"].update(entry_attributes)
            return self.mock_response()

        raise MethodException(f"Unhandled endpoint '{endpoint}'")

    def mock_post(self, endpoint, **kwargs):
        """Simulates a POST request to the SuiteCRM server"""
        if endpoint == "/Api/access_token":
            token_expiry = (datetime.now() + timedelta(hours=1)).timestamp()
            access_token = jwt.encode(
                payload={
                    "exp": token_expiry,
                },
                key="",
            )
            return self.mock_response(
                {
                    "access_token": access_token,
                }
            )

        if not kwargs["json"]:
            raise MethodException("Can't POST without a json unless authenticating")

        if endpoint == "/Api/V8/module":
            new_user = kwargs["json"]
            self.create_record(new_user)
            return self.mock_response()

        raise MethodException(f"Unhandled endpoint {endpoint}")