"""
HNS Signal Detector
"""

from pathlib import Path
from collections import namedtuple

import cv2
import numpy as np

from hns.logger import get_component_logger
from hns.utils import timeit
from hns.models import SignalType

logger = get_component_logger("SignalDetector")

# Type to represent a detected signal
DetectedSignal = namedtuple("DetectedSignal", ["type", "image", "data"])


def sliding_window(image, window_size, step_size=1):
    for y in range(0, image.shape[0], step_size):
        for x in range(0, image.shape[1], step_size):
            yield (x, y, image[y:y + window_size[1], x:x + window_size[0]])


class SignalDetector:
    """
    Functionality to detect a signal.

    Supported Signals are:
        * Infosignal
        * Stoppsignal

    Args:
        config: the Signal Detector configuration
    """
    @classmethod
    def from_config(cls, config):
        logger.info(
            "Using canny settings: threshold1=%s, threshold2=%s, aperture size=%s",
            config["canny_threshold1"],
            config["canny_threshold2"],
            config["canny_aperture_size"]
        )
        logger.info(
            "Using box detection settings: min box size=%s",
            config["minimum_box_size"]
        )
        logger.info(
            "Using start signal settings: template=%s, match confidence=%s",
            config["startsignal_template"],
            config["startsignal_match_confidence"]
        )

        # cache config to speed-up image processing
        canny_threshold1 = config.getint("canny_threshold1")
        canny_threshold2 = config.getint("canny_threshold2")
        canny_aperture_size = config.getint("canny_aperture_size")
        minimum_box_size = config.getint("minimum_box_size")
        startsignal_template = Path(__file__).parent / config["startsignal_template"]
        startsignal_match_confidence = config.getfloat("startsignal_match_confidence")
        return cls(
            canny_threshold1,
            canny_threshold2,
            canny_aperture_size,
            minimum_box_size,
            startsignal_template,
            startsignal_match_confidence
        )

    def __init__(self, canny_threshold1, canny_threshold2, canny_aperture_size,
                 minimum_box_size,
                 startsignal_template, startsignal_match_confidence):
        self.__canny_threshold1 = canny_threshold1
        self.__canny_threshold2 = canny_threshold2
        self.__canny_aperture_size = canny_aperture_size
        self.__minimum_box_size = minimum_box_size
        self.__startsignal_match_confidence = startsignal_match_confidence

        # load and prepare startsignal template
        self.__startsignal_template = cv2.resize(cv2.imread(str(startsignal_template)), (30, 30))
        self.__startsignal_template_hsv = cv2.cvtColor(
                self.__startsignal_template, cv2.COLOR_BGR2HSV)
        self.__startsignal_lower_blue_mask = np.array([110, 180, 0])
        self.__startsignal_upper_blue_mask = np.array([130, 255, 255])
        self.__startsignal_template_hist = cv2.calcHist(
            [self.__startsignal_template_hsv],
            channels=[0, 1], mask=None, histSize=[45, 32], ranges=[0, 180, 0, 256])
        cv2.normalize(
            self.__startsignal_template_hist, self.__startsignal_template_hist,
            alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

        self.__laplace_filter = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]])

    @timeit(logger, "SignalDetector::crop and detect")
    def crop_and_detect(self, image, signal_types=None):
        image = self.crop_image(image, signal_types)
        return self.detect(image, signal_types)

    @timeit(logger, "SignalDetector::entire detection")
    def detect(self, image, signal_types=None):
        """Detect a signal in the given image.

        Args:
            image (numpy.array): 3 channel RGB numpy image
        """
        if SignalType.START_SIGNAL in signal_types:
            is_start_signal, data = self._find_startsignal(image)
            if is_start_signal:
                return DetectedSignal(SignalType.START_SIGNAL, image, data)

        if SignalType.STOP_SIGNAL not in signal_types \
                and SignalType.INFO_SIGNAL not in signal_types:
            return None

        image, gray_image = self._prepare_image(image)
        contours = self._get_contours(image)
        image = self._find_number_on_signal(image, contours, gray_image)
        if image is None:
            return None

        detected_signal_type = (
                SignalType.STOP_SIGNAL
                if SignalType.STOP_SIGNAL in signal_types
                else SignalType.INFO_SIGNAL
        )
        return DetectedSignal(detected_signal_type, image, None)

    @timeit(logger, "SignalDetector::crop image")
    def crop_image(self, image, signal_types):
        # crop image according to the signal type
        if SignalType.STOP_SIGNAL in signal_types:
            return image[image.shape[0] // 2:, :]
        elif SignalType.INFO_SIGNAL in signal_types or SignalType.START_SIGNAL in signal_types:
            return image[:image.shape[0] // 2, :]

    @timeit(logger, "SignalDetector::find startsignal")
    def _find_startsignal(self, image):
        matched_signal_bhatt = float("inf")
        matched_signal_pos = None

        # crop image to a view from 50-200 Pixel in X
        image = image[:, 50:200]

        image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(
                image_hsv,
                self.__startsignal_lower_blue_mask, self.__startsignal_upper_blue_mask)

        if np.count_nonzero(mask) < 450:
            return False, (matched_signal_bhatt, matched_signal_pos)

        sliding_window_generator = sliding_window(
            image_hsv,
            (self.__startsignal_template.shape[0], self.__startsignal_template.shape[1]),
            step_size=10
        )

        for x, y, window in sliding_window_generator:
            window_hist = cv2.calcHist(
                [window], channels=[0, 1], mask=None,
                histSize=[45, 32], ranges=[0, 180, 0, 256])
            cv2.normalize(window_hist, window_hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
            dist_bhatt = cv2.compareHist(
                # window_hist, self.__startsignal_template_hist,
                self.__startsignal_template_hist, window_hist,
                cv2.HISTCMP_BHATTACHARYYA)

            if matched_signal_bhatt >= dist_bhatt:
                matched_signal_bhatt = dist_bhatt
                matched_signal_pos = (x, y)

                if matched_signal_bhatt <= self.__startsignal_match_confidence:
                    logger.info(
                        "Found start signal at %s with bhatt distance of %f in confidence %f",
                        str(matched_signal_pos),
                        matched_signal_bhatt, self.__startsignal_match_confidence)
                    break

        logger.debug(
            "Highest confidence for start signal %f <= %f",
            matched_signal_bhatt, self.__startsignal_match_confidence)
        return (
            matched_signal_bhatt <= self.__startsignal_match_confidence,
            (matched_signal_bhatt, matched_signal_pos)
        )

    @timeit(logger, "SignalDetector::image preparation")
    def _prepare_image(self, image):
        # gray scaling
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # edge detection with canny (https://docs.opencv.org/3.1.0/da/d22/tutorial_py_canny.html)
        canny_image = cv2.Canny(
                gray_image,
                self.__canny_threshold1, self.__canny_threshold2,
                self.__canny_aperture_size
        )

        laplace_image = cv2.filter2D(canny_image, -1, self.__laplace_filter)
        return laplace_image, gray_image

    @timeit(logger, "SignalDetector::get contours")
    def _get_contours(self, image):
        # find contours in the given image
        # _, contours = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[:2]
        _, contours = cv2.findContours(image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[:2]
        return contours

    @timeit(logger, "SignalDetector::find number on signal")
    def _find_number_on_signal(self, image, contours, gray_image):
        for contour_id, contour in enumerate(contours):
            # skip too small objects
            if abs(cv2.contourArea(contour)) < self.__minimum_box_size:
                logger.debug("Drop contour because it's area is too small")
                continue

            # find that box
            x, y, w, h = cv2.boundingRect(contour)

            # drop contour with wrong widths
            if w <= 4 or w >= 50:
                logger.debug("Drop contour because width wrong")
                continue

            # drop contour with wrong heights
            if h <= 15 or h >= 60:
                logger.debug("Drop contour because height wrong")
                continue

            # drop contour with wrong ratios
            h_w_ratio = float(h) / float(w)
            if h_w_ratio < 1.45 or h_w_ratio > 6:
                logger.debug("Drop contour because ratio wrong %f / %f = %f", h, w, h_w_ratio)
                continue

            def is_garbage():
                addition_in_y = h // 8
                addition_in_x = w // 3

                cropped_number = gray_image[
                    max(0, y - addition_in_y): min(y + h + addition_in_y, gray_image.shape[0]),
                    max(0, x - addition_in_x): min(x + w + addition_in_x, gray_image.shape[1])
                ]

                # it needs to be at least 20 pixels in height
                if cropped_number.shape[0] < 20:
                    logger.debug(
                        "Drop as garbage because it's not at least 20 pixel in height, it's %d",
                        cropped_number.shape[0])
                    return True

                binary_number = cv2.threshold(cropped_number, 30, 255, cv2.THRESH_BINARY)[1]
                # from hns.utils import debug_image
                # debug_image(binary_number)

                def array_is_white(array):
                    # 255 * 0.75 = 191.25
                    return array.sum() >= (array.size * 191.25)

                # invert black signals
                if not array_is_white(binary_number[-1, :]):
                    binary_number = cv2.bitwise_not(binary_number)

                # check if all borders are white enough
                if not array_is_white(binary_number[:, 0]):
                    logger.debug("Drop as garbage because left border is not white enough")
                    return True

                if not array_is_white(binary_number[:, -1]):
                    logger.debug("Drop as garbage because right border is not white enough")
                    return True

                if not array_is_white(binary_number[0, :]):
                    logger.debug("Drop as garbage because top border is not white enough")
                    return True

                if not array_is_white(binary_number[-1, :]):
                    logger.debug("Drop as garbage because bottom border is not white enough")
                    return True

                # calculate the ratio between black and white pixels
                b_w_ratio = np.count_nonzero(binary_number) / np.prod(binary_number.shape)
                if b_w_ratio < 0.5 or b_w_ratio > 0.9:
                    logger.debug(
                        "Drop as garbage because black and white ratio is wrong %f", b_w_ratio)
                    return True

                # check if a middle row only contains white color
                rows, _ = binary_number.shape
                bound = round(rows * 0.2)
                middle_rows = binary_number[bound:-1 * bound, :]
                for row in middle_rows:
                    if row.sum() == row.size * 255:
                        logger.debug(
                            "Drop as garbage because a row between %d and %d was completely white",
                            bound, -1 * bound)
                        return True

                # it's most likely not garbage
                return False

            if is_garbage():
                logger.debug("Drop contour because it might be a window")
                continue

            addition_in_y = round(h / 5)
            addition_in_x = round(w / 2)
            cropped_image = gray_image[
                max(0, y - addition_in_y): min(y + h + addition_in_y, gray_image.shape[0]),
                max(0, x - addition_in_x): min(x + w + addition_in_x, gray_image.shape[1])
            ]
            return cropped_image

        return None
