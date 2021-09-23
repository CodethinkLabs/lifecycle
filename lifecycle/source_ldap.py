"""Source for pulling users and groups from LDAP """

import sys


class SourceLDAP:
    """Given an ldap server config, will collect user and groups from said LDAP server"""

    config = {}

    def __init__(self, config=None):
        """Create an LDAP source.  If config is supplied automatically reconfigure."""
        if config:
            self.reconfigure(config)

    def reconfigure(self, config):
        """Apply new configuration to object.

        The newly supplied config entry will be merged over the existing config.
        """
        error = None

        if not isinstance(config, dict):
            error = "You must provide a configuration dict to use this function"
        if "hostname" not in config:
            error = "Hostname must be specified"
        if "base_dn" not in config:
            error = "Base DN must be specified"
        if not ("bind_dn" in config and "bind_password" in config) and not config.get(
            "anonymous_bind", False
        ):
            error = "Please either specify a user DN & password, or set anonymous_bind to true"
        if error:
            print(error)
            sys.exit(1)

        default_config = {
            "anonymous_bind": False,
            "use_ssl": True,
            "port": 636,
        }

        self.config.update(default_config)
        self.config.update(config)

    def connect(self):
        """Connect to LDAP server using current configuration."""

    def fetch(self):
        """Fetch users / groups from LDAP into lifecycle user and group objects"""
