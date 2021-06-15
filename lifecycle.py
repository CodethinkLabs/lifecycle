# lifecycle main file

import argparse
from lib.ConfigReader import ConfigReader

parser = argparse.ArgumentParser()
parser.add_argument(
    "-c",
    "--configcheck",
    action="store_true",
    help="Parse the config, display and exit.",
)
parser.add_argument(
    "-f",
    "--file",
    help="config file location.  Either a single file or a folder of yaml files.",
    default="config/",
)

if __file__ == "__main__":
    args = parser.parse_args()

    config = ConfigReader(args.file)
    if args.configcheck:
        print("Config check requested.  Config-as-read is:")
        print("")
        config.print()
        exit(0)
