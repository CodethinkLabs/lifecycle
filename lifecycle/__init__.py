"""Lifecycle management namespace"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
import logging
from typing import Dict, Optional

from .model_diff import ModelDifference, ModelDifferenceConfig
from .models import User


class LifecycleException(Exception):
    """Generic Lifecycle exception. Base class for all the others"""


class ConfigException(LifecycleException):
    """Exception relating to configuration errors"""


class ConfigUnexpectedType(ConfigException):
    """Exception caused by configure() method returning an unexpected type"""

    def __init__(self, origin_class, config):
        self.origin_class = origin_class
        self.config = config
        self.message = (
            f"{origin_class.__name__}.configure() returned an "
            + f"unexpected type. Returned config was '{config}'"
        )
        super().__init__(self.message)


class ConfigMissingFields(ConfigException):
    """Exception caused by config having missing fields"""

    def __init__(self, missing_fields, config):
        self.config = config
        self.missing_fields = missing_fields
        self.message = (
            f"Config dict has fields '{config.keys()}', "
            + f"missing fields '{missing_fields}'"
        )
        super().__init__(self.message)


class ConfigUnexpectedFields(ConfigException):
    """Exception caused by config having unexpected fields"""

    def __init__(self, unexpected_fields, config):
        self.config = config
        self.unexpected_fields = unexpected_fields
        self.message = (
            f"Config dict has fields '{config.keys()}', "
            + "unexpected fields '{unexpected_fields}'"
        )
        super().__init__(self.message)


class _Base(ABC):
    """Abstract base class for sources and targets"""

    mandatory_fields = set()
    optional_fields = set()
    default_config = {}
    supported_user_fields = User.supported_fields()

    def __init__(self, config: Dict):
        self.users = {}

        self.config = self.configure(config)
        if not isinstance(self.config, Mapping):
            raise ConfigUnexpectedType(self.__class__, config)

    @staticmethod
    def _check_fields(_dict: Dict, mandatory_fields: set, optional_fields: set):
        """Check a dictionary's fields are valid

        :raises ConfigMissingFields: If there are missing fields
        :raises ConfigUnexpectedFields: If there are unexpected fields
        """
        missing_fields = mandatory_fields - set(_dict.keys())
        if missing_fields:
            raise ConfigMissingFields(missing_fields, _dict)
        unexpected_fields = set(_dict.keys()) - mandatory_fields - optional_fields
        if unexpected_fields:
            raise ConfigUnexpectedFields(unexpected_fields, _dict)

    def configure(self, config: Dict) -> Dict:
        """Apply defaults to loaded configs and perform validation"""
        self._check_fields(config, self.mandatory_fields, self.optional_fields)

        return self.default_config | config

    @abstractmethod
    def fetch_users(self, refresh: bool = False) -> Dict[str, User]:
        """Load users from services and map to the User model"""


class SourceBase(_Base):
    """Abstract base class for sources"""


class TargetBase(_Base):
    """Abstract base class for targets"""

    def __init__(self, config: Dict, source: SourceBase):
        super().__init__(config)

        self.source = source

    def process_stages(self):
        """Determine the differences in user models and execute configured stages"""
        enabled_stages = self.config["stages"]
        if not enabled_stages:
            logging.warning("No stages set for '%s', skipping", self.__class__.__name__)
            return

        difference = self.calculate_difference()
        print(difference)

        for stage in ("users_create", "users_cleanup", "users_sync"):
            if stage in enabled_stages:
                method = getattr(self, stage)
                try:
                    method(difference)
                except NotImplementedError:
                    logging.warning(
                        "%s not implemented for %s, skipping",
                        method.__name__,
                        self.__class__.__name__,
                    )
                    continue

    def calculate_difference(self):
        """Calculates the difference between the users in the source and the users in the target"""
        source_users = self.source.fetch_users()
        target_users = self.fetch_users()
        diff_config = ModelDifferenceConfig(
            fields=self.source.supported_user_fields & self.supported_user_fields,
            groups_patterns=[],
        )
        difference = ModelDifference.calculate(source_users, target_users, diff_config)
        return difference

    def users_create(self, diff: ModelDifference):
        """Create any users missing from the target"""
        raise NotImplementedError(
            f"{self.__class__.__name__} has not implemented the 'users_create' method"
        )

    def users_cleanup(self, diff: ModelDifference):
        """Remove any users missing from the source"""
        raise NotImplementedError(
            f"{self.__class__.__name__} has not implemented the 'users_cleanup' method"
        )

    def users_sync(self, diff: ModelDifference):
        """Synchronise user metadata differences between the source and the target"""
        raise NotImplementedError(
            f"{self.__class__.__name__} has not implemented the 'users_sync' method"
        )
