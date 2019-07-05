import operator
import multiprocessing
from collections import defaultdict

from hns.logger import get_component_logger
from hns.signal_detector import SignalDetector, SignalType
from hns.digit_detector import DigitDetector
from hns.config import parse_config

logger = get_component_logger("AsyncInfosignalDetector")


class AsyncInfosignalDetector:
    """
    Async infosignal detector using multiprocessing

    Args:
        config: the config
        async_camera: the async camera interface
    """

    @classmethod
    def from_config(cls, configfile, config, async_camera):
        number_of_workers = config["workers"].getint("number_of_workers")
        logger.info(
            "Using AsyncInfosignalDetector settings: number_of_workers=%d",
            number_of_workers
        )
        return cls(configfile, config, number_of_workers, async_camera)

    def __init__(self, configfile, config, number_of_workers, async_camera):
        #: Holds the config
        self.configfile = configfile
        self.config = config
        self.number_of_workers = number_of_workers
        #: Holds the worker pool
        self.worker_pool = multiprocessing.Pool(processes=number_of_workers)
        #: Holds the worker asyncResults
        self.async_results = []
        #: Holds the async camera interface
        self.async_camera = async_camera
        #: Holds the stop event
        self.stop_event = self.async_camera.pool_manager.Event()

    def run(self):
        """
        Start the worker processes to detect info signal.
        Async camera must be started first.
        """
        for _ in range(self.number_of_workers):
            self.async_results.append(self.worker_pool.apply_async(
                detect_info_signal_worker,
                (self.configfile, self.async_camera.process_worker_queue, self.stop_event)))

    def get_result(self):
        """Stops the worker processes, collects the results and returns the most detected digit."""
        self.stop_event.set()
        all_results = []
        for result in self.async_results:
            all_results.extend(result.get())
        logger.info("Do Majority voting for detected INFO signals: '%s'", str(all_results))
        return self._majority_vote(all_results)

    def _majority_vote(self, results):
        votes = defaultdict(int)
        for digit in results:
            votes[digit] += 1
        return max(votes.items(), key=operator.itemgetter(1))[0]


def detect_info_signal_worker(configfile, camera_queue, stop_event):
    try:
        config = parse_config(configfile)
        signal_detector = SignalDetector.from_config(config["signal-detector"])
        digit_detector = DigitDetector.from_config(config["digit-detector"])
        signals_to_detect = [SignalType.INFO_SIGNAL]
        results = []

        print("Start INFO signal detection worker")
        while not stop_event.is_set():
            try:
                image = camera_queue.get(timeout=5)
            except:
                continue

            try:
                signal = signal_detector.detect(image, signal_types=signals_to_detect)
            except Exception as exc:
                # print("Error occured during signal detection: '%s'" % str(exc))
                continue

            if signal is None:
                # drop frame because we didn't detect a signal
                # print("Dropping no signal detected")
                continue

            if signal.type == SignalType.INFO_SIGNAL:
                try:
                    digit = digit_detector.detect(signal.image)
                except Exception as exc:
                    # print("Error occured during digit detection: '%s'" % str(exc))
                    continue
                if digit is None:
                    # false alarm, not a signal
                    # print("Dropping frame because no digit in signal detected")
                    continue
                print("Detected INFO signal", digit)
                results.append(digit)

        print("Stopping INFO signal detection worker with result", results)
        return results
    except Exception as exc:
        print("Exception: '{}'".format(exc))
        import traceback
        traceback.print_exc()
        raise
