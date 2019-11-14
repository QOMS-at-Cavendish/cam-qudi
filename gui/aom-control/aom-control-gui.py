# -*- coding: utf-8 -*-

"""
This file contains a Qudi gui module for AOM control of laser power
and read-out from a photodiode.

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

"""

import os
import numpy as np
from itertools import cycle
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import uic
import pyqtgraph as pg
import functools
import datetime

from core.connector import Connector
from gui.guibase import GUIBase

# Decorator to catch ValueError exceptions in functions which cast UI input text to other types.
def value_error_handler(func):
    @functools.wraps(func)
    def check(self,*args,**kwargs):
        try:
            func(self,*args,**kwargs)
        except ValueError:
            self.log.warn("ValueError when converting UI input - check input values")
    return check

class AomMainWindow(QtWidgets.QMainWindow):

    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'aom-control.ui')

        # Load it
        super(AomMainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()

class AomControlGui(GUIBase):

    # declare connectors
    aomlogic = Connector(interface='AomControlLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        # Create main window instance
        self._mw = AomMainWindow()

        # Create 100 sample rolling buffer for the output graph
        self.power_buffer = np.zeros(100)
        self.time = np.arange(0,100)

        # Set up graph
        self._mw.plot.setLabel('left', 'Power', units='µW')
        self._mw.plot.setLabel('bottom', 'Time')
        self.plotdata = pg.PlotDataItem(pen=pg.mkPen('0BF', width=2))
        self._mw.plot.addItem(self.plotdata)

        self.aom_logic = self.aomlogic()

        self.aom_logic.sigPowerUpdated.connect(self.update_power)

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        """ Deactivate module
        """
        pass

    def update_power(self, power_dict):
        voltage = float(power_dict['pd-voltage'])
        power = float(power_dict['pd-power'])

        self._mw.voltage_readout.setText("{:.3f}".format(voltage))
        self._mw.power_readout.setText("{:.3f}".format(power))

        self.power_buffer = np.roll(self.power_buffer, -1)
        self.power_buffer[-1] = power

        self.plotdata.setData(self.time, self.power_buffer)

