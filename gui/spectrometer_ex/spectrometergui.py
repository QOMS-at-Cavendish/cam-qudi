# -*- coding: utf-8 -*-
"""
GUI for operating the spectrometer logic.

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

import os
import pyqtgraph as pg
import numpy as np

from core.connector import Connector
from core.util import units
from gui.colordefs import QudiPalettePale as palette
from gui.guibase import GUIBase
from gui.fitsettings import FitSettingsDialog, FitSettingsComboBox
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic

class SettingsDialog(QtWidgets.QDialog):
    """ Dialog for getting settings """
    def __init__(self):
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'settings_dialog.ui')
        super().__init__()
        uic.loadUi(ui_file, self)

class SpectrometerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        """Create main window from .ui file
        """
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_spectrometer.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()

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

class SpectrometerGui(GUIBase):
    """ GUI for collecting and displaying photon correlation histograms.
    """

    # Connectors
    spectrometerlogic = Connector(interface='SpectrometerLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        # Logic connector
        self._spectrum_logic = self.spectrometerlogic()

        # Qt windows
        self._mw = SpectrometerWindow()
        self._save_dialog = SaveDialog(self._mw)
        self._sd = SettingsDialog()

        # Set up spectrum plot
        self._plotdata = pg.PlotDataItem((0,),
                                         (0,),
                                         pen=pg.mkPen(palette.c1, width=2),
                                         symbol='o',
                                         symbolPen=palette.c1,
                                         symbolBrush=palette.c1,
                                         symbolSize=2)

        self._mw.spectrum_PlotWidget.addItem(self._plotdata)
        self._mw.spectrum_PlotWidget.setLabel(
            axis='left', text='Intensity', units='counts')
        self._mw.spectrum_PlotWidget.setLabel(
            axis='bottom', text='Wavelength', units='m')
        self._mw.spectrum_PlotWidget.showGrid(x=True, y=True, alpha=0.8)

        # Set up limits on wavelength/time combo boxes
        exposure_limits = self._spectrum_logic.get_limits('exposure_time')
        self._sd.exposure_SpinBox.setRange(*exposure_limits)
        wl_limits = self._spectrum_logic.get_limits('center_wavelength')
        self._sd.wavelength_SpinBox.setRange(*wl_limits)

        # Set up signals
        self.connections = (
            # User interactions
            self._mw.actionAcquire.triggered.connect(self._spectrum_logic.acquire_spectrum_async),
            self._mw.actionSave.triggered.connect(self._spectrum_logic.save_spectrum_async),
            self._mw.actionSettings.triggered.connect(self._sd.exec_),

            # Settings dialog
            self._sd.accepted.connect(self._save_settings),
            self._sd.update_pushButton.clicked.connect(self._get_settings),
            self._sd.wavelength_SpinBox.editingFinished.connect(self._wavelength_edited),
            self._sd.exposure_SpinBox.editingFinished.connect(self._exposure_edited),

            # Logic module
            self._spectrum_logic.status_changed.connect(self._logic_status_change),
            self._spectrum_logic.data_updated.connect(self._logic_data_updated),
        )

        self._wl_updated = False
        self._exp_updated = False

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
    def _get_settings(self):
        # Update settings
        self._spectrum_logic.update_params()
        self._wl_updated = False
        self._exp_updated = False

    @QtCore.Slot()
    def _save_settings(self):
        # Send new settings to logic on dialog accept
        if self._wl_updated:
            wl = self._sd.wavelength_SpinBox.value()
            self._spectrum_logic.set_wavelength(wl)
            self._wl_updated = False
        if self._exp_updated:
            exp = self._sd.exposure_SpinBox.value()
            self._spectrum_logic.set_exposure(exp)
            self._exp_updated = False

    @QtCore.Slot()
    def _wavelength_edited(self):
        self._wl_updated = True

    @QtCore.Slot()
    def _exposure_edited(self):
        self._exp_updated = True

    #############
    # Logic slots
    #############

    @QtCore.Slot(str)
    def _logic_status_change(self, status):
        if status == 'idle':
            enabled = True
            self._save_dialog.hide()
        
        if status == 'saving':
            enabled = False
            self._save_dialog.show()

        if status == 'busy':
            enabled = False
            self._save_dialog.hide()

        self._sd.exposure_SpinBox.setEnabled(enabled)
        self._sd.wavelength_SpinBox.setEnabled(enabled)
        self._sd.update_pushButton.setEnabled(enabled)
        self._sd.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(enabled)
        self._mw.actionAcquire.setEnabled(enabled)
        self._mw.actionSave.setEnabled(enabled)

    @QtCore.Slot(dict)
    def _logic_data_updated(self, data):
        for key in data:
            if key == 'center_wavelength':
                self._sd.wavelength_SpinBox.setValue(data[key])

            elif key == 'exposure_time':
                self._sd.exposure_SpinBox.setValue(data[key])

            elif key == 'detector_temp':
                self._sd.temp_SpinBox.setValue(data[key])

            elif key == 'spectrum':
                self._plotdata.setData(data[key][0, :], data[key][1, :])
