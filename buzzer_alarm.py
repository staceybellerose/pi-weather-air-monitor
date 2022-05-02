import asyncio

import board
import pwmio

# change this if the buzzer has been wired to a different GPIO pin
BUZZER_GPIO = board.D14

COUNT = 8
PULSE = 0.5
FREQ_HI = 6000
FREQ_LO = 4000
CYCLE = 0x7fff

async def sound_the_alarm():
    """
    Coroutine to play a pulsing alarm sound on the piezo buzzer.
    """
    buzzer = pwmio.PWMOut(BUZZER_GPIO, duty_cycle=CYCLE, frequency=FREQ_HI)
    for i in range(COUNT):
        await asyncio.sleep(PULSE)
        buzzer.frequency = FREQ_LO
        await asyncio.sleep(PULSE)
        buzzer.frequency = FREQ_HI
    buzzer.deinit()
