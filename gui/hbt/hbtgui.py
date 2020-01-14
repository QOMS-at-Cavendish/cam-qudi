# -*- coding: utf-8 -*-

"""
This file contains the Qudi HBT gui.

Slightly modified from github.com/WarwickEPR/qudi

Main changes:
    -   Added settings dialog
    -   Removed incomplete fitting stuff

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
import os
import pyqtgraph as pg

from core.module import Connector
from core.configoption import ConfigOption
from gui.colordefs import QudiPalettePale as palette
from gui.guibase import GUIBase
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic


class HbtSettingsDialog(QtWidgets.QDialog):
    """ Dialog for getting histogram settings """

    def __init__(self):
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'histogram_settings.ui')
        super(HbtSettingsDialog, self).__init__()
        uic.loadUi(ui_file, self)

class HbtMainWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self, **kwargs):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_hbt.ui')

        # Load it
        super().__init__(**kwargs)
        uic.loadUi(ui_file, self)
        self.show()

class HbtGui(GUIBase):
    """ GUI for collecting and displaying photon correlation histograms.
    """

    # Connectors
    hbtlogic = Connector(interface='HbtLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """

        self._hbt_logic = self.hbtlogic()

        # Qt windows
        self._mw = HbtMainWindow()
        self._sd = HbtSettingsDialog()

        self.hbt_image = pg.PlotDataItem((0,),
                                         (0,),
                                         pen=pg.mkPen(palette.c1, width=2),
                                         symbol='o',
                                         symbolPen=palette.c1,
                                         symbolBrush=palette.c1,
                                         symbolSize=2)

        # Set up HBT plot
        self._mw.hbt_plot_PlotWidget.addItem(self.hbt_image)
        self._mw.hbt_plot_PlotWidget.setLabel(
            axis='left', text='g2(t)', units='normalised units')
        self._mw.hbt_plot_PlotWidget.setLabel(
            axis='bottom', text='Time', units='s')
        self._mw.hbt_plot_PlotWidget.showGrid(x=True, y=True, alpha=0.8)

        #####################
        # Connecting user interactions
        self._mw.run_hbt_Action.toggled.connect(self.run_hbt_toggled)
        self._mw.save_hbt_Action.triggered.connect(self.save_clicked)
        self._mw.clear_hbt_Action.triggered.connect(self.clear_hbt)
        self._mw.histogram_setup_Action.triggered.connect(self._sd.exec_)

        # Settings dialog
        self._sd.accepted.connect(self.update_settings)
        self._sd.rejected.connect(self.reset_settings)

        # Settings dialog initialisation
        channels = self._hbt_logic.get_channels()
        for n, ch in enumerate(channels):
            self._sd.start_channel_comboBox.addItem(ch, n)
            self._sd.stop_channel_comboBox.addItem(ch, n)
        binlength = self._hbt_logic.get_bin_length() * 1e12
        self._sd.hardware_binlength_label.setText('{:.4f} ps'.format(binlength))
        
        self.reset_settings()

        ##################
        # Handling signals from the logic
        self._hbt_logic.hbt_updated.connect(self.update_data)

        return 0

    def run_hbt_toggled(self, run):
        if run:
            self._mw.run_hbt_Action.setIconText("Stop")
            self._hbt_logic.start_hbt()
        else:
            self._mw.run_hbt_Action.setIconText("Start")
            self._hbt_logic.stop_hbt()

    def show(self):
        """Make window visible and put it above all other windows.
        """
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        """ Deactivate the module
        """
        self._hbt_logic.stop_hbt()
        self._mw.close()
        return

    def update_data(self):
        """ Updates g(2) plot

        Handler for logic's hbt_updated signal
        """
        data = self._hbt_logic.get_data()
        self.hbt_image.setData(data[:, 0], data[:, 1])

    def save_clicked(self):
        """ Handling the save button to save the data into a file.
        """
        self._hbt_logic.save_hbt()

    def clear_hbt(self):
        """ Clears HBT. (toolbar button callback)
        """
        self._hbt_logic.clear_hbt()

    #################
    # Settings dialog
    #################

    def reset_settings(self):
        """ Resets settings dialog to values from logic module
        """
        self._sd.bin_width_spinBox.setValue(self._hbt_logic.bin_width)
        self._sd.bin_count_spinBox.setValue(self._hbt_logic.bin_count)
        idx = self._sd.start_channel_comboBox.findText(
            str(self._hbt_logic.start_channel))
        self._sd.start_channel_comboBox.setCurrentIndex(idx)
        idx = self._sd.stop_channel_comboBox.findText(
            str(self._hbt_logic.stop_channel))
        self._sd.stop_channel_comboBox.setCurrentIndex(idx)
        self._sd.ch1_delay_spinBox.setValue(self._hbt_logic.delay)

    def update_settings(self):
        """ Update logic with values from settings dialog
        """
        try:
            bin_width = int(self._sd.bin_width_spinBox.value())
            bin_count = int(self._sd.bin_count_spinBox.value())
            start_channel = int(self._sd.start_channel_comboBox.currentText())
            stop_channel = int(self._sd.stop_channel_comboBox.currentText())
            delay = int(self._sd.ch1_delay_spinBox.value())

            # Only update logic with parameters if they've been altered
            if bin_width == self._hbt_logic.bin_width:
                bin_width = None
            if bin_count == self._hbt_logic.bin_count:
                bin_count = None
            if delay == self._hbt_logic.delay:
                delay = None

            self._hbt_logic.configure(
                    bin_width, bin_count, start_channel, stop_channel,
                    delay)
            
        except ValueError:
            self.log.warn(
                'ValueError while converting settings input, nothing updated.')
            self.reset_settings()
