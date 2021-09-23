"""lifecycle main file"""

import argparse
import importlib
import sys
from lifecycle.config_reader import ConfigReader

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


def main():
    """Entry point for the lifecyle cli"""
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

    if "source" in config.config:
        source_mod = importlib.import_module(
            f"lifecycle.source_{config.config.source.module.lower()}",
        )
        # pylint: disable-msg=invalid-name
        Source = getattr(source_mod, f"Source{config.config.source.module}")
        current_source = Source(config.config["source"]["config"])
        print(current_source)


if __name__ == "__main__":
    main()
