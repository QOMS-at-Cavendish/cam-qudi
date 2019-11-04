# -*- coding: utf-8 -*-

"""
ANC-300 hardware interface using serial interface provided
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
from interface.stepper_interface import StepperError, StepperOutOfRange, AxisError, AxisConfigError
import numpy as np

# Decorator to check if axis is correct
def check_axis(func):
    @functools.wraps(func)
    def check(self,axis,*args,**kwargs):
        if axis in self.axes:
            return func(self,axis,*args,**kwargs)
        else:
            raise AxisError('Axis {} is not defined in config file dictionary.'.format(axis))
    return check

# Decorator to check serial connection & do serial exception handling
# Raises a generic StepperError instead of SerialError for hardware independence
def check_connected(func):
    @functools.wraps(func)
    def check(self,*args,**kwargs):
        try:
            if not self.connection.is_open:
                self.connection.connect(self.port)
            return func(self,*args,**kwargs)
        except serial.SerialTimeoutException:
            msg = "SerialTimeoutException while communicating on {}".format(self.port)
            raise StepperError(msg)
        except serial.SerialException:
            msg = "SerialException while communicating on {}".format(self.port)
            raise StepperError(msg)
    return check

class AttoCubeStepper(Base,StepperInterface):
    """
    Attocube ANC-300 stepper class
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
        self._config_option_list = ['frequency', 'step-voltage', 'mode']

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
        """
        Close hardware connection.
        """
        if self.connection.is_open:
            self.connection.reset_input_buffer()
            self.connection.reset_output_buffer()
            self.connection.close()

    def set_position(self, axis, position, relative=False):
        """
        No position feedback on ANC-300. Raise AxisConfigError.
        """
        raise AxisConfigError('No position feedback on ANC-300')

    def get_position(self, axis):
        """
        No position feedback on ANC-300. Raise AxisConfigError.
        """
        raise AxisConfigError('No position feedback on ANC-300')

    @check_axis
    def get_axis_status(self, axis, status=None):
        """
        No axis status information available on ANC-300.
        """
        raise AxisConfigError('No axis status info available on ANC-300.')

    @check_axis
    @check_connected
    def get_axis_config(self, axis, config_option=None):
        """
        Get configuration of specified axis.
        @param str axis: Axis to retrieve.
        @param str config_option: Config option to return (optional)
        @return: Specified config_option value.
        @return dict: All config_option values (if no config_option specified)

        config_option is one of:
        'frequency'
        'step-voltage'
        'mode'.
        """
        # This relies on a particular form of return value, so is fragile 
        # to Attocube controller changes. There is also a bug in the ANC-300
        # return value for frequencies specifically, which may be fixed
        # in newer firmware.

        if config_option == None:
            return self._get_all_config(axis)

        elif config_option == 'step-voltage':
            cmd = "getv {}".format(self.axes[axis])
            return_str = self.connection.send_cmd(cmd)
            return return_str[-3].split(' ')[-2]
        
        elif config_option == 'frequency':
            cmd = "getf {}".format(self.axes[axis])
            return_str = self.connection.send_cmd(cmd)
            return return_str[-2].split(' ')[-2]

        elif config_option == 'mode':
            cmd = "getm {}".format(self.axes[axis])
            return_str = self.connection.send_cmd(cmd)
            return return_str[-3].split(' ')[-1]

        else:
            raise AxisConfigError('Config option {} unsupported'.format(config_option))

    def _get_all_config(self, axis):
        """
        Get all config options and return dict.

        @param axis: Axis to get config options from.
        """
        options_dict = {}

        for option in self._config_option_list:
            options_dict[option] = self.get_axis_config(axis, option)
        
        return options_dict


    @check_axis
    @check_connected
    def set_axis_config(self, axis, config):
        """
        Get configuration of specified axis.
        @param str axis: Axis to set
        @param dict config: Configuration to set

        Config dict keys can be:
        'step-voltage'
        'frequency'
        'mode'
        """
        for config_option, value in config.items():
            if config_option == 'step-voltage':
                # Check voltage in range
                if (float(value) < min(self.vrange[axis])
                   or float(value) > max(self.vrange[axis])):
                    raise StepperOutOfRange('Voltage out of range')

                # Construct command
                cmd = "setv {} {}".format(self.axes[axis], value)
                self.connection.send_cmd(cmd)
            
            elif config_option == 'frequency':
                # Check frequency in range
                if (float(value) < min(self.frange[axis])
                   or float(value) > max(self.frange[axis])):
                    err_msg = ("Could not set frequency for axis {}."
                               "Frequency {} outside configured range {}")
                    raise StepperOutOfRange(err_msg.format(axis,value,self.vrange[axis]))
                
                # Construct command
                cmd = "setf {} {}" .format(self.axes[axis],value)
                self.connection.send_cmd(cmd)

            elif config_option == 'mode':
                # Check mode is one of the supported ones
                if value in self.mode_list:
                    cmd = "setm {} {}".format(self.axes[axis],value)
                    self.connection.send_cmd(cmd)
                else:
                    err_msg = "Could not set mode {} on axis {}. Mode should be one of {}."
                    raise StepperOutOfRange(err_msg.format(value,axis,self.mode_list))

    @check_axis
    def get_axis_limits(self, axis):
        """
        Get limits for specified axis
        @param str axis: Query limits on this axis
        @return dict: Dict of limits
        """
        limits_dict = {
            'step-voltage':self.vrange[axis],
            'frequency':self.frange[axis]
            }

        return limits_dict

    def get_axes(self):
        """
        Return list of axes.
        @return list: Axes strings that can be passed to other methods.
        """
        return self.axes

    @check_axis
    @check_connected
    def move_steps(self, axis, steps=1):
        """Moves stepper by a number of steps in a particular axis

        @param str axis: axis identifier as defined in config file
        @param int steps: number of steps to be moved. Sign indicates direction.
        """
        if steps > 0:
            cmd = "stepu "
        elif steps < 0:
            cmd = "stepd "

        cmd += "{} ".format(self.axes[axis])

        if steps != 0:
            cmd += str(abs(int(steps)))
        
        self.connection.send_cmd(cmd)

    @check_axis
    @check_connected
    def start_continuous_motion(self, axis, reverse=False):
        """ 
        Start continuous motion on the specified axis and direction.
        Continues until stopped by calling stop_axis or stop_all.

        @param str axis: Axis to move
        @param bool reverse: Move backwards (in negative direction)
        """
        if reverse:
            cmd = "stepd "
        else:
            cmd = "stepu "
        
        cmd += "{} c".format(self.axes[axis])

        self.connection.send_cmd(cmd)

    @check_axis
    @check_connected
    def stop_axis(self, axis):
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
        # Encode command and ensure it ends with CRLF
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
