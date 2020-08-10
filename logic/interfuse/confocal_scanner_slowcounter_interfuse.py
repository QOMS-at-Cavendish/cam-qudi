
# -*- coding: utf-8 -*-
"""
Interfuse to do confocal scans with count rates from an arbitrary counter
that implements slow_counter_interface

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

import numpy as np

from core.module import Base
from core.configoption import ConfigOption
from core.connector import Connector
from logic.generic_logic import GenericLogic
from interface.confocal_scanner_interface import ConfocalScannerInterface
from interface.slow_counter_interface import SlowCounterInterface

class SlowcounterScannerInterfuse(GenericLogic, ConfocalScannerInterface):
    """ Interfuse for using arbitrary slow counter for confocal scanning.
    """

    # Connectors
    confocalscanner1 = Connector(interface='ConfocalScannerInterface')
    counter1 = Connector(interface='SlowCounterInterface')

    def on_activate(self):
        """ Sets up connections when module is activated
        """
        self._scanner_hw = self.confocalscanner1()
        self._counter_hw = self.counter1()


    def on_deactivate(self):
        pass

    ########################
    # Re-implemented methods
    ########################

    def get_scanner_count_channels(self):
        """ Returns the list of channels that are recorded while scanning an 
            image.

        @return list(str): channel names
        """
        return self._counter_hw.get_counter_channels()

    def set_up_scanner_clock(self, clock_frequency=None, clock_channel=None):
        """ Configures the exposure time of the Qutau.

        @param float clock_frequency: 1/exposure time in seconds
        @param str clock_channel: Ignored

        @return int: error code (0:OK, -1:error)
        """
        return self._counter_hw.set_up_clock(clock_frequency)

    def scan_line(self, line_path=None, pixel_clock=False):
        """ Scans a line and returns the counts on that line.

        @param float[c][m] line_path: array of c-part tuples defining m points
            for the scan
        @param bool pixel_clock: whether we need to output a pixel 
            clock for this line (ignored by this interfuse)

        @return float[m][n]: the photon counts per second for n channels
        """
        line_length = np.shape(line_path)[1]

        count_data = np.zeros(
                (line_length, len(self._counter_hw.get_counter_channels())))

        axes = self.get_scanner_axes()

        for i, point in enumerate(line_path.transpose()):
            # Translate 1-4 items from point into x,y,z,a needed by
            # scanner_set_position.
            if len(axes) > 0:
                pos = {'x':point[0]}
            if len(axes) > 1:
                pos['y'] = point[1]
            if len(axes) > 2:
                pos['z'] = point[2]
            if len(axes) > 3:
                pos['a'] = point[3]

            if self.scanner_set_position(**pos) != 0:
                return
            # Ensure we always get freshest counts
            # First call clears buffer, second waits for new counts
            self._counter_hw.get_counter()
            counts = self._counter_hw.get_counter()
            count_data[i, :] = counts[:, 0]
        
        return count_data
    
    #####################
    # Black-holed methods
    #####################

    def set_up_scanner(self,
                       counter_channels=None,
                       sources=None,
                       clock_channel=None,
                       scanner_ao_channels=None):
        return 0

    def close_scanner(self):
        return 0
    
    def close_scanner_clock(self):
        return 0
    
    ######################
    # Pass-through methods
    ######################

    def reset_hardware(self):
        return self._scanner_hw.reset_hardware()

    def get_position_range(self):
        return self._scanner_hw.get_position_range()

    def set_position_range(self, *args, **kwargs):
        return self._scanner_hw.set_position_range(*args, **kwargs)

    def set_voltage_range(self, *args, **kwargs):
        return self._scanner_hw.set_voltage_range(*args, **kwargs)

    def get_scanner_axes(self):
        return self._scanner_hw.get_scanner_axes()

    def scanner_set_position(self, *args, **kwargs):
        return self._scanner_hw.scanner_set_position(*args, **kwargs)

    def get_scanner_position(self):
        return self._scanner_hw.get_scanner_position()