import serial
import threading
import struct
import collections
from operator import xor
from hns.logger import get_component_logger


class UartCommunication:

    def __init__(self):
        self.logger = get_component_logger("UART.Communication")
        self.communicator = UartCommunicator()
        self.runner = UartRunner(self.communicator)

    def start(self):
        self.logger.info("Start")
        self.communicator.open()
        self.runner.start()

    def stop(self):
        self.logger.info("Stop")
        self.runner.stop()
        self.communicator.close()

    def set_target_speed(self, percent):
        self.logger.info("Set target speed: %s", percent)
        self.communicator.set_target_speed(percent)

    def set_distance_to_go(self, distance):
        self.logger.info("Set distance to go: %s", distance)
        self.communicator.set_distance_to_go(distance)

    def get_status(self):
        return self.communicator.get_status()

    def register_status_updated_handler(self, handler):
        self.communicator.register_status_updated_handler(handler)


class UartRunner:

    def __init__(self, communicator):
        self.write_thread = None
        self.read_thread = None
        self.stop_event = threading.Event()
        self.stop_event.set()
        self.new_data_to_send_event = threading.Event()
        self.communicator = communicator
        self.communicator.register_movement_command_updated_handler(
            lambda event_arg: self.new_data_to_send_event.set())

    def start(self):
        if not self.stop_event.is_set():
            return
        self.stop_event.clear()
        self.new_data_to_send_event.clear()
        self.write_thread = threading.Thread(target=self._write_task, name="write_thread")
        self.read_thread = threading.Thread(target=self._read_task, name="read_thread")
        self.write_thread.start()
        self.read_thread.start()

    def stop(self):
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        self.new_data_to_send_event.set()
        self.write_thread.join()
        self.read_thread.join()

    def _write_task(self):
        while not self.stop_event.is_set():
            if self.new_data_to_send_event.is_set():
                self.new_data_to_send_event.clear()
                self.communicator.write()
            self.new_data_to_send_event.wait()

    def _read_task(self):
        while not self.stop_event.is_set():
            self.communicator.read()


FRAME_MINIMAL_LENGTH = 8


class UartCommunicator:

    def __init__(self):
        self.logger = get_component_logger("UART.Communicator")
        self.target_movement = (0, 0)
        self.latest_status = (0, 0, 0, 0, 0)
        self.uart = None
        self.read_queue = collections.deque()
        self.movement_command_updated_handler = None
        self.status_updated_handler = None

    def open(self):
        self.logger.info("Open serial port")
        if self.uart is None:
            self.uart = serial.Serial(
                port="/dev/serial0",
                baudrate=115200,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE,
                timeout=3
            )
        elif not self.uart.is_open:
            self.uart.open()

    def close(self):
        self.logger.info("Close serial port")
        if (self.uart is not None) and self.uart.is_open:
            self.uart.close()
            self.read_queue.clear()

    def write(self):
        try:
            frame = encode_to_frame(
                struct.pack("<BB", self.target_movement[0], self.target_movement[1]))
            self.logger.info("bytes out: %s", bytes_to_string(frame))
            self.uart.write(frame)
        except struct.error as error:
            self.logger.error("struc.error during packing payload: %s", error)

    def read(self):
        batch = self.uart.read(8)
        self.logger.info("bytes in: %s", bytes_to_string(batch))
        self.read_queue.extend(batch)
        frame = pop_frame(self.read_queue)
        while len(frame) > 0:
            self.logger.info("found new frame %s", bytes_to_string(frame))
            try:
                self.latest_status = struct.unpack("<BbbHB", decode_frame(frame))
                _notify_updated_handler(self.status_updated_handler, self.get_status())
            except struct.error as error:
                self.logger.error("struc.error during unpacking payload: %s", error)
            frame = pop_frame(self.read_queue)

    def set_target_speed(self, percent):
        self.target_movement = int(round(255 / 100 * percent)), 0
        _notify_updated_handler(self.movement_command_updated_handler, None)

    def set_distance_to_go(self, distance):
        self.target_movement = self.target_movement[0], int(distance / 8.45)
        _notify_updated_handler(self.movement_command_updated_handler, None)

    def get_status(self):
        return {
            "current speed": self.latest_status[0] / 80,
            "acceleration x": self.latest_status[1] / 6,
            "acceleration y": self.latest_status[2] / 6,
            "wheel cycles": self.latest_status[3] / 9,
            "status byte": self.latest_status[4]
        }

    def register_movement_command_updated_handler(self, handler):
        self.movement_command_updated_handler = handler

    def register_status_updated_handler(self, handler):
        self.status_updated_handler = handler


def _notify_updated_handler(handler, event_arg):
    if handler is not None:
        handler(event_arg)


START = 0x7E
STOP = 0x7D
ESCAPE = 0x7C
ESCAPE_MASK = 0x20


def encode_to_frame(payload):
    frame = bytearray()
    frame.append(START)

    for byte in payload:
        if byte == START or byte == STOP or byte == ESCAPE:
            frame.extend([ESCAPE, xor(byte, ESCAPE_MASK)])
        else:
            frame.append(byte)

    frame.append(STOP)
    return bytes(frame)


def pop_frame(deque):
    try:
        # first discarding everything until first start byte found
        byte = deque.popleft()
        while byte != START:
            byte = deque.popleft()
        frame = bytearray()
        frame.append(byte)
    except IndexError:
        # no start byte found in queue
        return bytearray(0)

    try:
        # secondly pop bytes until stop byte found
        byte = deque.popleft()
        while byte != STOP:
            if byte == START:
                # another start byte found after the last start byte with no stop byte in between.
                # everything appended so far is trash
                frame.clear()
            frame.append(byte)
            byte = deque.popleft()
        frame.append(byte)
        return frame
    except IndexError:
        # no stop byte found in queue, so no complete frame available yet.
        # restore already popped bytes to queue
        deque.extend(frame)
        return bytearray(0)


def decode_frame(frame):
    frame_length = len(frame)
    if frame_length < 2 or frame[0] != START or frame[frame_length - 1] != STOP:
        print("invalid frame")
        return bytearray(0)

    payload = bytearray()
    frame_index = 1
    while frame_index < frame_length - 1:
        if frame[frame_index] == ESCAPE:
            if frame_index < frame_length - 2:
                frame_index = frame_index + 1
                payload.append(xor(frame[frame_index], ESCAPE_MASK))
        else:
            payload.append(frame[frame_index])

        frame_index = frame_index + 1

    return payload


def bytes_to_string(data):
    return ''.join(['{0:0{1}X} '.format(byte, 2) for byte in data])


# if __name__ == "__main__":
#     test_manual_read_status()
