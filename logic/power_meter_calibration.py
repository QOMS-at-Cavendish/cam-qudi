# -*- coding: utf-8 -*-

"""
Create a calibration curve for the El Diablo photodiode using a Thorlabs PM100 power meter.
Activate module from Qudi manager to start logging calibration data.

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

from logic.generic_logic import GenericLogic
from core.connector import Connector
from core.statusvariable import StatusVar

import numpy as np
from qtpy import QtCore

class PowerMeterCalibration(GenericLogic):
    """ Power meter/photodiode calibration """

    # Connectors specifically to PM100D and X-series DAQ card.
    pm100 = Connector(interface='PM100D')
    nicard = Connector(interface='NationalInstrumentsXSeries')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        return

    def on_activate(self):
        """	
        Initialisation performed during activation of the module.
        """
        # Hardware objects
        self.power_meter = self.pm100()
        self.daqcard = self.nicard()

        # Timer for querying power meter and photodiode.
        self.queryInterval = 1000

        self.queryTimer = QtCore.QTimer()
        self.queryTimer.setInterval(self.queryInterval)
        self.queryTimer.setSingleShot(True)
        self.queryTimer.timeout.connect(self.record_data, QtCore.Qt.QueuedConnection)

        self.stop_request = False
        self.queryTimer.start(self.queryInterval)

        return

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.	
        """
        self.queryTimer.stop()
        self.stop_request = True
        return

    def record_data(self):
        """
        Callback for timer.
        """
        if self.stop_request:
            return
        power_meter_reading = self.power_meter.get_power()
        photodiode_reading = np.mean(self.daqcard.analog_channel_read('Dev1/ai0'))

        self.log.debug("PM: {} PD: {}".format(power_meter_reading, photodiode_reading))

        self.queryTimer.start(self.queryInterval)