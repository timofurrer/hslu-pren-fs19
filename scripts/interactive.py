#!/usr/bin/python3

import sys
import csv
import time
import logging
from pathlib import Path

import cv2

from hns.core import HNS
from hns.config import parse_config
from hns.camera import Camera
from hns.signal_detector import SignalDetector, SignalType
from hns.digit_detector import DigitDetector

logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).parent / ".."

config = parse_config(ROOT_DIR / "configs/stable.ini")

train = HNS(ROOT_DIR / "configs/stable.ini")	
