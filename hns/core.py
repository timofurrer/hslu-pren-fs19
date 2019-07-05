"""
HNS 2/4 Command and Control Functionalities.
"""

import time
from threading import Thread

from hns.config import parse_config
from hns.logger import get_component_logger

from hns.uart_communication import UartCommunication
from hns.crane import Crane
from hns.camera import Camera
from hns.signal_detector import SignalDetector, SignalType
from hns.digit_detector import DigitDetector
from hns.distance_estimator import DistanceEstimator
from hns.sound_output import SoundOutput
from hns.async_camera import AsyncCamera
from hns.async_infosignal_detector import AsyncInfosignalDetector

logger = get_component_logger("HNS")
telemetry_logger = get_component_logger("telemetry")


class HNS:
    """
    Core Application for the 2/4 HNS control software.

    Args:
        configfile (str, pathlib.Path): path to the config file
    """
    def __init__(self, configfile, debug=False):
        self.debug = debug
        self.config = parse_config(configfile)
        self.wheel_revolutions = 0
        logger.info("Created HNS from config %s", configfile)

        #: Holds configuration for the drive
        self._full_speed = self.config["drive"].getint("full_speed")
        self._stop_speed = self.config["drive"].getint("stop_speed")

        #: Holds the camera interface
        self.camera = Camera.from_config(self.config["camera"])

        #: Holds the Signal Detector to detect Info- and Stop-Signals
        self.signal_detector = SignalDetector.from_config(
            self.config["signal-detector"])

        #: Holds the async camera interface
        self.async_camera = AsyncCamera(self.camera, self.signal_detector)

        #: Holds the async infosignal detector
        self.async_infosignal_detector = AsyncInfosignalDetector.from_config(
            configfile, self.config, self.async_camera)

        #: Holds the Digit Detector
        self.digit_detector = DigitDetector.from_config(
            self.config["digit-detector"])

        #: Holds the Distance Estimator to estimate distance to Stop-Signals
        self.distance_estimator = DistanceEstimator()

        #: Holds the Crane instance
        self.crane = Crane()

        #: Holds the UART communication interface
        self.comm = UartCommunication()
        self.comm.register_status_updated_handler(self._status_updated)

        #: Holds the sound output actor
        self.sound = SoundOutput.from_config(self.config["sound"])

    def _status_updated(self, current_status):
        self.wheel_revolutions = current_status['wheel cycles']

        if current_status["status byte"] & 0x01 == 1 and not self.crane.is_picked():
            self.crane.picked_up()
            logger.debug("Received status byte indicating cube has been picked")

        telemetry_logger.info("status {0} %".format(current_status))

    def run(self):
        """Run the main loop of the control software."""
        logger.info("Starting HNS main loop")

        logger.info("Starting async INFO signal detectors")
        self.async_infosignal_detector.run()

        logger.info("Starting UART communication")
        self.comm.start()
        logger.info("Started UART communication")

        logger.info("Wait until the Crane picks up the cube ...")
        self.crane.wait_for_cube()
        logger.info("Cube seems to be loaded")

        signal_to_stop = self._speed_laps()
        self._drive_until_stop_signal(signal_to_stop)

        time.sleep(10)
        self.sound._buzz(3000, 1)

        logger.info("Stopping UART communication")
        self.comm.stop()
        logger.info("Stopped UART communication")

        logger.info("Shutdown HNS main loop")

    def _speed_laps(self):
        """Drive required laps full speed

        Returns:
            digit (int): the stop signal number to stop at
        """
        # in the beginning, we just watch out for the start and info signal
        signals_to_detect = [SignalType.START_SIGNAL]
        signal_to_stop = None
        laps = 0
        last_detected_start_signal = time.time()
        debounce_time_after_start_signal = 0.5

        logger.info("Start async camera")
        self.async_camera.start()

        logger.info("Drive, bitch, drive! Speed up until %d", self._full_speed)
        self.comm.set_target_speed(self._full_speed)

        while True:
            try:
                image = self.async_camera.main_thread_queue.get(timeout=5)
            except:
                continue

            try:
                signal = self.signal_detector.detect(image, signal_types=signals_to_detect)
            except Exception as exc:
                logger.error("Error occured during signal detection: '%s'", str(exc))
                continue

            if signal is None:
                # drop frame because we didn't detect a signal
                logger.debug("Dropping frame because no signal detected")
                continue

            if last_detected_start_signal + debounce_time_after_start_signal >= time.time():
                logger.debug("Detected same signal again - do not register as a lap")
                last_detected_start_signal = time.time()
                continue

            laps += 1
            last_detected_start_signal = time.time()
            logger.info("Increasing Lap count to %d", laps)
            if laps == 3:
                logger.info("Passed the Start Signal the 3rd time, so now we need to stop")
                logger.info("Slow down to stopping speed of %d", self._stop_speed)
                self.comm.set_target_speed(self._stop_speed)
                signal_to_stop = self.async_infosignal_detector.get_result()
                self.async_camera.stop()
                logger.info("Voted for STOP signal: %d", signal_to_stop)

                sound_thread = Thread(target=self.sound.output_number, args=(signal_to_stop,))
                sound_thread.daemon = True
                sound_thread.start()
                logger.info(
                    "Detected the Info Signal with number %d, shouting it out loud", signal_to_stop)

                return signal_to_stop

        return None

    def _drive_until_stop_signal(self, stop_signal_number):
        """Drive until the correct stop signal is found"""

        self.camera.reset()

        logger.info("Drive until the STOP signal %d is found", stop_signal_number)

        signal_to_detect = [SignalType.STOP_SIGNAL]
        remaining_distance_until_stop = 0

        for image in self.camera.stream():
            try:
                signal = self.signal_detector.crop_and_detect(image, signal_types=signal_to_detect)
            except Exception as exc:
                logger.error("Error occured during signal detection: '%s'", str(exc))
                continue

            if signal is None:
                # drop the frame
                logger.debug("Dropping frame because no signal detected")
                continue

            try:
                digit = self.digit_detector.detect(signal.image)
            except Exception as exc:
                logger.error("Error occured during digit detection: '%s'", str(exc))
                continue
            if digit is None:
                # false alarm, not a signal
                logger.debug("Dropping frame because no digit in signal detected")
                continue

            logger.info("Found a Stop Signal with digit: %d", digit)

            if digit == stop_signal_number:
                logger.info("Detected correct digit %d to stop and wait until stopped", digit)
                self.comm.set_target_speed(0)  # stop before a STOP Signal
                while self.comm.get_status()["current speed"] != 0:
                    logger.debug("wait for approach to complete")

                time.sleep(1)
                logger.info("Successfully stopped")
                break

        self.camera.reset()
        image_stream = self.camera.stream()
        image = next(image_stream)

        signal = self.signal_detector.crop_and_detect(image, signal_types=[SignalType.STOP_SIGNAL])
        distance = self.distance_estimator.estimate(signal.image)
        logger.info(
                "Found the Stop Signal %d where we need to stop in %fcmd",
                digit, distance)

        remaining_distance_until_stop = distance
        logger.info(
                "We are in distance to stop. Distance remaining: %f",
                remaining_distance_until_stop)

        self.comm.set_distance_to_go(remaining_distance_until_stop)
        time.sleep(1)
        logger.info("Completed stop drive!!")
