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
        self.id_index = 0
        if data is None:
            self.data = []

            self.create_user(
                {
                    "user_name": "foobar",
                    "first_name": "Foo",
                    "last_name": "Bar",
                    "full_name": "Foo Bar",
                    "email1": "foo.bar@example.org",
                    "status": "Active",
                }
            )
        else:
            self.data = data

    def new_id(self):
        """Generates a new ID for entries"""
        id_str = f"{self.id_index:x}"
        self.id_index += 1
        return id_str

    def create_user(
        self, attributes: dict, user_id: str = "", emails: list[str] = None
    ):
        """Creates a new user and inserts it into the data model"""

        if not user_id:
            user_id = self.new_id()

        # Replicate email1 being the first in the list of E-mails added
        if emails:
            if "email1" not in attributes:
                attributes["email1"] = emails[0]
        else:
            if "email1" in attributes:
                emails = [attributes["email1"]]
            else:
                emails = []

        if "email1" not in attributes:
            attributes["email1"] = ""

        # Replicate full_name being a concatenation of first_name and last_name
        # weirdly, full name overrides the names if set
        if "full_name" not in attributes:
            attributes["full_name"] = (
                f"{attributes.get('first_name', '')} "
                f"{attributes.get('last_name', '')}"
            ).strip()
        split_name = attributes["full_name"].split(" ", 1)
        attributes["first_name"] = split_name[0]
        if len(split_name) > 1:
            attributes["last_name"] = split_name[1]
        else:
            # I know this is bizarre. blame SuiteCRM
            attributes["last_name"] = split_name[0]

        user_entry = {
            "type": "User",
            "id": user_id,
            "attributes": attributes,
            "relationships": {
                "EmailAddress": {
                    "links": {
                        "related": f"V8/module/Users/{user_id}/relationships/email_addresses",
                    }
                },
                "SecurityGroups": {
                    "links": {
                        "related": f"V8/module/Users/{user_id}/relationships/SecurityGroups",
                    }
                },
            },
            "_relationships": {"email_addresses": [], "SecurityGroups": []},
        }

        self.data.append(user_entry)

        self.assign_emails(user_id, emails)

        return user_id

    def assign_emails(self, user_id: str, emails: list[str]):
        """Assign the listed E-mail addresses to the user with the specified ID"""

        user_entry = self.search_by_id(user_id)
        assert user_entry

        if emails and not user_entry["attributes"]["email1"]:
            user_entry["attributes"]["email1"] = emails[0]
        for email in emails:
            if not email:
                # it could be an empty string
                continue

            assert len(email) > 1, "Accidentally creating a single-character E-mail"
            mail_id = self.create_record(
                {
                    "data": {
                        "type": "EmailAddress",
                        "attributes": {"email_address": email},
                    },
                }
            )
            user_entry["_relationships"]["email_addresses"].append(mail_id)

    def create_record(self, request_json: dict):
        """Generates a new record from the given request"""
        record_type = request_json["data"]["type"]
        attributes = request_json["data"]["attributes"]

        if record_type == "User":
            return self.create_user(attributes)

        record_id = self.new_id()
        self.data.append(
            {
                "type": record_type,
                "id": record_id,
                "attributes": attributes,
            }
        )
        return record_id

    def search_by_type(self, entry_type):
        """Returns every entry that matches the type specified"""
        return list(entry for entry in self.data if entry["type"] == entry_type)

    def search_by_ids(self, ids: list[str]):
        """Returns every entry that matches one of the IDs specified

        It doesn't check that *every* ID is found, or if there are duplicate
        entries with the same ID.
        """
        return list(entry for entry in self.data if entry["id"] in ids)

    def search_by_id(self, entry_id: str) -> dict:
        """Returns the entry that matches the ID specified

        If no entry is found, it returns an empty dict
        """
        found_entries = self.search_by_ids([entry_id])
        assert len(found_entries) <= 1
        if found_entries:
            return found_entries[0]

        return {}

    def get_related_entries_for_module(self, entry_id: str, relationship: str):
        """Returns all the entries related to an entry for a given relationship name"""

        entry = self.search_by_id(entry_id)
        if not entry:
            # NOTE: probably nicer to raise some kind of exception
            return None

        related_ids = entry["_relationships"][relationship]
        return self.search_by_ids(related_ids)

    def get_entry_by_attribute(self, attribute_name: str, attribute_value):
        """Returns the first entry which has an attribute of the specified name
        matching the specified value
        """

        for entry in self.data:
            if attribute_name not in entry["attributes"]:
                continue

            if entry["attributes"][attribute_name] == attribute_value:
                return entry
        return None

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

    @staticmethod
    def map_module(module_name: str) -> str:
        """Translates a module's alias to the underlying module"""

        module_map = {
            "Users": "User",
            "User": "User",
            "EmailAddress": "EmailAddress",
            "SecurityGroup": "SecurityGroup",
        }
        if module_name not in module_map:
            raise MethodException(
                f"query with module name '{module_name}' is not a known alias of a module"
            )
        return module_map[module_name]

    @staticmethod
    def map_relationship(module_name: str, related_module_name: str) -> str:
        """Translates a related module's name to its relationship name for a given module"""

        relationships = {
            ("User", "EmailAddress"): "email_addresses",
            ("User", "SecurityGroup"): "SecurityGroups",
        }
        relation_tuple = (
            MockSuiteCRMServer.map_module(module_name),
            related_module_name,
        )
        if relation_tuple not in relationships:
            raise MethodException(
                f"query with module name '{module_name}' trying to relate "
                f"a '{related_module_name}' could not find a relationship name"
            )
        return relationships[relation_tuple]

    def mock_get(self, endpoint, **kwargs):
        """Simulates a GET request to the SuiteCRM server"""

        print(f"Simulating GET for {endpoint}")

        # zeroth entry was a blank space before the slash
        query = endpoint.split("/")[1:]

        assert query[0] == "Api"
        if len(query) == 4 and query[1] == "V8" and query[2] == "module":
            # /Api/V8/module/<modulename>, i.e. get all entries for that module
            module_name = self.map_module(query[3])
            found_modules = self.search_by_type(module_name)
            return self.mock_response(
                self.module_response_data(found_modules, **kwargs)
            )

        if (
            len(query) == 7
            and query[1] == "V8"
            and query[2] == "module"
            and query[5] == "relationships"
        ):
            # /Api/V8/module/<modulename>/<module_id>/relationships/<relationship_name>
            module_name = self.map_module(query[3])
            module_id = query[4]
            relationship_name = query[6]

            related_entries = self.get_related_entries_for_module(
                module_id, relationship_name
            )
            return self.mock_response(
                self.module_response_data(related_entries, **kwargs)
            )

        raise MethodException(f"Unhandled endpoint {endpoint}")

    def patch_entry(self, entry_id: str, entry_type: str, new_attributes: dict):
        """Replaces the attributes of an entry with the given attributes

        In addition, this deletes the entry if 'deleted' gets set to 1
        """
        entry = self.search_by_id(entry_id)
        if not entry:
            return self.mock_response(
                exception=requests.HTTPError(
                    "can't patch an entry that doesn't exist, 404 probably"
                )
            )
        assert entry["type"] == entry_type
        if int(new_attributes.get("deleted", "0")):
            # We actually want to delete this entry
            self.data.remove(entry)
        else:
            entry["attributes"].update(new_attributes)

        return self.mock_response()

    def mock_patch(self, endpoint, **kwargs):
        """Simulates a PATCH request to the SuiteCRM server"""

        print(f"Simulating PATCH for {endpoint}")

        if not kwargs["json"]:
            raise MethodException("PATCH requires a json")

        if endpoint == "/Api/V8/module":
            entry_id = kwargs["json"]["data"]["id"]
            entry_type = kwargs["json"]["data"]["type"]
            entry_attributes = kwargs["json"]["data"]["attributes"]
            self.patch_entry(entry_id, entry_type, entry_attributes)
            return self.mock_response()

        raise MethodException(f"Unhandled endpoint '{endpoint}'")

    def create_relationship(
        self, entry_type: str, entry_id: str, related_type: str, related_id: str
    ) -> MagicMock:
        """Creates a relationship between two entries, returning a mock response"""
        entry_type = self.map_module(entry_type)
        entry = self.search_by_id(entry_id)
        if not entry:
            return self.mock_response(
                exception=requests.HTTPError(
                    f"404 probably, no module with ID {entry_id}"
                )
            )
        assert entry_type == entry["type"]
        relationship_name = self.map_relationship(entry_type, related_type)
        entry["_relationships"][relationship_name].append(related_id)
        return self.mock_response()

    def mock_post(self, endpoint, **kwargs):
        """Simulates a POST request to the SuiteCRM server"""

        print(f"Simulating POST for {endpoint}")

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

        # zeroth entry is a blank space before the slash
        query = endpoint.split("/")[1:]
        assert query[0] == "Api"
        if (
            len(query) == 6
            and query[1] == "V8"
            and query[2] == "module"
            and query[5] == "relationships"
        ):
            # /Api/V8/module/<modulename>/<module_id>/relationships, aka create relationship
            module_name = query[3]
            module_id = query[4]
            return self.create_relationship(
                module_name,
                module_id,
                kwargs["json"]["data"]["type"],
                kwargs["json"]["data"]["id"],
            )

        if endpoint == "/Api/V8/module":
            new_user = kwargs["json"]
            self.create_record(new_user)
            return self.mock_response()

        raise MethodException(f"Unhandled endpoint {endpoint}")

    def delete_relationship(
        self, entry_type: str, entry_id: str, relationship_name: str, related_id: str
    ) -> MagicMock:
        """Deletes a relationship between two entries"""

        entry_type = self.map_module(entry_type)
        entry = self.search_by_id(entry_id)
        if not entry:
            return self.mock_response(
                exception=requests.HTTPError(
                    f"404 probably, no module with ID {entry_id}"
                )
            )
        assert entry["type"] == entry_type
        entry["_relationships"][relationship_name].remove(related_id)

        return self.mock_response()

    # pylint: disable-msg=unused-argument
    def mock_delete(self, endpoint, **kwargs):
        """Simulates a DELETE request to the SuiteCRM server"""

        print(f"Simulating DELETE for {endpoint}")

        query = endpoint.split("/")[1:]
        assert query[0] == "Api"
        if (
            len(query) == 8
            and query[1] == "V8"
            and query[2] == "module"
            and query[5] == "relationships"
        ):
            # /Api/V8/module/<modulename>/<module_id>/relationships/<relationship>/<related_id>
            module_name = query[3]
            module_id = query[4]
            relationship_name = query[6]
            related_id = query[7]
            return self.delete_relationship(
                module_name, module_id, relationship_name, related_id
            )

        raise MethodException(f"Unhandled endpoint {endpoint}")
