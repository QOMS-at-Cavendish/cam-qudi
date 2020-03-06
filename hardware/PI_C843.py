# -*- coding: utf-8 -*-

"""
PI C843 stage interface.

Implements interface defined in positioner_interface.py

Uses pipython library from PI for communication.

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

# PI's python library.
import pipython
import pipython.pitools

# Decorator to check if axis is correct
def check_axis(func):
    @functools.wraps(func)
    def check(self,axis,*args,**kwargs):
        if axis in self.axes:
            return func(self,axis,*args,**kwargs)
        else:
            raise AxisError('Axis {} is not defined in config file dictionary.'.format(axis))
    return check

class PI_C843(Base,PositionerInterface):
    """
    PI C843
    Config parameters:
    - port: int, PCIe card number
    - axes: dict, map axis names to physical axes
    Example config:

    pi_c843:
        module.Class: 'PI_C843.PI_C843'
        port: 1
        axes: {'x':1,'y':2,'z':3}
    """
    # pylint: disable=unsubscriptable-object

    port = ConfigOption('port', missing='error')
    axes = ConfigOption('axes', {}, missing='error')

    def on_activate(self):
        """Module start-up"""
        # Connect to PI controller.
        self.pidevice = pipython.GCSDevice('C-843')
        self.pidevice.ConnectPciBoard(board=self.port)
        self.log.debug('Connected: {}'.format(self.pidevice.qIDN().strip()))

        # Set up axes. TODO: Should be config option.
        self.pidevice.CST('1', 'M-405.DG')
        self.pidevice.CST('2', 'M-451.1DG')
        self.pidevice.CST('3', 'M-405.DG')

        self.pidevice.INI()

        # Enable servo on each axis.
        self.pidevice.SVO('1', 1)
        self.pidevice.SVO('2', 1)
        self.pidevice.SVO('3', 1)  

    def on_deactivate(self):
        """Module shutdown"""
        pass

    def reset_hardware(self):
        """
        Close hardware connection.
        """
        pass

    def hw_info(self):
        return {'manufacturer':'PI', 'model':'C843'}
        
    @check_axis
    def set_position(self, axis, position, relative=False):
        """
        Set position of specified axis.
        """
        try:
            if relative:
                self.pidevice.MVR(self.axes[axis], position*1e3)
            else:
                self.pidevice.MOV(self.axes[axis], position*1e3)
        except pipython.GCSError as err:
            if err.val == 5:
                raise PositionerNotReferenced(err)
            else:
                raise PositionerError(err)

    @check_axis
    def get_position(self, axis):
        """
        Get position of specified axis.
        """
        try:
            position = self.pidevice.qPOS(self.axes[axis])[self.axes[axis]]
            return position/1e3
        except pipython.GCSError as err:
            raise PositionerError(err)

    def reference_axis(self, axis=None):
        """
        References axis. If no axis specified, reference all axes.

        @param axis: str (optional) Axis to reference.
        """
        # pylint: disable=no-member
        if axis is None:
            self.pidevice.FRF(list(self.axes.values()))
        elif axis in self.axes.keys():
            self.pidevice.FRF(self.axes[axis])
        else:
            raise AxisError("Axis {} not found.".format(axis))

    @check_axis
    def get_axis_status(self, axis, status=None):
        """
        Get status of specified axis.
        @param str axis: Axis to retrieve
        @param str status: Status variable or flag to retrieve (Optional)
        @param str return: Requested variable
        @param str dict: All available variables (if no status specified)
        """
        try:
            if status == None:
                return self._get_all_status(axis)
    
            elif status == 'is_moving':
                # Get moving status
                return self.pidevice.IsMoving(self.axes[axis])[self.axes[axis]]
            elif status == 'on_target':
                # Get whether stage is on closed-loop target
                return self.pidevice.qONT(self.axes[axis])[self.axes[axis]]

        except pipython.GCSError as err:
            raise PositionerError(err)

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

        if config_option == None:
            return self._get_all_config(axis)
        
        elif config_option == 'velocity':
            # Get axis velocity
            return self.pidevice.qVEL(self.axes[axis])[self.axes[axis]]/1e3

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
    def set_axis_config(self, axis, **config):
        """
        Get configuration of specified axis.
        @param str axis: Axis to set
        @kwargs: Name-value pairs for configuration to set
        """
        for option, value in config.items():
            if option == 'velocity':
                # Set axis velocity
                self.pidevice.VEL(self.axes[axis], value*1e3)

    @check_axis
    def get_axis_limits(self, axis):
        """
        Get limits for specified axis
        @param str axis: Query limits on this axis
        @return dict: Dict of limits
        """
        pos_min = self.pidevice.qTMN(self.axes[axis])[self.axes[axis]]/1e3
        pos_max = self.pidevice.qTMX(self.axes[axis])[self.axes[axis]]/1e3

        return {'position':(pos_min, pos_max)}

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
        self.pidevice.MVR(self.axes[axis], 0.0005*steps)

    @check_axis
    def start_continuous_motion(self, axis, reverse=False):
        """ 
        Start continuous motion on the specified axis and direction.
        Continues until stopped by calling stop_axis or stop_all.

        @param str axis: Axis to move
        @param bool reverse: Move backwards (in negative direction)
        """
        # Start a move to axis limit
        if reverse:
            limit = self.pidevice.qTMN(self.axes[axis])[self.axes[axis]]
        else:
            limit = self.pidevice.qTMX(self.axes[axis])[self.axes[axis]]

        self.pidevice.MOV(self.axes[axis], limit)

    @check_axis
    def stop_axis(self, axis):
        """Stops motion on specified axis

        @param str axis: can only be part of dictionary axes
        """
        try:
            self.pidevice.HLT(self.axes[axis])
        except pipython.GCSError:
            # Always get a GCSError -10 when axis is stopped.
            pass

    def stop_all(self):
        """Stops motion on all axes
        """
        try:
            self.pidevice.STP()
        except pipython.GCSError:
            # Always get a GCSError -10 when axis is stopped.
            pass
