# -*- coding: utf-8 -*-
"""
Acquire a spectrum using Winspec over the network using the winspec package
(github.com/johnjarman/winspec-server)

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

from core.module import Base
from core.configoption import ConfigOption
from interface.spectrometer_interface import SpectrometerInterface
from interface.spectrometer_interface_ex import SpectrometerInterfaceEx
import numpy as np
import winspec

class WinspecRemote(Base, SpectrometerInterface, SpectrometerInterfaceEx):
    """This module interfaces with a remote Winspec spectrometer using the 
    winspec package.

    Demo config:

    spectrometer:
        module.Class: 'spectrometer.winspec_remote_spectrometer.WinspecRemote'
        remote_host: 'ws://<ip-address>:<port>
    """

    # Config options
    remote_host = ConfigOption('remote_host', missing='error')
    exposure_limits = ConfigOption('exposure_limits', default=[1e-6, 1e3])
    wavelength_limits = ConfigOption('wavelength_limits', default=[5e-7, 2e-6])

    def on_activate(self):
        # Check configured parameters
        #pylint: disable=unsubscriptable-object
        if self.exposure_limits[0] < 0:
            raise ValueError('Lower exposure limit cannot be negative')

        if self.wavelength_limits[0] < 0:
            raise ValueError('Lower wavelength limit cannot be negative')

        if self.exposure_limits[0] >= self.exposure_limits[1]:
            raise ValueError('Lower exposure limit cannot be higher than upper limit')

        if self.wavelength_limits[0] >= self.wavelength_limits[1]:
            raise ValueError('Lower wavelength limit cannot be higher than upper limit')
        
        # Dict of supported parameters and limits
        self.supported_params = {
            'exposure_time':{
                'set':True,
                'get':True,
                'min':self.exposure_limits[0],
                'max':self.exposure_limits[1]
            },
            'center_wavelength':{
                'set':True,
                'get':True,
                'min':self.wavelength_limits[0],
                'max':self.wavelength_limits[1]
            },
            'detector_temp':{
                'set':False,
                'get':True,
                'min':-1000,
                'max':1000
            }
        }

        # Mapping between winspec and Qudi param names
        self.param_names = {
            'exposure_time':'exposure_time',
            'center_wavelength':'wavelength',
            'detector_temp':'detector_temp'
        }

        # Correction factors to convert from spectrometer to Qudi units
        self.param_factors = {
            'exposure_time': 1,
            'center_wavelength': 1e-9,
            'detector_temp': 1
        }

    def on_deactivate(self):
        pass

    #########################
    # SpectrometerInterfaceEx
    #########################

    def acquire_spectrum(self):
        """Acquire and return a spectrum

        Block until spectrum has been acquired.

        @return np.ndarray((2, N)): Axis 0: wavelength (m), Axis 1: intensity (cts)
            N is spectrometer-dependent.
        """
        spect = self.recordSpectrum()
        spect[0, :] = spect[0, :] * 1e-9
        return spect
    
    def set_parameter(self, parameter, value):
        """Set a parameter on the spectrometer.

        Block until parameter has been successfully set.

        @param str parameter: Parameter to set. This can be one of:
            - exposure_time (in seconds)
            - center_wavelength (in metres)
        @param value: Value to set

        @raises: KeyError if the parameter is unsupported.
        """
        if self.supported_params[parameter]['set']:
            param = {self.param_names[parameter]:value/self.param_factors[parameter]}
            with winspec.WinspecClient(self.remote_host) as ws:
                ws.set_parameters(**param)
        else:
            raise KeyError('Set is not supported on {}'.format(parameter))

    def get_parameter(self, parameter):
        """Get a parameter from the spectrometer.

        @param str parameter: Parameter to get. This can be one of:
            - exposure_time (in seconds)
            - center_wavelength (in metres)
            - detector_temp (in degrees C)
        
        @return: Value of requested parameter

        @raises: KeyError if the parameter is unsupported.
        """
        if self.supported_params[parameter]['get']:
            with winspec.WinspecClient(self.remote_host) as ws:
                return ws.get_parameter(self.param_names[parameter])*self.param_factors[parameter]
        else:
            raise KeyError('Get is not supported on {}'.format(parameter))

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
        return self.supported_params
    
    
    #######################
    # SpectrometerInterface
    #######################

    def recordSpectrum(self):
        """Acquire a spectrum.

        @return 2D array: [wavelength[n], intensity[n]]
        """
        try:
            with winspec.WinspecClient(self.remote_host) as spectro:
                spect = spectro.acquire()
                return np.array(spect)
        except winspec.WinspecError as err:
            self.log.error(str(err))
            return np.zeros((2, 10))

    def getExposure(self):
        """Get exposure time.

        @return float: Exposure time in seconds.
        """
        try:
            with winspec.WinspecClient(self.remote_host) as spectro:
                return spectro.get_parameter('exposure_time')
        except winspec.WinspecError as err:
            self.log.error(str(err))
            return -1

    def setExposure(self, exposureTime):
        """Set exposure time.

        @param float exposureTime: Exposure time in seconds.
        """
        try:
            with winspec.WinspecClient(self.remote_host) as spectro:
                spectro.set_parameters(exposure_time=exposureTime)
        except winspec.WinspecError as err:
            self.log.error(str(err))
            return -1