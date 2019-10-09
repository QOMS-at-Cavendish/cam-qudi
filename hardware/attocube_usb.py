# -*- coding: utf-8 -*-

"""
ANC-300 or ANC-350 hardware interface using serial interface provided
by Attocube USB drivers.

Uses interface defined in stepper_interface.py

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
from interface.stepper_interface import StepperInterface
import numpy as np


class AttoCubeStepper(Base,StepperInterface):
    """
    Attocube stepper class
    Config parameters:
    - port: string, COM port provided by attocube
    - voltage_range: dict, Voltage range [min,max] for each axis
    - frequency_range: dict, Frequency range [min,max] for each axis
    Example config:

    attocube:
        module.Class: 'attocube_usb.AttoCubeStepper'
        port: 'COM4'
        axes: {'x':1,'y':2,'z':3}
        step_voltage_range: {'x':[0,60], 'y':[0,60], 'z':[0,60]}
        frequency_range: {'x':[0,1000], 'y':[0,1000], 'z':[0,1000]}
    """

    _modtype = 'AttoCubeStepper'
    _modclass = 'hardware'

    _port = ConfigOption('port', missing='error')
    _voltage_range = ConfigOption('step_voltage_range', [0,60], missing='warn')
    _frequency_range = ConfigOption('frequency_range', [0,10000], missing='warn')
    _axes = ConfigOption('axes', {}, missing='error')

    def on_activate(self):
        """Module start-up"""

        # Read config
        config = self.getConfiguration()
        self._port = config['port']
        self._vrange = config['step_voltage_range']
        self._frange = config['frequency_range']
        self._axes = config['axes']

        # Set default step voltage and frequency for missing axes config
        default_vrange = [0,60]
        default_frange = [0,10000]
        
        for axis in self._axes.keys():
            if not axis in self._vrange:
                self.log.warn("No step voltage range given for axis {}. Using default {}.".format(axis,default_vrange))
                self._vrange[axis] = default_vrange
            
            if not axis in self._frange:
                self.log.warn("No frequency range given for axis {}. Using default {}.".format(axis,default_frange))
                self._frange[axis] = default_frange
            
        # Connect serial port
        #self.connection = AttocubeComm(port=self._port)


    def on_deactivate(self):
        """Module shutdown"""
        pass

    def reset_hardware(self):
        self.log.info('Attocube reset not implemented')

    def set_step_amplitude(self,axis,voltage):
        """Set step amplitude for a particular axis
        @param str axis: axis identifier as defined in config file
        @param float voltage: step voltage
        """
        raise NotImplementedError

    def get_step_amplitude(self,axis,voltage):
        """Get step amplitude set for a particular axis
        @param str axis: axis identifier as defined in config file
        @param float voltage: step voltage
        """
        raise NotImplementedError

    def set_step_frequency(self,axis,frequency):
        """Get step amplitude set for a particular axis
        @param str axis: axis identifier as defined in config file
        @return float frequency: step frequency
        """
        raise NotImplementedError

    def get_step_frequency(self,axis):
        """Get step amplitude set for a particular axis
        @param str axis: axis identifier as defined in config file
        @return float frequency: step frequency
        """
        raise NotImplementedError

    def set_axis_mode(self,axis,mode):
        """Set axis mode

        @param str axis: axis identifier as defined in config file
        @param str mode: mode to be set
        """
        raise NotImplementedError
    
    def get_axis_mode(self,axis):
        """Get axis mode

        @param str axis: axis identifier as defined in config file
        @return str mode: mode to be set
        """
        raise NotImplementedError

    def get_stepper_axes(self):
        """ Find out how many axes the scanning device is using for confocal and their names.

        @return list(str): list of axis names

        Example:
          For 3D confocal microscopy in cartesian coordinates, ['x', 'y', 'z'] is a sensible value.
          For 2D, ['x', 'y'] would be typical.
          You could build a turntable microscope with ['r', 'phi', 'z'].
          Most callers of this function will only care about the number of axes, though.

          On error, return an empty list.
        """
        return self._axes.keys()

    def move_stepper(self):
        """Moves stepper either continuously or by a number of steps in a particular axis

        @param str axis: axis identifier as defined in config file
        @param str mode: Sets movement mode. 'step': Stepping, 'cont': Continuous
        @param str direction: 'out': move out, 'in': move in.
        @param int steps: number of steps to be moved (in stepping mode)
        @return int:  error code (0: OK, -1:error)
        """
        raise NotImplementedError

    def stop_axis(self,axis):
        """Stops motion on specified axis

        @param str axis: can only be part of dictionary axes
        """
        raise NotImplementedError

    def stop_all(self):
        """Stops motion on all axes
        """
        raise NotImplementedError

    def get_amplitude_range(self):
        """Returns the current possible stepping voltage range of the stepping device for all axes
        @return dict: step voltage range of each axis, as set in config file
        """
        raise NotImplementedError

    def get_freq_range(self):
        """Returns the current possible frequency range of the stepping device for all axes
        @return dict: step frequency range of each axis, as set in config file
        """
        raise NotImplementedError
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
