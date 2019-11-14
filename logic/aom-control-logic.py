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


class AomControlLogic(GenericLogic):
    """
    Control laser power with AOM
    """

    sigPowerUpdated = QtCore.Signal(dict)
    nicard = Connector(interface='NationalInstrumentsXSeries')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        # Hardware
        self.daqcard = self.nicard()

        self.queryInterval = 100

        self._stop_poll = False

        # Timer
        self.queryTimer = QtCore.QTimer()
        self.queryTimer.setInterval(self.queryInterval)
        self.queryTimer.setSingleShot(True)
        self.queryTimer.timeout.connect(self.update_power_reading, QtCore.Qt.QueuedConnection)

        self.queryTimer.start(self.queryInterval)

    def on_deactivate(self):
        """Module deactivation
        """
        # Stop timer
        self.queryTimer.stop()
        self._stop_poll = True


    def update_power_reading(self):
        """
        Get power reading from DAQ card.
        """
        if self._stop_poll == True:
            return

        #TODO: make channel a config option
        voltage_reading = np.mean(self.daqcard.analog_channel_read('/Dev1/ai0'))

        # Calibration gives near perfectly linear relationship
        # *81.571 to get uW before scanning mirror
        # *0.3525 to get uW after objective
        power = voltage_reading * 81.571 * 0.3525

        output_dict = {
            'pd-voltage':voltage_reading,
            'pd-power':power
        }

        self.sigPowerUpdated.emit(output_dict)

        self.queryTimer.start(self.queryInterval)