import threading
import queue
import multiprocessing
from hns.signal_detector import SignalType


class AsyncCamera:
    """
    Asynchronous camera interface

    An `AsyncCamera` provides two queues:
        1. a `queue.Queue()` to use in the same process
        2. a `multiprocessing.Manager.Queue` to use with a `multiprocessing.Pool`

    Args:
        camera: the synchronous camera interface
    """

    def __init__(self, camera, signal_detector):
        #: Holds the camera interface
        self.camera = camera
        #: Holds the thread to capture camera frames
        self.capture_frames = threading.Thread(target=self._capture_frames, args=(signal_detector,))
        self.capture_frames.daemon = True
        #: Holds the event to stop the async frame capturing
        self.stop_event = threading.Event()
        #: Holds the queue to pass the last frame to the main thread
        self.main_thread_queue = queue.Queue(maxsize=1)
        #: Holds the queue to pass frames to the process workers
        self.pool_manager = multiprocessing.Manager()
        self.process_worker_queue = self.pool_manager.Queue()

    def start(self):
        """Start capturing frames with camera async."""
        self.capture_frames.start()

    def stop(self):
        """Stop capturing frames with camera async."""
        self.stop_event.set()
        self.capture_frames.join()

    def _capture_frames(self, signal_detector):
        for image in self.camera.stream():
            if self.stop_event.is_set():
                break

            cropped_image = signal_detector.crop_image(
                image, [SignalType.START_SIGNAL, SignalType.INFO_SIGNAL])

            try:
                # Needs to be empty to put in the latest frame
                self.main_thread_queue.get_nowait()
            except queue.Empty:
                pass

            self.main_thread_queue.put_nowait(cropped_image)
            self.process_worker_queue.put_nowait(cropped_image)
