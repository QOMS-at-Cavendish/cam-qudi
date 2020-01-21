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
import os

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

    # Max filesize for saved timestamp data (bytes)
    _max_filesize = ConfigOption('max_filesize', 10e9)

    savelogic = Connector(interface='SaveLogic')

    # Currently this logic module is specific to the QuTau
    qutau = Connector(interface='QuTau')

    hbt_updated = QtCore.Signal()
    hbt_save_started = QtCore.Signal()
    hbt_saved = QtCore.Signal()
    hbt_running = QtCore.Signal(bool)
    
    started_recording = QtCore.Signal()
    stopped_recording = QtCore.Signal()

    _sig_start_hbt = QtCore.Signal()
    _sig_stop_hbt = QtCore.Signal()
    _sig_save_hbt = QtCore.Signal()

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
        self._sig_save_hbt.connect(self._save_hbt)

        # At the moment, the Qutau handles all the histogram acquisition, so
        # just emit update available signal periodically for GUI.
        self._update_timer = QtCore.QTimer()
        self._update_timer.timeout.connect(self.hbt_updated.emit)

        # Timer for file size checker (10 sec)
        self._file_check_timer = QtCore.QTimer()
        self._file_check_timer.timeout.connect(self._check_file)
        self.started_recording.connect(lambda: self._file_check_timer.start(1e4))
        self.stopped_recording.connect(self._file_check_timer.stop)

        self.sizelimit = 10e9

        self._hbt_running = False
    
    def start_hbt(self):
        self.hbt_running.emit(True)
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
        self.hbt_running.emit(False)
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
        """ Save current HBT data
        """
        # Emit save signal to run save in logic thread
        self._sig_save_hbt.emit()

    def _save_hbt(self):
        # File path and name
        self.hbt_save_started.emit()
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

    def enable_recording(self, enable=True):
        """ Enables recording to file.

        If sizelimit is specified, automatically stop recording if file size
        exceeds specified limit in bytes.

        @param enable: bool, enable/disable recording to file
        @param sizelimit: int, specify maximum size of file
        """
        if not enable:
            self._qutau.stop_recording()
            self.stopped_recording.emit()
            return

        path = self._save_logic.get_path_for_module('HBT')
        if os.path.exists(os.path.join(path, 'raw_count_data')):
            i = 1
            while os.path.exists(os.path.join(path, 'raw_count_data_{}'.format(i))):
                i += 1
            self.filename = os.path.join(path, 'raw_count_data_{}'.format(i))
        else:
            self.filename = os.path.join(path, 'raw_count_data')

        self._qutau.record_timestamps(self.filename)

        self.started_recording.emit()

    def _check_file(self):
        """ Checks if timestamp file has exceeded limit 

        Slot for _file_check_timer timeout
        """
        if os.path.getsize(self.filename) > self.sizelimit:
            self.enable_recording(False)
            self.log.warn('Stopped recording timestamps: file exceeded '
                'specified max size {} GB'.format(self.sizelimit/1e9))


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