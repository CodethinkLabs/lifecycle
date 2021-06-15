# Config reading for lifecycle

import yaml
import glob


class ConfigReader:
    def __init__(self, folder="config/"):
        self.config = {}

        for file in sorted(glob.glob(folder + "*.yml")):
            with open(file, "r") as config_file:
                try:
                    self.config.update(yaml.safe_load(config_file))
                except (yaml.YAMLError, ValueError) as exc:
                    print("Config read failed when parsing {}!".format(file))
                    print("Error was: {}".format(exc))
                    exit(1)

    def print(self):
        print(yaml.dump(self.config, default_flow_style=False, default_style=""))
