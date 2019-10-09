# Quick test for attocube comms

import attocube_usb
from serial import SerialException

with attocube_usb.AttocubeComm(port='COM3') as comm:
    print(comm.send_cmd('stepd 1 5'))
