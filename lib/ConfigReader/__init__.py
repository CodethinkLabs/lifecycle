""" Config reading for lifecycle """

import yaml
import glob
import os
import os.path
import string
import collections


class ConfigReader:
    def __init__(self, file, raw=False):
        self.config = {}
        self.config_raw = {}

        if os.path.isdir(file):
            filelist = sorted(glob.glob(file + "/*.yml"))
        elif os.path.isfile(file):
            filelist = [file]
        else:
            print("Specified config file couldn't be found! {}!".format(file))
            exit(1)

        for file in filelist:
            with open(file, "r") as config_file:
                try:
                    self.config_raw.update(yaml.safe_load(config_file))
                except (yaml.YAMLError, ValueError) as exc:
                    print("Config read failed when parsing {}!".format(file))
                    print("Error was: {}".format(exc))
                    exit(1)

        if not raw:
            try:
                self.config = eval(
                    string.Template(str(self.config_raw)).substitute(**os.environ)
                )
            except KeyError as exc:
                print(
                    "The environment variable {} used in your config file wasn't provided!".format(
                        exc
                    )
                )
                exit(1)
        else:
            self.config = self.config_raw

    def print(self):
        print(yaml.dump(self.config, default_flow_style=False, default_style=""))

    def print_raw(self):
        print(yaml.dump(self.config_raw, default_flow_style=False, default_style=""))
