# -*- coding: utf-8 -*-

"""
Logic module for controlling power via AOM

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

import numpy as np

from core.connector import Connector
from core.statusvariable import StatusVar
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic
from qtpy import QtCore

from core.configoption import ConfigOption

from PyDAQmx import DAQError


class AomControlLogic(GenericLogic):
    """
    Control laser power with AOM
    """

    sigAomUpdated = QtCore.Signal(dict)
    nicard = Connector(interface='NationalInstrumentsXSeries')

    # Config options
    photodiode_channel = ConfigOption('photodiode_channel', missing='error')
    aom_channel = ConfigOption('aom_channel', '')
    photodiode_factor = ConfigOption('photodiode_factor', 1.0)
    query_interval = ConfigOption('query_interval', 100)
    volt_range = ConfigOption('aom_volt_range', [0,5])

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        # Hardware
        self.daqcard = self.nicard()

        self.start_poll()
        

    def on_deactivate(self):
        """Module deactivation
        """
        self.stop_poll()
        

    def start_poll(self):
        """
        Start polling DAQ
        """
        self._stop_poll = False
        QtCore.QTimer.singleShot(self.query_interval, self.update_power_reading)

    def stop_poll(self):
        """
        Stop polling DAQ
        """
        self._stop_poll = True


    def update_power_reading(self):
        """
        Get power reading from DAQ card.
        """
        if self._stop_poll == True:
            return

        try:
            # Read voltage from photodiode
            voltage_reading = np.mean(self.daqcard.analog_channel_read(self.photodiode_channel))
        
            # Convert power to volts using factor
            power = voltage_reading * self.photodiode_factor

            output_dict = {
                'pd-voltage':voltage_reading,
                'pd-power':power
            }

            self.sigAomUpdated.emit(output_dict)
            QtCore.QTimer.singleShot(self.query_interval, self.update_power_reading)

        except DAQError as err:
            # Log any DAQ errors
            self.log.error('DAQ error {}'.format(err))

    def set_aom_volts(self, volts):
        """
        Manually set AOM output to specified volts.
        """
        volts = float(volts)
        if volts >= min(self.volt_range) and volts <= max(self.volt_range):
            # Check inside acceptable voltage range
            # Write to analogue output
            if self.aom_channel != '':
                self.daqcard.analog_channel_write(self.aom_channel, volts)
                return 0
            else:
                self.log.warn('No AOM channel specified - no output')
                return -1