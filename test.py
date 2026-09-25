from gpiozero import LED
from time import sleep

led = LED(17)  # BCM GPIO17 = physical pin 11

while True:
    led.on()
    sleep(1)
    led.off()
    sleep(1)