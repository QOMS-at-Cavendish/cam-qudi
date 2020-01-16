"""
This module performs an HBT and saves data appropriately.

Heavily modified from github.com/WarwickEPR/qudi

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

from collections import OrderedDict
import numpy as np
from logic.generic_logic import GenericLogic
from core.module import Connector
from core.configoption import ConfigOption
from qtpy import QtCore

import matplotlib.pyplot as plt

class HbtLogic(GenericLogic):
    """
    This is the logic for running HBT experiments.

    Example config for copy-paste:

    hbtlogic:
        module.Class: 'hbt_logic.HbtLogic'
        start_channel: 1
        stop_channel: 2
        bin_width: 4
        bin_count: 500
    """

    start_channel = ConfigOption('start_channel', 1)
    stop_channel = ConfigOption('stop_channel', 2)

    # Bin width and count in hardware units
    bin_width = ConfigOption('bin_width', 4)
    bin_count = ConfigOption('bin_count', 500)

    # Channel 1 delay in hardware units
    delay = ConfigOption('delay', 0)

    # Update rate in Hz
    _update_rate = ConfigOption('update_rate', 1)

    savelogic = Connector(interface='SaveLogic')

    # Currently this logic module is specific to the QuTau
    qutau = Connector(interface='QuTau')

    hbt_updated = QtCore.Signal()
    hbt_saved = QtCore.Signal()

    _sig_start_hbt = QtCore.Signal()
    _sig_stop_hbt = QtCore.Signal()

    def on_activate(self):
        """ Sets up qutau for histogram measurements.
        """
        self._save_logic = self.savelogic()
        self._qutau = self.qutau()

        self._qutau.enable_histogram()
        self._qutau.set_histogram_params(self.bin_width, self.bin_count)
        if self.delay > 0:
            self._qutau.set_delays([self.delay])

        self._sig_start_hbt.connect(self._start_hbt)
        self._sig_stop_hbt.connect(self._stop_hbt)

        # At the moment, the Qutau handles all the histogram acquisition, so
        # just emit update available signal periodically for GUI.
        self._update_timer = QtCore.QTimer()
        self._update_timer.timeout.connect(self.hbt_updated.emit)

        self._hbt_running = False
    
    def start_hbt(self):
        self._sig_start_hbt.emit()

    def _start_hbt(self):
        """ Starts acquiring HBT and sending updates to GUI.

        Does not clear any HBT data, so can be used to re-start a stopped
        acquisition.
        """
        # Unfreeze buffer
        self._qutau.freeze_buffers(False)
        self._update_timer.start(round(1000/self._update_rate))

    def stop_hbt(self):
        self._sig_stop_hbt.emit()

    def _stop_hbt(self):
        """ Pauses acquiring HBT and sending updates to GUI.
        """
        self._qutau.freeze_buffers(True)
        self._update_timer.stop()
        self.hbt_updated.emit()

    def clear_hbt(self):
        self._qutau.clear_histogram()
        self.hbt_updated.emit()

    def get_data(self):
        return self._qutau.get_histogram(self.start_channel, self.stop_channel)

    def save_hbt(self):
        # File path and name
        filepath = self._save_logic.get_path_for_module(module_name='HBT')

        histogram = self.get_data()
        data = OrderedDict()
        data['Time (s)'] = histogram[:, 0]
        data['g2(t)'] = histogram[:, 1]

        timebase = self._qutau.get_bin_length()

        params = {
            'Bin width (HW bins)':self.bin_width,
            'Bin count':self.bin_count,
            'Exposure time (s)':self._qutau.hist_exposure_time*timebase,
            'Start channel':self.start_channel,
            'Stop channel':self.stop_channel,
            'Ch1 Delay (HW bins)':self.delay,
            'HW bin length (ps)':timebase*1e12
        }

        plot = self._create_figure(histogram)

        self._save_logic.save_data(
            data, filepath=filepath, filelabel='g2data', 
            fmt=['%.6e', '%.6e'], parameters=params, plotfig=plot)
        self.log.debug('HBT data saved to:\n{0}'.format(filepath))

        self.hbt_saved.emit()
        return 0

    def on_deactivate(self):
        """ Reverse steps of activation

        @return int: error code (0:OK, -1:error)
        """
        return 0

    def configure(
            self, bin_width=None, bin_count=None, 
            start_channel=None, stop_channel=None, delay=None):
        """ Configures histogram parameters.

        @param int bin_width: Width of bin in hardware units
        @param int bin_count: Number of bins in hardware units
        @param int start_channel: Start channel (1-9)
        @param int stop_channel: Stop channel (1-9)
        """
        if bin_width is not None:
            self.bin_width = int(bin_width)
        
        if bin_count is not None:
            self.bin_count = int(bin_count)

        if start_channel is not None:
            self.start_channel = int(start_channel)
        
        if stop_channel is not None:
            self.stop_channel = int(stop_channel)

        if bin_width is not None or bin_count is not None:
            self._qutau.set_histogram_params(self.bin_width, self.bin_count)

        if delay is not None:
            self.delay = int(delay)
            self._qutau.set_delays([self.delay])

    def get_channels(self):
        """ Get list of enabled channels from hardware
        """
        return self._qutau.get_histogram_channels()

    def get_bin_length(self):
        """ Get hardware bin length in seconds
        """
        return self._qutau.get_bin_length()

    def _create_figure(self, histogram):
        """ Creates matplotlib figure for saving
        """
        # Use qudi style
        plt.style.use(self._save_logic.mpl_qd_style)
        # Create figure
        fig, ax = plt.subplots()
        ax.set_xlabel('Time delay (ns)')
        ax.set_ylabel('Coincidences')

        ax.plot(histogram[:, 0]*1e9, histogram[:, 1])

        return fig