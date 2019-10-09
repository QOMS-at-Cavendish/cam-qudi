# Quick test for attocube comms

import attocube_usb
from serial import SerialException

with attocube_usb.AttocubeComm(port='') as comm:
    print(comm.send_cmd('stepu 1 5'))
