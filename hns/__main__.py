"""
Entry point for 2/4 HNS
"""

import sys
import pathlib
import logging
import argparse
import threading

from hns.core import HNS
from hns.logger import get_component_logger

logger = get_component_logger("main")

logging.basicConfig(level=logging.INFO)

#: Holds a global thread-specific context variable for the HNS app
context = threading.local()


def main(args=sys.argv[1:]):
    """
    Main entry point for the 2/4 HNS control software.
    """
    parser = argparse.ArgumentParser(description="2/4 HNS Control Software")
    parser.add_argument(
        "configfile", metavar="CONFIG", nargs="?",
        default=pathlib.Path(__file__).parent / "../configs/stable.ini",
        type=pathlib.Path,
        help="Path to the configuration file"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true",
        help="Enable debug mode"
    )

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    context.hns = HNS(args.configfile, debug=args.debug)
    context.hns.run()


if __name__ == "__main__":
    main()
