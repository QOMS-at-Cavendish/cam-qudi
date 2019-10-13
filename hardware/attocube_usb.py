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

import functools

from core.module import Base
from core.configoption import ConfigOption
from interface.stepper_interface import StepperInterface
from interface.stepper_interface import StepperError
import numpy as np

# Decorator to check if axis is correct
def check_axis(func):
    @functools.wraps(func)
    def check(self,axis,*args,**kwargs):
        if axis in self.axes:
            func(self,axis,*args,**kwargs)
        else:
            msg = 'Axis {} is not defined in config file dictionary.'.format(axis)
            self.log.error(msg)
            raise KeyError(msg)
    return check

# Decorator to check serial connection & do serial exception handling
# Raises a generic StepperError instead of SerialError for hardware independence
def check_connected(func):
    @functools.wraps(func)
    def check(self,*args,**kwargs):
        try:
            if not self.connection.is_open:
                self.connection.connect(self.port)
            func(self,*args,**kwargs)
        except serial.SerialTimeoutException:
            msg = "SerialTimeoutException while communicating on {}".format(self.port)
            self.log.error(msg)
            raise StepperError(msg)
        except serial.SerialException:
            msg = "SerialException while communicating on {}".format(self.port)
            self.log.error(msg)
            raise StepperError(msg)
    return check

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
    _voltage_range = ConfigOption('step_voltage_range', {})
    _frequency_range = ConfigOption('frequency_range', {})
    _axes = ConfigOption('axes', {}, missing='error')

    def on_activate(self):
        """Module start-up"""
        # Currently supported modes of Attocube: gnd, stp
        self.mode_list = ['gnd','stp']

        # Read config
        config = self.getConfiguration()
        self.port = config['port']
        self.vrange = config['step_voltage_range']
        self.frange = config['frequency_range']
        self.axes = config['axes']

        # Set conservative default step voltage and frequency for missing axes config
        default_vrange = [0,40]
        default_frange = [0,1000]
        
        for axis in self.axes.keys():
            if not axis in self.vrange:
                self.log.warn("No step voltage range given for axis {}. Using default {}.".format(axis,default_vrange))
                self.vrange[axis] = default_vrange
            
            if not axis in self.frange:
                self.log.warn("No frequency range given for axis {}. Using default {}.".format(axis,default_frange))
                self.frange[axis] = default_frange
            
        # Create serial port
        self.connection = AttocubeComm()

        # Note that port connection is handled in check_connection decorator
        # (see top of file) - this should decorate any function that needs
        # a serial connection to the Attocube.


    def on_deactivate(self):
        """Module shutdown"""
        self.reset_hardware()

    def reset_hardware(self):
        if self.connection.is_open:
            self.connection.reset_input_buffer()
            self.connection.reset_output_buffer()
            self.connection.close()

    @check_axis
    @check_connected
    def set_step_amplitude(self,axis,voltage):
        """Set step amplitude for a particular axis
        @param str axis: axis identifier as defined in config file
        @param float voltage: step voltage
        """
        # Check voltage in range
        if float(voltage) < min(self.vrange[axis]) or float(voltage) > max(self.vrange[axis]):
            self.log.warn("Could not set voltage for axis {}. Voltage {} outside configured range {}".format(axis,voltage,self.vrange[axis]))
            return
        
        # Construct command
        cmd = "setv {} {}".format(self.axes[axis], voltage)
        self.connection.send_cmd(cmd)

    @check_axis
    @check_connected
    def get_step_amplitude(self,axis,voltage):
        """Get step amplitude set for a particular axis
        @param str axis: axis identifier as defined in config file
        @param float voltage: step voltage
        """
        raise NotImplementedError

    @check_axis
    @check_connected
    def set_step_freq(self,axis,frequency):
        """Get step amplitude set for a particular axis
        @param str axis: axis identifier as defined in config file
        @return float frequency: step frequency
        """
        # Check frequency in range
        if float(frequency) < min(self.frange[axis]) or float(frequency) > max(self.frange[axis]):
            self.log.warn("Could not set frequency for axis {}. Frequency {} outside configured range {}".format(axis,frequency,self.vrange[axis]))
            return
        
        # Construct command
        cmd = "setf {} {}" .format(self.axes[axis],frequency)
        self.connection.send_cmd(cmd)

    @check_axis
    @check_connected
    def get_step_freq(self,axis):
        """Get step amplitude set for a particular axis
        @param str axis: axis identifier as defined in config file
        @return float frequency: step frequency
        """
        raise NotImplementedError

    @check_axis
    @check_connected
    def set_axis_mode(self,axis,mode):
        """Set axis mode

        @param str axis: axis identifier as defined in config file
        @param str mode: mode to be set (currently one of 'gnd' or 'stp')
        """
        # Check mode is one of the supported ones
        if mode in self.mode_list:
            cmd = "setm {} {}".format(self.axes[axis],mode)
            self.connection.send_cmd(cmd)
        else:
            self.log.warn("Could not set mode {} on axis {}. mode should be one of {}.".format(mode,axis,self.mode_list))
    
    @check_axis
    @check_connected
    def get_axis_mode(self,axis):
        """Get axis mode

        @param str axis: axis identifier as defined in config file
        @return str mode: mode to be set
        """
        raise NotImplementedError

    def get_stepper_axes(self):
        """ Get list of axis names.

        @return list(str): list of axis names

        Example:
          For 3D confocal microscopy in cartesian coordinates, ['x', 'y', 'z'] is a sensible value.
          For 2D, ['x', 'y'] would be typical.
          You could build a turntable microscope with ['r', 'phi', 'z'].
          Most callers of this function will only care about the number of axes, though.

          On error, return an empty list.
        """
        return self.axes.keys()

    @check_axis
    @check_connected
    def move_stepper(self,axis,mode,direction='out',steps=1):
        """Moves stepper either continuously or by a number of steps in a particular axis

        @param str axis: axis identifier as defined in config file
        @param str mode: Sets movement mode. 'step': Stepping, 'cont': Continuous
        @param str direction: 'out': move out, 'in': move in.
        @param int steps: number of steps to be moved (in stepping mode)
        """
        if direction == 'in':
            cmd = "stepu "
        elif direction == 'out':
            cmd = "stepd "
        else:
            self.log.error("Direction should be one of 'in' or 'out' when calling move_stepper")
            return

        cmd += "{} ".format(self.axes[axis])

        if mode == 'step':
            cmd += str(int(steps))
        elif mode == 'cont':
            cmd += "c"
        else:
            self.log.error("Mode should be one of 'step' or 'cont' when calling move_stepper")
            return
        
        self.connection.send_cmd(cmd)

    @check_axis
    @check_connected
    def stop_axis(self,axis):
        """Stops motion on specified axis

        @param str axis: can only be part of dictionary axes
        """
        cmd = "stop {}".format(self.axes[axis])
        self.connection.send_cmd(cmd)

    @check_connected
    def stop_all(self):
        """Stops motion on all axes
        """
        for axis in self.axes.items():
            cmd = "stop {}".format(axis[1])
            self.connection.send_cmd(cmd)

    @check_connected
    def get_amplitude_range(self):
        """Returns the current possible stepping voltage range of the stepping device for all axes
        @return dict: step voltage range of each axis, as set in config file
        """
        return self.vrange

    @check_connected
    def get_freq_range(self):
        """Returns the current possible frequency range of the stepping device for all axes
        @return dict: step frequency range of each axis, as set in config file
        """
        return self.frange

class AttocubeComm(serial.Serial):
    """
    Class for controlling attocube over serial connection.
    Extends pyserial.Serial
    """
    def __init__(self,port=None,timeout=0.5,*args,**kwargs):
        """Create serial interface object. Can be called with a port, in 
        which case it opens immediately."""
        serial.Serial.__init__(self,port,timeout=timeout, write_timeout=timeout,*args,**kwargs)

    def connect(self,port='COM3'):
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

        read_string = read_bytes.decode().split("\r\n")

        return read_string
