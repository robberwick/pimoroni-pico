from pimoroni import ShiftRegister
from machine import Pin, I2C, RTC
from wakeup import get_shift_state, reset_shift_state
from micropython import const
import pcf85063a
import ntptime
import time

BLACK = const(0)
WHITE = const(1)

GREEN = const(2)
BLUE = const(3)
RED = const(4)
YELLOW = const(5)
ORANGE = const(6)
TAUPE = const(7)

SR_CLOCK = const(8)
SR_LATCH = const(9)
SR_OUT = const(10)

LED_A = const(11)
LED_B = const(12)
LED_C = const(13)
LED_D = const(14)
LED_E = const(15)

LED_BUSY = const(6)
LED_WIFI = const(7)

HOLD_VSYS_EN = const(2)

RTC_ALARM = const(5)
EXTERNAL_TRIGGER = const(6)
EINK_BUSY = const(7)

SHIFT_STATE = get_shift_state()

reset_shift_state()

i2c = I2C(0)
rtc = pcf85063a.PCF85063A(i2c)
i2c.writeto_mem(0x51, 0x00, b'\x00')  # ensure rtc is running (this should be default?)
rtc.enable_timer_interrupt(False)

vsys = Pin(HOLD_VSYS_EN)
vsys.on()


def woken_by_rtc():
    return bool(sr.read() & (1 << RTC_ALARM))


def woken_by_button():
    return bool(SHIFT_STATE & 0b00011111)


def pico_rtc_to_pcf():
    # Set the PCF85063A to the time stored by Pico W's RTC
    year, month, day, dow, hour, minute, second, _ = RTC().datetime()
    rtc.datetime((year, month, day, hour, minute, second, dow))


def pcf_to_pico_rtc():
    # Set Pico W's RTC to the time stored by the PCF85063A
    t = rtc.datetime()
    # BUG ERRNO 22, EINVAL, when date read from RTC is invalid for the Pico's RTC.
    try:
        RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
        return True
    except OSError:
        return False


def sleep_for(minutes):
    year, month, day, hour, minute, second, dow = rtc.datetime()

    # if the time is very close to the end of the minute, advance to the next minute
    # this aims to fix the edge case where the board goes to sleep right as the RTC triggers, thus never waking up
    if second >= 55:
        minute += 1

    minute += minutes

    while minute >= 60:
        minute -= 60
        hour += 1

    if hour >= 24:
        hour -= 24

    rtc.clear_alarm_flag()
    rtc.set_alarm(0, minute, hour)
    rtc.enable_alarm_interrupt(True)

    vsys.off()


def turn_off():
    vsys.off()


def set_time():
    # Set both Pico W's RTC and PCF85063A to NTP time
    ntptime.settime()
    pico_rtc_to_pcf()


class Button:
    def __init__(self, sr, idx, led, debounce=50):
        self.sr = sr
        self.startup_state = bool(SHIFT_STATE & (1 << idx))
        self.led = Pin(led, Pin.OUT)  # LEDs are just regular IOs
        self.led.off()
        self._idx = idx
        self._debounce_time = debounce
        self._changed = time.ticks_ms()
        self._last_value = None

    def led_on(self):
        self.led.on()

    def led_off(self):
        self.led.off()

    def read(self):
        if self.startup_state:
            self.startup_state = False
            return True

        value = self.raw()
        if value != self._last_value and time.ticks_ms() - self._changed > self._debounce_time:
            self._last_value = value
            self._changed = time.ticks_ms()
            return value
        return False

    def raw(self):
        if self.startup_state:
            self.startup_state = False
            return True
        return self.sr[self._idx] == 1

    @property
    def is_pressed(self):
        return self.raw()


sr = ShiftRegister(SR_CLOCK, SR_LATCH, SR_OUT)

button_a = Button(sr, 7, LED_A)
button_b = Button(sr, 6, LED_B)
button_c = Button(sr, 5, LED_C)
button_d = Button(sr, 4, LED_D)
button_e = Button(sr, 3, LED_E)

led_busy = Pin(LED_BUSY, Pin.OUT)
led_wifi = Pin(LED_WIFI, Pin.OUT)
