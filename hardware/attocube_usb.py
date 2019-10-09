# -*- coding: utf-8 -*-

"""
ANC-300 or ANC-350 hardware interface using serial interface provided
by Attocube USB drivers.

Uses pyserial for communication.

John Jarman jcj27@cam.ac.uk

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import serial
import time




class AttocubeComm(serial.Serial):
    """
    Class for controlling attocube over serial connection.
    Extends pyserial.Serial
    """
    def __init__(self,port=None,timeout=0.5,*args,**kwargs):
        """Create serial interface object. Can be called with a port, in 
        which case it opens immediately."""
        serial.Serial.__init__(self,port,timeout=timeout, write_timeout=timeout,*args,**kwargs)

    def connect(self,port='COM4'):
        """Start serial connection"""
        self.setPort(port)
        self.open()

    def send_cmd(self, cmd):
        """Send command string
        @param cmd: String to send
        @return 0
        Throws SerialException if port is not working properly
        """
        # Encode command
        cmd_encoded = cmd.encode('ascii')+b"\r\n"

        # Reset buffers
        self.reset_output_buffer()
        self.reset_input_buffer()

        # Write command
        self.write(cmd_encoded)

        time.sleep(0.05)

        # Read-back:
        read_bytes = self.read(self.in_waiting)

        print(read_bytes)
        read_string = read_bytes.decode().split("\r\n")

        print(read_string[-2])
        return read_string
