"""Config reader for lifecycle"""

from ast import literal_eval
import glob
import logging
import os
import string
import sys

from addict import Dict
import yaml


class ConfigReader:
    """Reads a file or folder of yaml configuration files"""

    def __init__(self, file, raw=False):
        """Parse the specified file or folder into self.config"""
        self.config = None
        self.config_raw = {}

        if os.path.isdir(file):
            filelist = sorted(glob.glob(file + "/*.yml"))
        elif os.path.isfile(file):
            filelist = [file]
        else:
            logging.error("Specified config file couldn't be found: %s", file)
            sys.exit(1)

        for current_file in filelist:
            with open(current_file, "r", encoding="utf-8") as config_file:
                try:
                    self.config_raw.update(yaml.safe_load(config_file))
                except (yaml.YAMLError, ValueError) as exc:
                    logging.error(
                        "Config read failed when parsing %s! Error was: %s",
                        current_file,
                        str(exc),
                    )
                    sys.exit(1)

        if not raw:
            try:
                config_dict = literal_eval(
                    string.Template(str(self.config_raw)).substitute(**os.environ)
                )
                self.config = Dict(config_dict)
            except KeyError as exc:
                logging.error(
                    "The environment variable %s used in your config file wasn't provided!",
                    str(exc),
                )
                sys.exit(1)
        else:
            self.config = Dict(self.config_raw)

    def print(self):
        """Print the current configuration to the terminal"""
        print(yaml.dump(self.config, default_flow_style=False, default_style=""))

    def print_raw(self):
        """Print the current configuration, without templating environment variables"""
        print(yaml.dump(self.config_raw, default_flow_style=False, default_style=""))
