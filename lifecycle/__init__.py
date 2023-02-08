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


class _Base(ABC):
    """Abstract base class for sources and targets"""

    def __init__(self, config: Dict):
        self.users = {}

        self.config = self.configure(config)
        if not isinstance(self.config, Mapping):
            raise ConfigException(
                f"{self.__class__.__name__}.configure() has not set a valid config"
            )

    @abstractmethod
    def configure(self, config: Dict) -> Dict:
        """Apply defaults to loaded configs and perform validation"""

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

        source_users = self.source.fetch_users()
        target_users = self.fetch_users()
        diff_config = ModelDifferenceConfig(
            # TODO: Include groups.
            fields=[
                "username",
                "forename",
                "surname",
                "fullname",
                "email",
                "locked",
            ],
            groups_patterns=[],
        )
        difference = ModelDifference.calculate(source_users, target_users, diff_config)

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
