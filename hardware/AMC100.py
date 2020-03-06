# -*- coding: utf-8 -*-
"""
AMC-100 hardware module using TCP socket interface to controller.

Uses interface defined in positioner_interface.py

Authors
---
John Jarman jcj27@cam.ac.uk

This file is part of Qudi.

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

import socket
import json
import random
from interface.positioner_interface import PositionerInterface, \
    PositionerError, AxisError, AxisConfigError
from core.module import Base
from core.configoption import ConfigOption
from core.util.mutex import Mutex

import functools

def check_axis(func):
    """ Decorator that checks if axis is OK """
    @functools.wraps(func)
    def check(self, axis, *args, **kwargs):
        if axis in self.axes:
            return func(self, axis, *args, **kwargs)
        else:
            raise AxisError(
                'Axis {} is not defined in config file dictionary.'.format(axis))
    return check


class AMC100(Base, PositionerInterface):
    """
    Attocube AMC-100 stepper class
    Config parameters:
    - address: string, IP address of AMC-100 controller
    - voltage_range: dict, Voltage range [min,max] for each axis
    - frequency_range: dict, Frequency range [min,max] for each axis
    Example config:

    attocube:
        module.Class: 'ANC300_serial.AttoCubeStepper'
        address: '192.168.1.1'
        axes: {'x':0,'y':1,'z':2}
        step_voltage_range: {'x':[0,60], 'y':[0,60], 'z':[0,60]}
        frequency_range: {'x':[0,1000], 'y':[0,1000], 'z':[0,1000]}
    """
    # pylint: disable=unsubscriptable-object

    _ip_addr = ConfigOption('address', missing='error')
    _port = ConfigOption('port', default=9090)
    _timeout = ConfigOption('timeout', default=5)
    _axes = ConfigOption('axes', missing='error')
    _step_voltage_range = ConfigOption('step_voltage_range',
                                       default={
                                           'x': [0, 60],
                                           'y': [0, 60],
                                           'z': [0, 60]
                                       },
                                       missing='warn')

    _step_frequency_range = ConfigOption('step_frequency_range',
                                         default={
                                             'x': [20, 1000],
                                             'y': [20, 1000],
                                             'z': [20, 1000]
                                         },
                                         missing='warn')

    _hw_lock = Mutex()

    def __init__(self):
        super().__init__()
        self.connection = None
        self.config_options = (
            'step_voltage',
            'frequency',
            'offset_voltage',
            'output_enable',
            'enable_positioning',
            'target_range',
            'velocity'
        )

    def on_activate(self):
        """ Activates module.
        Tasks during activation:
        1. Establish connection
        2. Enable axes
        """
        if self.connection is not None:
            # Confirm connection is closed
            self.connection.close()
            self.connection = None

        self.connection = socket.create_connection((self._ip_addr, self._port),
                                                    timeout=self._timeout)

        self._enable_axes()

    def on_deactivate(self):
        """ Deactivates module.
        Tasks during deactivation:
        1. Disable axes
        2. Close connection.
        """
        self._disable_axes()

        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def get_axes(self):
        """
        Get configured axes.

        @return list: List of strings defining each axis.
        """
        # pylint: disable=no-member
        return self._axes.keys()

    def hw_info(self):
        """
        Get a dict containing hardware info.
        Keys:
        'manufacturer'
        'model'
        and optionally other (hardware-dependent) keys.
        """
        return {
            'manufacturer': 'Attocube',
            'model': 'AMC100'
        }

    def move_steps(self, axis, steps=1):
        """
        Moves a specified number of steps
        This will execute a movement that corresponds to the smallest
        possible stage motion.

        @param str axis: Axis to move
        @param int steps: Number of steps to move (sign indicates direction)
        """
        if steps > 0:
            direction = True
        elif steps < 0:
            direction = False
        else:
            # no-op if steps=0
            return
        self._send_message("com.attocube.amc.move.setNSteps",
                [self._axes[axis], direction, int(steps)])

    def start_continuous_motion(self, axis, reverse=False):
        """
        Start continuous motion on the specified axis and direction.
        Continues until stopped by calling stop_axis or stop_all.

        @param str axis: Axis to move
        @param bool reverse: Move backwards (in negative direction)
        """
        # Stop any closed-loop movement in progress
        self._send_request('com.attocube.amc.control.setControlMove',
                [self._axes[axis]], False)
        if reverse:
            self.request('com.attocube.amc.move.setControlContinousFwd',
                [self._axes[axis], False])
            self.request('com.attocube.amc.move.setControlContinousBkwd', 
                [self._axes[axis], True])
        else:
            self._send_request('com.attocube.amc.move.setControlContinousBkwd',
                [self._axes[axis], False])
            self._send_request('com.attocube.amc.move.setControlContinousFwd',
                [self._axes[axis], True])

    def set_position(self, axis, position, relative=False):
        """
        Move to specified position.
        Only available for closed-loop movements.

        @param str axis: Axis to move
        @param float position: Position in meters
        @param bool relative: If true, move relative to current position.

        Raise AxisConfigError if the axis does not support position
        feedback.
        """
        if relative:
            # Add position to current position if relative move needed
            current_pos = self.get_position(self._axes[axis])
            position += current_pos

        # Set command position
        self._send_request('com.attocube.amc.move.setControlTargetPosition',
                [self._axes[axis], round(position*1e9)])

        # Enable closed-loop positioning
        self._send_request('com.attocube.amc.control.setControlMove',
                [self._axes[axis], True])

    def get_position(self, axis):
        """
        Get current position.

        @param str axis: Get position from this axis

        Raise AxisConfigError if the axis does not support position
        feedback.
        """
        response = self._send_request('com.attocube.amc.move.getPosition',
                [self._axes[axis]])
        return response['result'][1]*1e-9

    def reference_axis(self, axis):
        """
        Move axis to reference position/home position (if available)
        Raise AxisConfigError if this axis does not have a reference/home position.
        @param str axis: Move this axis
        """
        pass

    @check_axis
    def get_axis_config(self, axis, config_option=None):
        """
        Retrieve configuration of specified axis
        @param str axis: Axis to retrieve
        @param str config_option: Configuration option to retrieve (optional)
        @return: Specified config_option value
        @return dict: All config_options available (if no config_option specified)

        See docstring of set_axis_config for standard config names.

        Raise AxisConfigError if a config_option is not implemented.
        """
        if config_option == "step_voltage":
            r = self._send_request(
                    "com.attocube.amc.control.getControlAmplitude",
                    [self._axes[axis]])
            return r["result"][1]/1e3

        elif config_option == "frequency":
            r = self._send_request(
                    "com.attocube.amc.control.getControlFrequency",
                    [self._axes[axis]])
            return r["result"][1]

        elif config_option == "offset_voltage":
            r = self._send_request(
                    "com.attocube.amc.control.getControlFixOutputVoltage",
                    [self._axes[axis]])
            return r["result"][1]/1e3

        elif config_option == "output_enable":
            r = self._send_request(
                    "com.attocube.amc.control.getControlOutput",
                    [self._axes[axis]])
            return r["result"][1]

        elif config_option == "enable_positioning":
            r = self._send_request(
                    "com.attocube.amc.control.getControlMove",
                    [self._axes[axis]])
            return r["result"][1]

        elif config_option == "target_range":
            r = self._send_request(
                    "com.attocube.amc.control.getControlTargetRange",
                    [self._axes[axis]])
            return r["result"][1]*1e-9

        elif config_option == "auto_update":
            r = self._send_request(
                    "com.attocube.amc.control.getControlReferenceAutoUpdate",
                    [self._axes[axis]])
            return r["result"][1]
        
        elif config_option == "auto_reset":
            r = self._send_request(
                    "com.attocube.amc.control.getControlAutoReset",
                    [self._axes[axis]])
            return r["result"][1]
        
        elif config_option is None:
            # Return all config options available
            all_config = {}
            for opt in self.config_options:
                all_config[opt] = self.get_axis_config(axis, opt)
            return all_config

        else:
            raise AxisConfigError(
                    "Unsupported config option {}".format(config_option))

    def set_axis_config(self, axis, **config):
        """
        Set configuration of specified axis
        @param str axis: Axis to set
        @kwargs config: Configuration to set

        The config kwargs can be an arbitrary number of hardware-specific
        configuration settings. For example, to set a particular frequency
        and step voltage on an axis, this might accept

        set_axis_config('x', frequency=100, step-voltage=20)

        Available options:
        'frequency': Step frequency (Hz) (float)
        'step_voltage': Step voltage (V) (float)
        'offset_voltage': Offset voltage (V) (float)
        'output_enable': Enable output (bool)
        'enable_positioning': Enable closed-loop positioning (bool)
        'target_range': Set position range for which 'on_target' status flag
                is set (m)
        'auto_update': Automatically update reference position when passed
        'auto_reset': Automatically reset position to zero when ref position is
                passed.
        'velocity': Set V/Hz to achieve a particular velocity in m/sec

        Ignore unimplemented configuration options.
        """
        for config_option in config.keys():
            if config_option == "step_voltage":
                if (config[config_option] > max(self._step_voltage_range) or
                        config[config_option] < min(self._step_voltage_range)):
                    raise AxisConfigError("Step voltage out of range")
                self._send_request(
                    "com.attocube.amc.control.setControlAmplitude",
                    [self._axes[axis], int(config[config_option]*1e3)])

            elif config_option == "frequency":
                if (config[config_option] > max(self._step_frequency_range) or
                        config[config_option] < min(self._step_frequency_range)):
                    raise AxisConfigError("Step frequency out of range")
                self._send_request(
                    "com.attocube.amc.control.setControlFrequency",
                    [self._axes[axis], int(config[config_option])])

            elif config_option == "offset_voltage":
                self._send_request(
                    "com.attocube.amc.control.setControlFixOutputVoltage",
                    [self._axes[axis], int(config[config_option]*1e3)])

            elif config_option == "output_enable":
                self._send_request(
                    "com.attocube.amc.control.setControlOutput",
                    [self._axes[axis], config[config_option]])

            elif config_option == "enable_positioning":
                self._send_request(
                    "com.attocube.amc.control.setControlMove",
                    [self._axes[axis], config[config_option]])

            elif config_option == "target_range":
                self._send_request(
                    "com.attocube.amc.control.setControlTargetRange",
                    [self._axes[axis], int(config[config_option]*1e9)])

            elif config_option == "auto_update":
                self._send_request(
                    "com.attocube.amc.control.setControlReferenceAutoUpdate",
                    [self._axes[axis], config[config_option]])
            
            elif config_option == "auto_reset":
                self._send_request(
                    "com.attocube.amc.control.setControlAutoReset",
                    [self._axes[axis], config[config_option]])

            elif config_option == "velocity":
                # Set V/Hz from a velocity in m/sec (approximate)
                v = config[config_option]*1e3
                if v < 0.02:
                    raise AxisConfigError("Velocity below supported range")
                if v >= 0.02 and v < 0.1:
                    # Set frequency between 200 and 2000 Hz, V = 25 V
                    freq = (((v - 0.02) / (0.1 - 0.02)) + 0.1) * 2000
                    self.set_axis_config(axis, step_voltage = 25)
                    self.set_axis_config(axis, frequency = freq)
                
                elif v >= 0.1 and v <= 1:
                    # Set voltage between 25 and 40 V, f = 2000 Hz
                    volt = (((v - 0.1)/(1 - 0.1)) + 1.66) * 15
                    self.set_axis_config(axis, step_voltage = volt)
                    self.set_axis_config(axis, frequency = 2000)

                else:
                    raise AxisConfigError("Velocity above supported range")

    def get_axis_status(self, axis, status=None):
        """
        Get status of specified axis.
        @param str axis: Get status from this axis
        @param str status: Get this status flag or variable (optional)
        @return status: Hardware-dependent status variable.
        @return dict status: Dict of all status variables (if no status specified)

        Available status variables:
        'moving' (bool)
        'end_of_travel' (bool)

        The returned dict should contain keys for each available status variable,
        with a boolean value for the state of status flags.

        Raise AxisConfigError if status is not implemented.
        """
        if status == "moving":
            r = self._send_request(
                    "com.attocube.amc.status.getStatusTargetRange",
                    [self._axes[axis]])
            return not r["result"][1]
        
        elif status == "end_of_travel":
            r = self._send_request(
                    "com.attocube.amc.status.getStatusEotFwd",
                    [self._axes[axis]])
            fwd_eot = r["result"][1]

            r = self._send_request(
                    "com.attocube.amc.status.getStatusEotBkwd",
                    [self._axes[axis]])
            
            rev_eot = r["result"][1]

            return fwd_eot or rev_eot

    def get_axis_limits(self, axis):
        """
        Get limits for specified axis.
        @param str axis: Get limits from this axis
        @return dict: Dict of all configured limits. Values are (min, max) tuples.

        Standardise on the following names for limits:
        'step_voltage'
        'frequency'
        'position'
        'velocity'

        If a limit is not known or implemented for a particular stage, its key
        will not appear in the returned dict.
        """
        return {
            "step_voltage":self._step_voltage_range,
            "step_frequency":self._step_frequency_range
        }

    def stop_axis(self, axis):
        """
        Stop all motion on specified axis.
        @param str axis: Axis to stop
        """
        # Disable closed-loop positioning
        self._send_request('com.attocube.amc.control.setControlMove',
                [self._axes[axis], True])
        
        # Disable continuous motion
        self.request('com.attocube.amc.move.setControlContinousFwd',
                [self._axes[axis], False])
        self.request('com.attocube.amc.move.setControlContinousBkwd', 
                [self._axes[axis], False])

    def stop_all(self):
        """
        Stop motion on all axes.
        """
        #pylint: disable=no-member
        for axis in self._axes.keys():
            self.stop_axis(axis)

    def _enable_axes(self):
        """ Enables output on configured axes
        """
        # pylint: disable=no-member
        for axis in self._axes.values():
            self._send_request('com.attocube.amc.control.setControlOutput',
                [axis, True])

    def _disable_axes(self):
        """ Disables output on configured axes
        """
        # pylint: disable=no-member
        for axis in self._axes.items():
            self._send_request('com.attocube.amc.control.setControlOutput',
                [axis, False])

    def _send_request(self, method, params=None, await_response=True):
        """ Sends message on the socket to the Attocube controller.
        By default, block and await a response from the Attocube.

        @param method (str): Command

        @param params (list): Parameters (optional)

        @param await_response (bool): Whether to wait for a response (optional,
        default True)

        @return dict containing parsed JSON data received as response, or
        None (if await_response is False).
        """
        response= None

        request= {
            'jsonrpc': '2.0',
            'method': method,
            'id': 0
        }
        if params is not None:
            request['params']= params
        with self._hw_lock:
            with self.connection.makefile("rw", newline='\r\n') as f:
                f.write(json.dumps(request))
                f.flush()
                if await_response:
                    response= json.loads(f.readline())
                    err= response['result'][0]
                    if err != 0:
                        # Translate error and raise exception
                        error_request= {
                            'jsonrpc': '2.0',
                            'method': 'com.attocube.system.errorNumberToString',
                            'params': [0, err]
                        }
                        f.write(json.dumps(error_request))
                        f.flush()
                        err_response= json.loads(f.readline())
                        raise PositionerError("Hardware error {}: {}".format(
                            err, err_response['result'][0]))

        return response
