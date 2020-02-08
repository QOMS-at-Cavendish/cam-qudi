# -*- coding: utf-8 -*-

"""
This file contains the Qudi HBT gui.

Modified from github.com/WarwickEPR/qudi

Main changes:
    -   Added settings dialog
    -   Reworked GUI
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

class SaveDialog(QtWidgets.QDialog):
    """ Dialog to provide feedback and block GUI while saving """
    def __init__(self, parent, title="Please wait", text="Saving..."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)

        # Dialog layout
        self.text = QtWidgets.QLabel("<font size='16'>" + text + "</font>")
        self.hbox = QtWidgets.QHBoxLayout()
        self.hbox.addSpacerItem(QtWidgets.QSpacerItem(50, 0))
        self.hbox.addWidget(self.text)
        self.hbox.addSpacerItem(QtWidgets.QSpacerItem(50, 0))
        self.setLayout(self.hbox)

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
        self._save_dialog = SaveDialog(self._mw)

        self.hbt_plotdata = pg.PlotDataItem((0,),
                                         (0,),
                                         pen=pg.mkPen(palette.c1, width=2),
                                         symbol='o',
                                         symbolPen=palette.c1,
                                         symbolBrush=palette.c1,
                                         symbolSize=2)

        # Set up HBT plot
        self._mw.hbt_plot_PlotWidget.addItem(self.hbt_plotdata)
        self._mw.hbt_plot_PlotWidget.setLabel(
            axis='left', text='Coincidences', units='Counts')
        self._mw.hbt_plot_PlotWidget.setLabel(
            axis='bottom', text='Time', units='s')
        self._mw.hbt_plot_PlotWidget.showGrid(x=True, y=True, alpha=0.8)

        # Settings dialog initialisation
        channels = self._hbt_logic.get_channels()
        for n, ch in enumerate(channels):
            self._sd.start_channel_comboBox.addItem(ch, n)
            self._sd.stop_channel_comboBox.addItem(ch, n)
        binlength = self._hbt_logic.get_bin_length() * 1e12
        self._sd.hardware_binlength_label.setText('{:.4f} ps'.format(binlength))
        
        self.reset_settings()

        #################
        # Connect signals
        #################
        self.connections = [
            # User interactions
            self._mw.run_hbt_Action.triggered.connect(self._hbt_logic.start_hbt),
            self._mw.stop_hbt_Action.triggered.connect(self._hbt_logic.stop_hbt),
            self._mw.save_hbt_Action.triggered.connect(self.save_clicked),
            self._mw.clear_hbt_Action.triggered.connect(self.clear_hbt),
            self._mw.histogram_setup_Action.triggered.connect(self._sd.exec_),
            self._mw.record_timestamps_Action.toggled.connect(self.record_clicked),

            # Settings dialog
            self._sd.accepted.connect(self.update_settings),
            self._sd.rejected.connect(self.reset_settings),

            # From logic module
            self._hbt_logic.hbt_updated.connect(self.update_data),
            self._hbt_logic.hbt_save_started.connect(self._save_dialog.show),
            self._hbt_logic.hbt_saved.connect(self._save_dialog.hide),
            self._hbt_logic.hbt_running.connect(self.update_hbt_run_status),
            self._hbt_logic.started_recording.connect(
                lambda: self._mw.record_timestamps_Action.setChecked(True)),
            self._hbt_logic.stopped_recording.connect(
                lambda: self._mw.record_timestamps_Action.setChecked(False))
        ]

        return 0

    def show(self):
        """Make window visible and put it above all other windows.
        """
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        """ Deactivate the module
        """
        for conn in self.connections:
            QtCore.QObject.disconnect(conn)
        self._mw.close()

    ###########
    # GUI slots
    ###########

    @QtCore.Slot()
    def save_clicked(self):
        """ Save action slot """
        self._hbt_logic.save_hbt()

    @QtCore.Slot()
    def clear_hbt(self):
        """ Clear action slot """
        self._hbt_logic.clear_hbt()

    @QtCore.Slot(bool)
    def record_clicked(self, enable):
        """ Record timestamps action slot  """
        self._hbt_logic.enable_recording(enable)

    #############
    # Logic slots
    #############

    @QtCore.Slot(bool)
    def update_hbt_run_status(self, status):
        """ Updates run/stop buttons when signalled by logic """
        self._mw.run_hbt_Action.setEnabled(not status)
        self._mw.stop_hbt_Action.setEnabled(status)

    def update_data(self):
        """ Updates g(2) plot

        Handler for logic's hbt_updated signal
        """
        data = self._hbt_logic.get_data()
        self.hbt_plotdata.setData(data[:, 0], data[:, 1])

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
        self._sd.max_filesize_lineEdit.setText(
            '{}'.format(self._hbt_logic.sizelimit/1e9))

    def update_settings(self):
        """ Update logic with values from settings dialog
        """
        try:
            bin_width = int(self._sd.bin_width_spinBox.value())
            bin_count = int(self._sd.bin_count_spinBox.value())
            start_channel = int(self._sd.start_channel_comboBox.currentText())
            stop_channel = int(self._sd.stop_channel_comboBox.currentText())
            delay = int(self._sd.ch1_delay_spinBox.value())
            maxsize = float(self._sd.max_filesize_lineEdit.text())

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

            self._hbt_logic.sizelimit = round(maxsize * 1e9)
            
        except ValueError:
            self.log.warn(
                'ValueError while converting settings input, nothing updated.')
            self.reset_settings()
