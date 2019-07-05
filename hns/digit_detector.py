"""
HNS Digit Detector
"""

from pathlib import Path

import cv2
import numpy as np
from keras.models import load_model

from hns.logger import get_component_logger
from hns.utils import timeit

logger = get_component_logger("DigitDetector")


class DigitDetector:
    """
    Functionality to detect a digit from an image.

    Args:
        config: the Digit Detector configuration
    """
    @classmethod
    def from_config(cls, config):
        model_path = Path(__file__).parent / config["model"]
        logger.info("Using model=%s", model_path)
        return cls(model_path)

    def __init__(self, model_path):
        self.model_path = model_path

        # Load trained weights
        self.__model = load_model(str(self.model_path))

    @timeit(logger, "DigitDetector::entire detection")
    def detect(self, image):
        """Detect a digit in the given image

        Args:
            image (numpy.array): 1 channel grayscale image
        """
        image = self._prepare_image(image)
        vectorized_image = image.reshape(1, 28, 28, 1)
        predictions = self.__model.predict(vectorized_image)
        logger.debug("Predicated image possibilities: %s", str(predictions))

        # choose the digit with greatest possibility as predicted digit
        predicted_digit = np.argmax(predictions)
        if predicted_digit == 0:
            logger.debug("No digit found in image")
            return None

        logger.debug("Predicted digit in image: %d", predicted_digit)
        return predicted_digit

    @timeit(logger, "DigitDetector::preprocess image for detection")
    def _prepare_image(self, image):
        scaled_image = cv2.resize(image, (28, 28))
        return scaled_image
