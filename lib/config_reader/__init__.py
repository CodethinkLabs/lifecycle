"""Config reader for lifecycle"""

import glob
import os
import os.path
import string
import sys
from ast import literal_eval
import yaml


class ConfigReader:
    """Reads a file or folder of yaml configuration files"""

    def __init__(self, file, raw=False):
        """Parse the specified file or folder into self.config"""
        self.config = {}
        self.config_raw = {}

        if os.path.isdir(file):
            filelist = sorted(glob.glob(file + "/*.yml"))
        elif os.path.isfile(file):
            filelist = [file]
        else:
            print("Specified config file couldn't be found! {}!".format(file))
            sys.exit(1)

        for current_file in filelist:
            with open(current_file, "r") as config_file:
                try:
                    self.config_raw.update(yaml.safe_load(config_file))
                except (yaml.YAMLError, ValueError) as exc:
                    print("Config read failed when parsing {}!".format(current_file))
                    print("Error was: {}".format(exc))
                    sys.exit(1)

        if not raw:
            try:
                self.config = literal_eval(
                    string.Template(str(self.config_raw)).substitute(**os.environ)
                )
            except KeyError as exc:
                print(
                    "The environment variable {} used in your config file wasn't provided!".format(
                        exc
                    )
                )
                sys.exit(1)
        else:
            self.config = self.config_raw

    def print(self):
        """Print the current configuration to the terminal"""
        print(yaml.dump(self.config, default_flow_style=False, default_style=""))

    def print_raw(self):
        """Print the current configuration, without templating environment variables"""
        print(yaml.dump(self.config_raw, default_flow_style=False, default_style=""))
