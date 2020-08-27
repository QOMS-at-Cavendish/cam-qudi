# -*- coding: utf-8 -*-
"""
Extended spectrometer interface.

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


class SpectrometerInterfaceEx(metaclass=InterfaceMetaclass):
    """Extended spectrometer interface
    """
    @abstract_interface_method
    def acquire_spectrum(self):
        """Acquire and return a spectrum

        Block until spectrum has been acquired.

        @return np.ndarray((2, N)): Axis 0: wavelength, Axis 1: intensity
            N is spectrometer-dependent.
        """
        pass

    @abstract_interface_method
    def set_parameter(self, parameter, value):
        """Set a parameter on the spectrometer.

        Block until parameter has been successfully set.

        @param str parameter: Parameter to set. This can be one of:
            - exposure_time (in seconds)
            - center_wavelength (in nanometres)
            - Other hardware-dependent values if supported.
        @param value: Value to set

        @raises: KeyError if the parameter is unsupported.
        """
        pass

    @abstract_interface_method
    def get_parameter(self, parameter):
        """Get a parameter from the spectrometer.

        @param str parameter: Parameter to get. This can be one of:
            - exposure_time (in seconds)
            - center_wavelength (in nanometres)
            - detector_temp (in degrees Celsius)
            - Other hardware-dependent values if supported.
        
        @return: Value of requested parameter

        @raises: KeyError if the parameter is unsupported.
        """
        pass

    @abstract_interface_method
    def get_supported_params(self):
        """Get all supported parameters.

        Returns a dictionary with the supported parameters as keys.
        Values in the dict are also dicts, with the following keys:
            - get: If the parameter can be read from the spectrometer (bool)
            - set: If the parameter can be set on the spectrometer (bool)
            - max: Maximum value
            - min: Minimum value

        @return dict params: Dict of all parameters.
            Has the format 
            {'<param_name>':{
                {'get':True,
                 'set':True,
                 'max':<max_val>,
                 'min':<min_val>}
            }}
        """
        pass