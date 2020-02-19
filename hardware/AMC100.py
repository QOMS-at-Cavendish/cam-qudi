# -*- coding: utf-8 -*-
"""
AMC-100 hardware module using TCP socket interface to controller.

Uses interface defined in positioner_interface.py

Authors
---
John Jarman jcj27@cam.ac.uk

Copyright Nu Quantum Ltd (2020).

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
from interface.positioner_interface import PositionerInterface, PositionerError
from core.module import Base
from core.configoption import ConfigOption


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
    ip_addr = ConfigOption('address', missing='error')
    port = ConfigOption('port', default=9090)
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

    def __init__(self):
        super().__init__()
        self.connection = None
    
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
        
        self.connection = socket.create_connection((self.ip_addr, self.port),
                                                    timeout=5)

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
        pass

    def start_continuous_motion(self, axis, reverse=False):
        """ 
        Start continuous motion on the specified axis and direction.
        Continues until stopped by calling stop_axis or stop_all.

        @param str axis: Axis to move
        @param bool reverse: Move backwards (in negative direction)
        """
        pass

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
        pass

    def get_position(self, axis):
        """
        Get current position.

        @param str axis: Get position from this axis

        Raise AxisConfigError if the axis does not support position
        feedback.
        """
        pass

    def reference_axis(self, axis):
        """
        Move axis to reference position/home position (if available)
        Raise AxisConfigError if this axis does not have a reference/home position.
        @param str axis: Move this axis
        """
        pass

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
        pass

    def set_axis_config(self, axis, **config):
        """
        Set configuration of specified axis
        @param str axis: Axis to set
        @kwargs config: Configuration to set

        The config kwargs can be an arbitrary number of hardware-specific
        configuration settings. For example, to set a particular frequency 
        and step voltage on an axis, this might accept 

        set_axis_config('x', frequency=100, step-voltage=20)

        Standardise on the following names for common config options:
        'frequency': Step frequency (float)
        'step_voltage': Step voltage (float)
        'offset_voltage': Offset voltage (float)
        'mode': Axis mode (string, e.g. 'stp', 'gnd', 'cap' for attocube)

        Ignore unimplemented configuration options.
        """
        pass

    def get_axis_status(self, axis, status=None):
        """
        Get status of specified axis.
        @param str axis: Get status from this axis
        @param str status: Get this status flag or variable (optional)
        @return status: Hardware-dependent status variable.
        @return dict status: Dict of all status variables (if no status specified)

        Standardise on the following names for common status variables:
        'moving' (bool)
        'end-of-travel' (bool)

        The returned dict should contain keys for each available status variable,
        with a boolean value for the state of status flags.

        Raise AxisConfigError if status is not implemented.
        """
        pass

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
        pass

    def stop_axis(self, axis):
        """
        Stop all motion on specified axis.
        @param str axis: Axis to stop
        """
        pass

    def stop_all(self):
        """
        Stop motion on all axes.
        """
        pass

    def _enable_axes(self):
        """ Enables output on configured axes
        """
        pass

    def _disable_axes(self):
        """ Disables output on configured axes
        """
        pass

    def _send_message(self, method, params=None, await_response=False):
        response = None

        request = {
            'jsonrpc': '2.0',
            'method': method,
            'id': 0
        }
        if params is not None:
            request['params'] = params
        with self.connection.makefile("rw", newline='\r\n') as f:
            f.write(json.dumps(request))
            if await_response:
                response = f.readline()

        return response
