import logging.config
import configparser


def parse_config(configfile):
    """Parse and validate the given config file."""
    config = configparser.ConfigParser()
    config.read(str(configfile))

    logging.config.fileConfig(str(configfile))
    return config
