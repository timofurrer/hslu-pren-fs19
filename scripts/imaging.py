#!/usr/bin/python3

import csv
import time
import logging
from pathlib import Path

import cv2

from hns.core import HNS
from hns.signal_detector import SignalType

logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).parent / ".."
train = HNS(ROOT_DIR / "configs/stable.ini")

train.comm.start()

logging.info("Press any key to start the test drive or press Ctrl+C")
input()

signal_types = [SignalType.INFO_SIGNAL, SignalType.START_SIGNAL]


frames = []
try:
    train.comm.set_target_speed(30)
    time.sleep(1)

    logging.info("Let's gooo")

    for frame_id, frame in enumerate(train.camera.stream()):
        frame_starttime = time.time()
        signal = train.signal_detector.crop_and_detect(frame, signal_types=signal_types)
        if signal is None:
            frame_duration = time.time() - frame_starttime
            frames.append((frame_id, frame, frame, "none", 0, frame_duration))
            logging.info("Frame %d detected nothing in %f seconds", frame_id, frame_duration)
            continue

        if signal.type == SignalType.START_SIGNAL:
            frame_duration = time.time() - frame_starttime
            frames.append((frame_id, frame, signal.image, signal.type, "START", frame_duration))
            logging.info("Frame %d is a start signal in %f seconds", frame_id, frame_duration)
            continue

        try:
            digit = train.digit_detector.crop_and_detect(signal.image)
        except Exception as exc:
            logging.error("Failed to detect number, because: %s", str(exc))
            digit = 0

        frame_duration = time.time() - frame_starttime
        frames.append((frame_id, frame, signal.image, signal.type, digit, frame_duration))
        logging.info("Frame %d detected %s in %f seconds", frame_id, digit, frame_duration)
except Exception as exc:
    print(exc)
    pass
except KeyboardInterrupt:
    pass

train.comm.set_target_speed(0)
time.sleep(10)
train.comm.stop()

logging.info("Saving frames for analysis ...")

RESULT_DIR = Path() / (str(int(time.time())))
RESULT_DIR.mkdir(parents=True)

with open(str(RESULT_DIR / "frames.csv"), 'w', newline="") as csvfile:
    framewriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)

    # write frames to disk for further analysis
    for frame_id, frame, frame_signal, signal_type, detected_digit, frame_time in frames:
        frame_image_path = str(RESULT_DIR / "frame-{}.jpg".format(frame_id))
        frame_signal_image_path = str(RESULT_DIR / "frame-{}-signal.jpg".format(frame_id))
        cv2.imwrite(frame_image_path, frame)
        cv2.imwrite(frame_signal_image_path, frame_signal)
        framewriter.writerow([
            str(frame_id), str(detected_digit),
            frame_image_path, frame_signal_image_path, str(signal_type), str(frame_time)])


logging.info("Results at: %s", str(RESULT_DIR))
