import time

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    # NOTE(TF): RPi.GPIO refuses to be imported on systems
    #           other than the RPI.
    #           So we just provide a mock for testing.
    from unittest import mock
    GPIO = mock.MagicMock()


from hns.logger import get_component_logger

logger = get_component_logger("Sound")


class SoundOutput:
    @classmethod
    def from_config(cls, config):
        logger.info(
            "Using SoundOutput settings: buzzer_pin=%s, pitch=%s, pitch_duration=%s, interval=%s",
            config["buzzer_pin"],
            config["pitch"],
            config["pitch_duration"],
            config["interval"],
        )
        buzzer_pin = config.getint("buzzer_pin")
        pitch = config.getint("pitch")
        pitch_duration = config.getfloat("pitch_duration")
        interval = config.getfloat("interval")
        return cls(buzzer_pin, pitch, pitch_duration, interval)

    def __init__(self, buzzer_pin, pitch, pitch_duration, interval):
        GPIO.setmode(GPIO.BCM)
        self.buzzer_pin = buzzer_pin
        self.pitch = pitch
        self.pitch_duration = pitch_duration
        self.interval = interval
        GPIO.setup(self.buzzer_pin, GPIO.OUT)

    def output_number(self, number):
        # NOTE(TF): hack the first pitch, because the buzzer is stupid
        self._buzz(self.pitch - 300, self.pitch_duration)
        time.sleep(self.interval)
        for i in range(number):
            self._buzz(self.pitch, self.pitch_duration)
            time.sleep(self.interval)

    def _buzz(self, pitch, duration):
        if pitch == 0:
            time.sleep(duration)
            return

        # in physics, the period (sec/cyc) is the inverse of the frequency (cyc/sec)
        period = 1.0 / pitch
        # calculate the time for half of the wave
        delay = period / 2
        # the number of waves to produce is the duration times the frequency
        cycles = int(duration * pitch)

        for i in range(cycles):  # start a loop from 0 to the variable “cycles” calculated above
            GPIO.output(self.buzzer_pin, True)
            time.sleep(delay)
            GPIO.output(self.buzzer_pin, False)
            time.sleep(delay)
