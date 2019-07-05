"""
HNS 2/4 camera interface
"""

import time

try:
    from picamera.array import PiRGBArray
    from picamera import PiCamera
except ImportError:
    # We are not on a raspberry pi
    from unittest import mock
    PiRGBArray = mock.MagicMock()
    PiCamera = mock.MagicMock()


from hns.logger import get_component_logger

logger = get_component_logger("Camera")


class Camera:
    @classmethod
    def from_config(cls, config):
        logger.info(
            "Using Camera settings: resolution=%s, rotation=%s, shutter_speed=%s, iso=%s",
            config["resolution"], config["rotation"], config["shutter_speed"], config["iso"]
        )
        resolution = config.get("resolution").split("x")
        rotation = config.getint("rotation")
        shutter_speed = config.getint("shutter_speed")
        iso = config.getint("iso")
        return cls((int(resolution[0]), int(resolution[1])), rotation, shutter_speed, iso)

    def __init__(self, resolution, rotation, shutter_speed, iso):
        self.__resolution = resolution
        self.__rotation = rotation
        self.__shutter_speed = shutter_speed
        self.__iso = iso

        logger.info("Initializing camera ...")
        self._camera = PiCamera()
        self._camera.resolution = self.__resolution
        self._camera.rotation = self.__rotation
        self._camera.shutter_speed = self.__shutter_speed
        self._camera.iso = self.__iso
        self.__raw_capture = PiRGBArray(self._camera, size=self.__resolution)
        # let camera initialize properly
        time.sleep(2)
        logger.info("Camera initialized")

    def reset(self):
        """Reset stream"""
        # clear the stream in preparation for the next frame
        self.__raw_capture.truncate(0)

    def stream(self):
        """Access the camera stream"""
        # capture frames from the camera
        for frame in self._camera.capture_continuous(
                self.__raw_capture, format="bgr", use_video_port=True):

            # grab the raw NumPy array representing the image
            image = frame.array
            yield image

            # clear the stream in preparation for the next frame
            self.__raw_capture.truncate(0)
