"""
Implement the interface to the crane
for the cube pick up.
"""

from threading import Event

from hns.logger import get_component_logger

logger = get_component_logger("Crane")


class Crane:
    """
    Interface to the Crane responsible to pick up and hold the cube.
    """

    def __init__(self):
        #: Holds an Event which indicates if the cube was picked up
        self.__cube_picked_up = Event()

    def picked_up(self):
        """Notify the Crane that the cube is successfully picked up"""
        logger.info("Cube has been picked up")
        self.__cube_picked_up.set()

    def wait_for_cube(self):
        """Wait until the cube is picked up"""
        logger.debug("Waiting for the cube to be picked up")
        picked = self.__cube_picked_up.wait()
        logger.debug("Finished waiting for the cube to be picked up: %d", picked)
        return picked

    def is_picked(self):
        """Check if the cube is picked up"""
        return self.__cube_picked_up.is_set()
