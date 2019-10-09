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

from core.module import Base
from core.configoption import ConfigOption
from interface.confocal_stepper_interface import ConfocalStepperInterface
import numpy as np


class AttoCubeStepper(Base, ConfocalStepperInterface):
    """
    Attocube stepper class
    Example config:

    attocube:
        module.Class: 'attocube_usb.AttoCubeStepper'
        port:'COM4'
        voltage_range_stepper:[0,60]
        z_axis_channel:3
    """

    _modtype = 'AttoCubeStepper'
    _modclass = 'hardware'

    _port = ConfigOption('port', missing='error')
    _voltage_range_stepper = ConfigOption('voltage_range_stepper', [0,60], missing='warn')
    _z_axis_channel = ConfigOption('z_axis_channel', missing='error')

    def on_activate(self):
        """Module start-up"""

        config = self.getConfiguration()
        self._port = config['port']
        self._vrange = config['voltage_range_stepper']
        self._zchannel = config['z_axis_channel']

        # Test config read
        self.log.info("port: {} vrange: {} zchannel: {}".format(self._port,self._vrange,self._zchannel))

        # Connect serial port
        self.connection = AttocubeComm(port=self._port)


    def on_deactivate(self):
        """Module shutdown"""
        pass


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

        # Read-back:
        read_string = []
        for byte in self.read(): 
            if byte != b'>':
                read_bytes.append(byte)
            else:
                break
        
        read_string = read_bytes.decode().split("\r\n")

        return read_string
