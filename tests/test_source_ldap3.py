""" Basic functionality tests for LDAP source

This checks the logic of config settings and mocks an LDAP server connection.
"""

from unittest.mock import MagicMock, PropertyMock

import pytest

from lifecycle.source_ldap3 import SourceLDAP3


def test_config_basic():
    """Test an LDAP source with minimal config can be created"""
    source = SourceLDAP3(
        config={
            "url": "ldaps://ldap.example.org",
            "base_dn": "dc=example,dc=org",
            "anonymous_bind": True,
        }
    )
    assert source.config["url"] == "ldaps://ldap.example.org"
    assert source.config["base_dn"] == "dc=example,dc=org"
    assert source.config["anonymous_bind"] is True
    assert source.config["use_ssl"] is True


def test_config_no_creds():
    """LDAP Source with no credentials or anonymous_bind should fail"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        SourceLDAP3(
            config={
                "url": "ldap://ldap.example.org",
                "base_dn": "dc=example,dc=org",
            }
        )
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_config_no_creds_anon_false():
    """LDAP Source with no credentials and anonymous_bind set to false should fail"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        SourceLDAP3(
            config={
                "url": "ldap://ldap.example.org",
                "base_dn": "dc=example,dc=org",
                "anonymous_bind": False,
            }
        )
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_config_with_creds():
    """LDAP Source with credentials and no anonymous_bind should work ok"""
    source = SourceLDAP3(
        config={
            "url": "ldap://ldap.example.org",
            "base_dn": "dc=example,dc=org",
            "bind_dn": "cn=blep,dc=example,dc=org",
            "bind_password": "password",
        }
    )
    assert source.config["anonymous_bind"] is False
    assert source.config["bind_dn"] == "cn=blep,dc=example,dc=org"
    assert source.config["bind_password"] == "password"


@pytest.fixture(name="ldap_connection")
def fixture_ldap_connection(mocker):
    """Fixture to create a test LDAP connection"""

    def _ldap_connection(user_data):
        mock_entries = []
        for entry in user_data:
            mock_entry = MagicMock()
            type(mock_entry).entry_attributes_as_dict = entry
            mock_entries.append(mock_entry)

        mock_connection = MagicMock()
        property_entries = PropertyMock(return_value=mock_entries)
        type(mock_connection).entries = property_entries

        mocker.patch(
            "lifecycle.source_ldap3.SourceLDAP3.connect", return_value=mock_connection
        )

    return _ldap_connection


@pytest.fixture(name="source")
def fixture_source():
    """Fixture to create a test Modelsource"""
    return SourceLDAP3(
        config={
            "url": "ldap://ldap.example.org",
            "base_dn": "dc=example,dc=org",
            "bind_dn": "johndoe",
            "bind_password": "insecure",
            "anonymous_bind": True,
        }
    )


def test_current_user(source, ldap_connection):
    """Test a single current user in a single group"""
    my_user_data = [
        {
            "uid": ["jsmith"],
            "mail": ["john.smith@codethink.co.uk"],
            "surName": ["Smith"],
            "nsAccountLock": [],
            "givenName": ["John"],
            "description": [],
        }
    ]

    ldap_connection(my_user_data)
    source.fetch_users()

    assert len(source.users) == 1
    assert "jsmith" in source.users
    user = source.users["jsmith"]
    assert user.surname == "Smith"
    assert user.fullname == "John Smith"
    assert user.forename == "John"
    assert user.email == ["john.smith@codethink.co.uk"]
    assert len(user.groups) == 0

    my_group_data = [
        {
            "description": ["Built In Default group for all users"],
            "cn": ["ipausers"],
            "member": [
                "uid=jsmith,cn=users,cn=accounts,dc=codethink,dc=co,dc=uk",
            ],
            "mail": ["ipausers@codethink.co.uk"],
        }
    ]

    ldap_connection(my_group_data)
    source.fetch_groups()

    assert len(user.groups) == 1
    group = user.groups[0]
    assert group.name == "ipausers"
    assert group.description == "Built In Default group for all users"
    assert group.email == ["ipausers@codethink.co.uk"]
