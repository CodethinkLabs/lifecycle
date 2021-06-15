# Config reading for lifecycle

import yaml
import glob
import os.path


class ConfigReader:
    def __init__(self, file):
        self.config = {}

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
                    self.config.update(yaml.safe_load(config_file))
                except (yaml.YAMLError, ValueError) as exc:
                    print("Config read failed when parsing {}!".format(file))
                    print("Error was: {}".format(exc))
                    exit(1)

    def print(self):
        print(yaml.dump(self.config, default_flow_style=False, default_style=""))
