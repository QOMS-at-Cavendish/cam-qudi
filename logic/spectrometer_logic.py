# -*- coding: utf-8 -*-
"""
Logic for interfacing with spectrometers using SpectrometerInterfaceEx

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

from core.connector import Connector
from logic.generic_logic import GenericLogic
from qtpy import QtCore
from collections import OrderedDict
import matplotlib.pyplot as plt
import numpy as np


class SpectrometerLogic(GenericLogic):
    """Obtain spectra.
    """
    # Declare connectors
    spectrometer = Connector(interface='SpectrometerInterfaceEx')
    savelogic = Connector(interface='SaveLogic')

    # Signals for GUI
    status_changed = QtCore.Signal(str)
    data_updated = QtCore.Signal(dict)

    # Internal signals
    _start_acquisition = QtCore.Signal()
    _start_save = QtCore.Signal()
    _set_param = QtCore.Signal(list)
    _update_all = QtCore.Signal()

    def on_activate(self):
        self._spectrometer = self.spectrometer()
        self._save_logic = self.savelogic()

        self.params = self._spectrometer.get_supported_params()

        self.spectrum_data = np.zeros((2,1))

        self.connections = (
            self._start_acquisition.connect(self.acquire_spectrum),
            self._start_save.connect(self.save_spectrum),
            self._set_param.connect(self.set_parameters),
            self._update_all.connect(self._update_params),
            self.status_changed.connect(self._lock_module)
        )

    def on_deactivate(self):
        for conn in self.connections:
            QtCore.QObject.disconnect(conn)

    ###################
    # Blocking methods
    ###################

    @QtCore.Slot(list)
    def set_parameters(self, param):
        try:
            self.status_changed.emit('busy')
            self._spectrometer.set_parameter(*param)
            self.data_updated.emit({param[0]:param[1]})
        finally:
            self.status_changed.emit('idle')

    @QtCore.Slot()
    def acquire_spectrum(self):
        try:
            self.status_changed.emit('busy')
            spect = self._spectrometer.acquire_spectrum()

            self.data_updated.emit({'spectrum':spect})
            self.spectrum_data = spect
            return spect

        finally:
            self.status_changed.emit('idle')

    @QtCore.Slot()
    def save_spectrum(self):
        self.status_changed.emit('saving')
        try:
            filepath = self._save_logic.get_path_for_module(module_name='Spectrometer')

            data = OrderedDict()
            data['Counts'] = self.spectrum_data[0, :]
            data['Wavelength (m)'] = self.spectrum_data[1, :]

            plot = self._create_figure()

            self._save_logic.save_data(
                data, filepath=filepath, filelabel='spectrum', 
                fmt=['%.6e', '%.6e'], plotfig=plot)

            self.log.debug('Spectrum data saved to:\n{0}'.format(filepath))
        finally:
            self.status_changed.emit('idle')

    def get_limits(self, param):
        return [self.params[param]['min'], self.params[param]['max']]

    ##############################
    # Non-blocking methods for GUI
    ##############################

    def acquire_spectrum_async(self):
        self._start_acquisition.emit()

    def save_spectrum_async(self):
        self._start_save.emit()

    def set_exposure(self, exposure):
        self._set_param.emit(['exposure_time', exposure])

    def set_wavelength(self, wavelength):
        self._set_param.emit(['center_wavelength', wavelength])

    def update_params(self):
        self._update_all.emit()

    ###################
    # Internal methods
    ###################
    
    @QtCore.Slot()
    def _update_params(self):
        try:
            self.status_changed.emit('busy')
            param_dict = {}
            for param in self.params.keys():
                param_dict[param] = self._spectrometer.get_parameter(param)
            self.data_updated.emit(param_dict)
        finally:
            self.status_changed.emit('idle')

    @QtCore.Slot(str)
    def _lock_module(self, state):
        if state in ('busy', 'saving'):
            self.module_state.lock()
        else:
            self.module_state.unlock()

    def _create_figure(self):
        """ Creates matplotlib figure for saving
        """
        # Use qudi style
        plt.style.use(self._save_logic.mpl_qd_style)
        # Create figure
        fig, ax = plt.subplots()
        ax.set_xlabel('Wavelength (nm)')
        ax.set_ylabel('Intensity')

        ax.plot(self.spectrum_data[0, :]*1e9, self.spectrum_data[1, :])

        return fig