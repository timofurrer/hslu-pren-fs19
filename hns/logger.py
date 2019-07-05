"""
Module with the logger configuration for the HNS.
"""

import logging

#: Holds the root looger name
LOGGER_NAME = "hns"

logger = logging.getLogger(LOGGER_NAME)


def get_component_logger(name):
    """Return a component specific logger instance."""
    return logging.getLogger(LOGGER_NAME + "." + name)
