"""lifecycle main file"""

import argparse
import sys
from lib.config_reader import ConfigReader

parser = argparse.ArgumentParser()
parser.add_argument(
    "-c",
    "--configcheck",
    action="store_true",
    help="Parse the config files, replace environment variables, display and exit.",
)
parser.add_argument(
    "-r",
    "--configraw",
    action="store_true",
    help="When performing a config check, do not parse environment variables.",
)
parser.add_argument(
    "-f",
    "--file",
    help="config file location.  Either a single file or a folder of yaml files.",
    default="config/",
)

if __name__ == "__main__":
    args = parser.parse_args()

    config = ConfigReader(args.file, args.configraw)
    if args.configcheck:
        if args.configraw:
            print("Raw config check requested.  Config is:")
            print("")
            config.print_raw()
        else:
            print("Config check requested.  Config is:")
            print("")
            config.print()
        sys.exit(0)
