# -*- coding: utf-8 -*-

"""
Dummy positioner interface.

Uses interface defined in positioner_interface.py

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
import functools

from core.module import Base
from core.configoption import ConfigOption
from interface.positioner_interface import PositionerInterface
from interface.positioner_interface import AxisConfigError, AxisError, PositionerError, PositionerNotReferenced, PositionerOutOfRange
import numpy as np

def check_axis(func):
    @functools.wraps(func)
    def check(self,axis,*args,**kwargs):
        if axis in self.axes:
            return func(self,axis,*args,**kwargs)
        else:
            raise AxisError('Axis {} is not defined in config file dictionary.'.format(axis))
    return check

class PositionerDummy(Base,PositionerInterface):
    """
    PositionerDummy dummy class.
    """

    _modtype = 'PositionerDummy'
    _modclass = 'hardware'

    def on_activate(self):
        """Module start-up"""
            
        self.position = {
            'x':0,
            'y':0,
            'z':0
        }

        self.axes = ['x','y','z']
        
    def on_deactivate(self):
        """Module shutdown"""
        pass

    def reset_hardware(self):
        """
        Close hardware connection.
        """
        pass

    def hw_info(self):
        return {'manufacturer':'dummy', 'model':'dummy'}
    
    @check_axis
    def set_position(self, axis, position, relative=False):
        """
        Set position of specified axis.
        """
        if relative:
            self.position[axis] += position
        else:
            self.position[axis] = position

    @check_axis
    def get_position(self, axis):
        """
        Get position of specified axis.
        """
        return self.position[axis]

    @check_axis
    def reference_axis(self, axis):
        """
        Reference axis.
        """
        pass

    @check_axis
    def get_axis_status(self, axis, status=None):
        """
        Get status of specified axis.
        @param str axis: Axis to retrieve
        @param str status: Status variable or flag to retrieve (Optional)
        @param str return: Requested variable
        @param str dict: All available variables (if no status specified)
        """
        if status == None:
            return self._get_all_status(axis)

        elif status == 'is_moving':
            # Get moving status
            return False
        elif status == 'on_target':
            # Get whether stage is on closed-loop target
            return True

        else:
            raise AxisConfigError('Status variable {} unsupported'.format(status))

    @check_axis
    def get_axis_config(self, axis, config_option=None):
        """
        Get configuration of specified axis.
        @param str axis: Axis to retrieve.
        @param str config_option: Config option to return (optional)
        @return: Specified config_option value.
        @return dict: All config_option values (if no config_option specified)
        """
        raise AxisConfigError('Config option {} unsupported'.format(config_option))

    @check_axis
    def set_axis_config(self, axis, **config):
        """
        Get configuration of specified axis.
        @param str axis: Axis to set
        @kwargs: Name-value pairs for configuration to set
        """
        pass

    @check_axis
    def get_axis_limits(self, axis):
        """
        Get limits for specified axis
        @param str axis: Query limits on this axis
        @return dict: Dict of limits
        """
        return {}

    def get_axes(self):
        """
        Return list of axes.
        @return list: Axes strings that can be passed to other methods.
        """
        return self.axes

    @check_axis
    def move_steps(self, axis, steps=1):
        """Moves stepper by a number of steps in a particular axis

        @param str axis: axis identifier as defined in config file
        @param int steps: number of steps to be moved. Sign indicates direction.
        """
        self.position[axis] += 0.005

    @check_axis
    def start_continuous_motion(self, axis, reverse=False):
        """ 
        Start continuous motion on the specified axis and direction.
        Continues until stopped by calling stop_axis or stop_all.

        @param str axis: Axis to move
        @param bool reverse: Move backwards (in negative direction)
        """
        # Start a move to axis limit
        self.position[axis] += 0.05

    @check_axis
    def stop_axis(self, axis):
        """Stops motion on specified axis

        @param str axis: can only be part of dictionary axes
        """
        pass

    def stop_all(self):
        """Stops motion on all axes
        """
        pass
