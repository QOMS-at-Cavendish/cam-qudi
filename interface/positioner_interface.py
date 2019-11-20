# -*- coding: utf-8 -*-

"""
This module contains the Qudi interface file for a stepper (e.g. Attocube)

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

from core.interface import abstract_interface_method
from core.meta import InterfaceMetaclass

class PositionerError(Exception):
    """ 
    PositionerError exception for hardware errors.
    """
    pass

class PositionerOutOfRange(PositionerError):
    """ 
    PositionerOutOfRange exception if requested value is out of range.
    Raise when e.g. setting out-of-range config option or position.
    """
    pass

class PositionerNotReferenced(PositionerError):
    """
    PositionerNotReferenced exception if position is requested or set while
    stage is not referenced/homed.
    """
    pass

class AxisError(PositionerError):
    """ 
    AxisError exception if axis is not configured (e.g. if axis str is not
    found in the config file)
    """
    pass

class AxisConfigError(AxisError):
    """ 
    AxisConfigError exception if config option is passed but is not
    implemented in hardware.
    """
    pass

class PositionerInterface(metaclass=InterfaceMetaclass):
    """ Interface to positioner hardware.
    """

    _modtype = 'PositionerInterface'
    _modclass = 'interface'

    @abstract_interface_method
    def get_axes(self):
        """
        Get configured axes.

        @return list: List of strings defining each axis.
        """
        pass

    @abstract_interface_method
    def move_steps(self, axis, steps=1):
        """ 
        Move a specified number of steps
        Generally, this will be for open-loop movements.

        @param str axis: Axis to move
        @param int steps: Number of steps to move (sign indicates direction)
        """
        pass

    @abstract_interface_method
    def start_continuous_motion(self, axis, reverse=False):
        """ 
        Start continuous motion on the specified axis and direction.
        Continues until stopped by calling stop_axis or stop_all.

        @param str axis: Axis to move
        @param bool reverse: Move backwards (in negative direction)
        """
        pass

    @abstract_interface_method
    def set_position(self, axis, position, relative=False):
        """ 
        Move to specified position.
        Generally, this will be for closed-loop movements.
        
        @param str axis: Axis to move
        @param float position: Position in meters
        @param bool relative: If true, move relative to current position.

        Raise AxisConfigError if the axis does not support position
        feedback.
        """
        pass

    @abstract_interface_method
    def get_position(self, axis):
        """
        Get current position.

        @param str axis: Get position from this axis

        Raise AxisConfigError if the axis does not support position
        feedback.
        """
        pass

    @abstract_interface_method
    def reference_axis(self, axis):
        """
        Move axis to reference position/home position (if available)
        Raise AxisConfigError if this axis does not have a reference/home position.
        @param str axis: Move this axis
        """
        pass

    @abstract_interface_method
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

    @abstract_interface_method
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

        Raise AxisConfigError if the configuration option is not implemented.
        """
        pass

    @abstract_interface_method
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

    @abstract_interface_method
    def get_axis_limits(self, axis):
        """
        Get limits for specified axis.
        @param str axis: Get limits from this axis
        @return dict: Dict of all configured limits. Values are (min, max) tuples.

        Standardise on the following names for limits:
        'step_voltage'
        'frequency'
        'position'
        """
        pass

    @abstract_interface_method
    def stop_axis(self, axis):
        """
        Stop all motion on specified axis.
        @param str axis: Axis to stop
        """
        pass

    @abstract_interface_method
    def stop_all(self):
        """
        Stop motion on all axes.
        """
        pass