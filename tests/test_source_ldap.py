""" Basic functionality tests for LDAP source

This will likely mostly be to do with checking the logic of config settings,
unless we can mock an entire ldap server somehow.
"""

import pytest
from lifecycle.source_ldap import SourceLDAP


def test_config_basic():
    """Test an LDAP source with minimal config can be created"""
    source = SourceLDAP(
        config={
            "hostname": "example.org",
            "base_dn": "dc=example,dc=org",
            "anonymous_bind": True,
        }
    )
    assert source.config["hostname"] == "example.org"
    assert source.config["base_dn"] == "dc=example,dc=org"
    assert source.config["anonymous_bind"] is True
    assert source.config["port"] == 636
    assert source.config["use_ssl"] is True


def test_config_no_creds():
    """LDAP Source with no credentials or anonymous_bind should fail"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        SourceLDAP(
            config={
                "hostname": "example.org",
                "base_dn": "dc=example,dc=org",
            }
        )
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_config_no_creds_anon_false():
    """LDAP Source with no credentials and anonymous_bind set to false should fail"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        SourceLDAP(
            config={
                "hostname": "example.org",
                "base_dn": "dc=example,dc=org",
                "anonymous_bind": False,
            }
        )
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_config_with_creds():
    """LDAP Source with credentials and no anonymous_bind should work ok"""
    source = SourceLDAP(
        config={
            "hostname": "example.org",
            "base_dn": "dc=example,dc=org",
            "bind_dn": "cn=blep,dc=example,dc=org",
            "bind_password": "password",
        }
    )
    assert source.config["anonymous_bind"] is False
    assert source.config["bind_dn"] == "cn=blep,dc=example,dc=org"
    assert source.config["bind_password"] == "password"
