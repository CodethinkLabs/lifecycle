"""lifecycle main file"""

import argparse
import importlib
import logging
import sys

from lifecycle.config_reader import ConfigReader


def parse_args():
    """Parse command line arguments."""
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
    parser.add_argument(
        "-d",
        "--debug",
        help="enable debug mode",
        action="store_true",
    )
    return parser.parse_args()


def main():
    """Entry point for the lifecyle cli"""
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    config = ConfigReader(args.file, args.configraw)
    if args.configcheck:
        if args.configraw:
            logging.info("Raw config check requested.  Config is:\n")
            config.print_raw()
        else:
            logging.info("Config check requested.  Config is:\n")
            config.print()
        sys.exit(0)

    if "source" in config.config:
        source_mod = importlib.import_module(
            f"lifecycle.source_{config.config.source.module.lower()}",
        )
        # pylint: disable-msg=invalid-name
        Source = getattr(source_mod, f"Source{config.config.source.module}")
        current_source = Source(config.config.source)
        current_source.fetch()

    if "targets" in config.config:
        for target in config.config.targets:
            try:
                target_mod = importlib.import_module(
                    f"lifecycle.target_{target.module.lower()}",
                )
            except ModuleNotFoundError:
                logging.warning(
                    "No module found for target '%s', skipping", target.module
                )
                continue
            # pylint: disable-msg=invalid-name
            Target = getattr(target_mod, f"Target{target.module}")
            current_target = Target(target, current_source)
            current_target.process_stages()


if __name__ == "__main__":
    main()
