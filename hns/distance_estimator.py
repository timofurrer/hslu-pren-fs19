"""
Implements functionality to estimate the distances on an image.
"""

from hns.logger import get_component_logger

logger = get_component_logger("DistanceEstimator")


class DistanceEstimator:
    """Estimate distances to a cropped image.

    The distance is currently estimated by using
    the dimensions of a cropped image.

    This estimater needs calibration.
    """
    def estimate(self, cropped_image):
        """Estimate the distance to the cropped image
            :return distance to stopsign in Millimeter mm.
        """
        height, *_ = cropped_image.shape
        return ((-4.1225) * height) + 372.02 - 32
