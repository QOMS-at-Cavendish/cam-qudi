# -*- coding: utf-8 -*-
"""
This module contains fake spectrometer.

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
from core.connector import Connector
from interface.spectrometer_interface import SpectrometerInterface
from interface.spectrometer_interface_ex import SpectrometerInterfaceEx

from time import strftime, localtime

import time
import numpy as np


class SpectrometerInterfaceDummy(Base,SpectrometerInterface,SpectrometerInterfaceEx):
    """ Dummy spectrometer module.

    Shows a silicon vacancy spectrum at liquid helium temperatures.

    Example config for copy-paste:

    spectrometer_dummy:
        module.Class: 'spectrometer.spectrometer_dummy.SpectrometerInterfaceDummy'
        fitlogic: 'fitlogic' # name of the fitlogic module, see default config

    """

    fitlogic = Connector(interface='FitLogic')

    def on_activate(self):
        """ Activate module.
        """
        self._fitLogic = self.fitlogic()
        self.exposure = 0.1
        self.wavelength = 5e-7

        # Dict of supported parameters and limits
        self.supported_params = {
            'exposure_time':{
                'set':True,
                'get':True,
                'min':0,
                'max':120
            },
            'center_wavelength':{
                'set':True,
                'get':True,
                'min':1e-9,
                'max':2e-6
            },
            'detector_temp':{
                'set':False,
                'get':True,
                'min':-1000,
                'max':1000
            }
        }

    def on_deactivate(self):
        """ Deactivate module.
        """
        pass

    #########################
    # SpectrometerInterfaceEx
    #########################

    def acquire_spectrum(self):
        return self.recordSpectrum()
    
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
            time.sleep(1)
            if parameter == 'exposure_time':
                self.exposure = value
            elif parameter == 'center_wavelength':
                self.wavelength = value
        else:
            raise KeyError('Set is not supported on {}'.format(parameter))

    def get_parameter(self, parameter):
        """Get a parameter from the spectrometer.

        @param str parameter: Parameter to get. This can be one of:
            - exposure_time (in seconds)
            - center_wavelength (in nanometres)
            - detector_temp (in degrees C)
        
        @return: Value of requested parameter

        @raises: KeyError if the parameter is unsupported.
        """
        if self.supported_params[parameter]['get']:
            if parameter == 'exposure_time':
                return self.exposure
            elif parameter == 'center_wavelength':
                return self.wavelength
            elif parameter == 'detector_temp':
                return -120
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

    def recordSpectrum(self):
        """ Record a dummy spectrum.

            @return ndarray: 1024-value ndarray containing wavelength and intensity of simulated spectrum
        """
        length = 1024

        data = np.empty((2, length), dtype=np.double)
        data[0] = np.arange(730, 750, 20/length)
        data[1] = np.random.uniform(0, 2000, length)

        lorentz, params = self._fitLogic.make_multiplelorentzian_model(no_of_functions=4)
        sigma = 0.05
        params.add('l0_amplitude', value=2000)
        params.add('l0_center', value=736.46)
        params.add('l0_sigma', value=1.5*sigma)
        params.add('l1_amplitude', value=5800)
        params.add('l1_center', value=736.545)
        params.add('l1_sigma', value=sigma)
        params.add('l2_amplitude', value=7500)
        params.add('l2_center', value=736.923)
        params.add('l2_sigma', value=sigma)
        params.add('l3_amplitude', value=1000)
        params.add('l3_center', value=736.99)
        params.add('l3_sigma', value=1.5*sigma)
        params.add('offset', value=50000.)

        data[1] += lorentz.eval(x=data[0], params=params)

        data[0] = data[0] * 1e-9  # return to logic in SI units (m)

        time.sleep(self.exposure)
        return data

    def saveSpectrum(self, path, postfix = ''):
        """ Dummy save function.

            @param str path: path of saved spectrum
            @param str postfix: postfix of saved spectrum file
        """
        timestr = strftime("%Y%m%d-%H%M-%S_", localtime())
        print( 'Dummy would save to: ' + str(path) + timestr + str(postfix) + ".spe" )

    def getExposure(self):
        """ Get exposure time.

            @return float: exposure time
        """
        return self.exposure

    def setExposure(self, exposureTime):
        """ Set exposure time.

            @param float exposureTime: exposure time
        """
        self.exposure = exposureTime
