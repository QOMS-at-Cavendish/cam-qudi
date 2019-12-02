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

from gui.colordefs import QudiPalettePale as palette

from core.connector import Connector
from gui.guibase import GUIBase

# Decorator to catch ValueError exceptions in functions which cast UI input text to other types.
def value_error_handler(func):
    @functools.wraps(func)
    def check(self,*args,**kwargs):
        try:
            return func(self,*args,**kwargs)
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
        self.power_filtered = np.zeros(100)
        self.time = np.arange(0,100)

        # Set up graph
        self._mw.plot.setLabel('left', 'Power', units='µW')
        self._mw.plot.setLabel('bottom', 'Time')
        self.plotdata = pg.PlotDataItem(pen=pg.mkPen(palette.c1, width=2))
        self.plotdata_smoothed = pg.PlotDataItem(pen=pg.mkPen(palette.c2, width=2), symbol=None)
        self._mw.plot.addItem(self.plotdata)
        self._mw.plot.addItem(self.plotdata_smoothed)

        # Connect GUI events
        self._mw.output_adj.valueChanged.connect(self.output_slider_moved)
        self._mw.output_adj.sliderPressed.connect(self.output_slider_pressed)
        self._mw.pid_enable.stateChanged.connect(self.enable_pid)
        self._mw.setpoint.editingFinished.connect(self.setpoint_changed)

        # Connect logic events
        self.aom_logic = self.aomlogic()

        self.aom_logic.sigAomUpdated.connect(self.update)

        # Set slider to appropriate range
        v_range = self.aom_logic.volt_range

        self._mw.output_adj.setMinimum(v_range[0]*10)
        self._mw.output_adj.setMaximum(v_range[1]*10)

        self.aom_logic.start_poll()

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        """ Deactivate module
        """
        self.aom_logic.stop_poll()

    def update(self, param_dict):
        """
        Callback to update interface when the AOM logic produces a sigAomUpdated.
        @param dict param_dict: Dict of parameters to use for updating GUI.
        """
        try:
            # Get photodiode voltage and power
            voltage = float(param_dict['pd-voltage'])
            power = float(param_dict['pd-power'])
            power_filtered = float(param_dict['pd-power-filtered'])
            volts = float(param_dict['aom-output'])


            # Update readout widgets
            self._mw.voltage_readout.setText("{:.3f}".format(voltage))
            self._mw.power_readout.setText("{:.3f}".format(power))
            self._mw.aom_out.setText("{:.2f}".format(volts))

            # Add power to rolling buffer and update plot data
            self.power_buffer = np.roll(self.power_buffer, -1)
            self.power_buffer[-1] = power

            self.power_filtered = np.roll(self.power_filtered, -1)
            self.power_filtered[-1] = power_filtered

            self.plotdata.setData(self.time, self.power_buffer)
            self.plotdata_smoothed.setData(self.time, self.power_filtered)
        except:
            # Stop polling if any exception is raised
            self.aom_logic.stop_poll()
            raise

    def output_slider_moved(self, val):
        volts = val / 10
        self.aom_logic.enable_pid(False)
        self._mw.pid_enable.setChecked(False)
        self.aom_logic.set_aom_volts(volts)

    def output_slider_pressed(self):
        val = self._mw.output_adj.value()
        self.output_slider_moved(val)

    def enable_pid(self, val):
        """
        Control Loop Enable checkbox ticked
        """
        if val == 0:
            # Unchecked
            self.aom_logic.enable_pid(False)
        elif val == 2:
            # Checked
            self.aom_logic.enable_pid(True)

    @value_error_handler    
    def setpoint_changed(self):
        """
        Setpoint changed
        """
        new_setpoint = float(self._mw.setpoint.text())
        self.aom_logic.setpoint = new_setpoint