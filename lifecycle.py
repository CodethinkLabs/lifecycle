# lifecycle main file

import argparse
from lib.ConfigReader import ConfigReader

parser = argparse.ArgumentParser()
parser.add_argument(
    "-c", "--configcheck", action="store_true", help="Parse the config and exit."
)
args = parser.parse_args()

config = ConfigReader()
if args.configcheck:
    print("Config check requested.  Config-as-read is:")
    print("")
    config.print()
    exit(0)
