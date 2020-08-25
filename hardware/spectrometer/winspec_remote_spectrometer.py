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
import numpy as np
import winspec

class WinspecRemote(Base, SpectrometerInterface):
    """This module interfaces with a remote Winspec spectrometer using the 
    winspec package.

    Demo config:

    spectrometer:
        module.Class: 'spectrometer.winspec_remote_spectrometer.WinspecRemote'
        remote_host: 'ws://<ip-address>:<port>
    """

    # Config options
    remote_host = ConfigOption('remote_host', missing='error')

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

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