# -*- coding: utf-8 -*-
"""
Logic module for performing hyperspectral mapping.

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

from qtpy import QtCore

from core.connector import Connector
from logic.generic_logic import GenericLogic
from core.connector import Connector
from core.statusvariable import StatusVar

class HyperspectralLogic(GenericLogic):
    """Logic for acquiring hyperspectral maps.

    Config for copy-paste:

    hyperspectral:
        module.Class: 'hyperspectral_logic.HyperspectralLogic'
    """

    # Signal that data has been updated
    # Includes tuple containing names of updated attributes.
    sig_data_updated = QtCore.Signal(tuple)

    scannerlogic = Connector('ConfocalLogic')
    spectrometerlogic = Connector('SpectrometerLogic')

    # Internal signals
    _sig_start_mapping = QtCore.Signal(bool)

    _stop_requested = False

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    def start_mapping(self):
        if self.module_state() != 'locked':
            self._sig_start_mapping.emit(False)
        else:
            raise HyperspectralLogicError('Cannot start hyperspectral map: logic module busy')

    def continue_mapping(self):
        if self.module_state() != 'locked':
            self._sig_start_mapping.emit(True)
        else:
            raise HyperspectralLogicError('Cannot start hyperspectral map: logic module busy')
    
    def stop_mapping(self):
        self._stop_requested = True

    @QtCore.Slot(bool)
    def _start_mapping(self, continue_map=False):
        self.module_state.lock()
        if continue_map:
            start_x = self._last_x
            start_y = self._last_y
        else:
            start_x = self.scannerlogic().image_x_range[0]
            start_y = self.scannerlogic().image_y_range[0]
            
        stop_x = self.scannerlogic().image_x_range[1]
        stop_y = self.scannerlogic().image_y_range[1]

        self.log.debug('Run map between {}-{} (x) and {}-{} (y)'.format(start_x, stop_x, start_y, stop_y))
        self.module_state.unlock()

        

class HyperspectralLogicError(Exception):
    """Exception for HyperspectralLogic errors"""
    pass
    
