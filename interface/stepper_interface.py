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

import abc
from core.interface import abstract_interface_method
from core.meta import InterfaceMetaclass

# Custom StepperError exception for general hardware failures
class StepperError(Exception):
    pass

class StepperInterface(metaclass=InterfaceMetaclass):
    """ This is the Interface class to define the controls for the confocal microscope using a 
    stepper hardware.
    """

    _modtype = 'ConfocalStepperInterface'
    _modclass = 'interface'

    @abc.abstractmethod
    def reset_hardware(self):
        """ Resets the hardware, so the connection is lost and other programs
            can access it.

        @return int: error code (0:OK, -1:error)
        """
        pass

    # ============================== Stepper Commands ====================================

    @abc.abstractmethod
    def set_step_amplitude(self, axis, voltage):
        """Sets the step voltage/amplitude for an axis

        @param str axis: the axis to be changed
        @param int voltage: the stepping amplitude/voltage the axis should be set to
        @return int: error code (0:OK, -1:error)
        """
        pass

    @abc.abstractmethod
    def get_step_amplitude(self, axis):
        """ Reads the amplitude of a step for a specific axis from the device

        @param str axis: the axis for which the step amplitude is to be read
        @return float: the step amplitude of the axis
        """
        pass

    @abc.abstractmethod
    def set_step_freq(self, axis, freq):
        """Sets the step frequency for an axis

        @param str axis: the axis to be changed
        @param int freq: the stepping frequency the axis should be set to
        @return int: error code (0:OK, -1:error)
        """
        pass

    @abc.abstractmethod
    def get_step_freq(self, axis):
        """ Reads the step frequency for a specific axis from the device

        @param str axis: the axis for which the frequency is to be read
        @return float: the step amplitude of the axis
        """
        pass

    @abc.abstractmethod
    def set_axis_mode(self, axis, mode):
        """Change axis mode

        @param str axis: axis to be changed, can only be part of dictionary axes
        @param str mode: mode to be set (hardware-dependent)
        @return int: error code (0: OK, -1:error)
        """
        pass

    @abc.abstractmethod
    def get_axis_mode(self, axis):
        """ Checks the mode for a specific axis

        @param str axis: the axis for which the frequency is to be checked
        @return float: the mode of the axis, -1 for error
        """
        pass

    @abc.abstractmethod
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
        pass

    @abc.abstractmethod
    def move_stepper(self, axis, mode='step', reverse=False, steps=1):
        """Moves stepper either continuously or by a number of steps in a particular axis

        @param str axis: axis to be moved, can only be part of dictionary axes
        @param str mode: Sets movement mode. 'step': Stepping, 'cont': Continuous
        @param str direction: 'out': move out, 'in': move in.
        @param int steps: number of steps to be moved (in stepping mode)
        @return int:  error code (0: OK, -1:error)
        """
        pass

    @abc.abstractmethod
    def stop_axis(self, axis):
        """Stops motion on specified axis

        @param str axis: can only be part of dictionary axes
        """
        pass

    @abc.abstractmethod
    def stop_all(self):
        """Stops motion on all axes
        """
        pass

    @abc.abstractmethod
    def get_amplitude_range(self):
        """Returns the current possible stepping voltage range of the stepping device for all axes
        @return dict: step voltage range of each axis, as set in config file
        """
        pass

    @abc.abstractmethod
    def get_freq_range(self):
        """Returns the current possible frequency range of the stepping device for all axes
        @return dict: step frequency range of each axis, as set in config file
        """
        pass
