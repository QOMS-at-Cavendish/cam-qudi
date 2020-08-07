# -*- coding: utf-8 -*-
"""
Qudi hardware interface to QuTau time-tagger.

Implements slow_counter_interface.

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
import hardware.qutau.qutaupy as qutaupy
import time
import threading

from core.module import Base
from core.configoption import ConfigOption
from interface.slow_counter_interface import SlowCounterInterface
from interface.slow_counter_interface import SlowCounterConstraints, CountingMode


class CountPoller(threading.Thread):
    """ Thread to poll counts asynchronously.

    Usage
    -----
    Call get_counts(), which will block any number of callers
    until QuTAU reports at least 1 update, when it will return the count data
    to all callers.

    To stop the thread, call stop().

    @param hardware_method: Callable that implements qutaupy.getCoincCounters
    @param timeout: Unblock and throw TimeoutError after this time (default 10 secs)
    """

    def __init__(self, hardware_method, timeout=10):
        super().__init__()
        self._update_signal = threading.Event()
        self._poll_signal = threading.Event()
        self._stop_signal = threading.Event()
        self._get_counters = hardware_method
        self._count_data = None
        self._count_data_lock = threading.Lock()
        self.timeout = timeout
        self.daemon = True

    def run(self):
        """ Runs polling loop """
        self._stop_signal.clear()
        while self._stop_signal.is_set() == False:
            # Wait until counts are requested
            self._poll_signal.wait()

            # Poll QuTAU for latest count data
            num_updates = 0
            # Want to wait for 1 update from time of call, so clear buffer with
            # an initial call to _get_counters()
            self._get_counters()
            while num_updates == 0:
                # Poll until 1 update arrives
                r = self._get_counters()
                num_updates = r['updates']
                if num_updates == 0:
                    # Wait until at least 1 update of the count data has
                    # occurred.
                    if self._stop_signal.is_set():
                        return
                    if not self._poll_signal.is_set():
                        break
                    time.sleep(1e-3)
                else:
                    self._count_data = r['data']
                    self._update_signal.set()
                    self._poll_signal.clear()

    def get_counts(self):
        """ Gets counts from counter, blocking until countdata is updated.

        Any number of callers will be blocked until update, when they will all
        receive count data."""
        self._update_signal.clear()
        self._poll_signal.set()
        if self._update_signal.wait(timeout=self.timeout):
            with self._count_data_lock:
                return np.copy(self._count_data)
        else:
            raise TimeoutError('Timeout while waiting for counts from QuTAU')

    def stop(self):
        """ Stops thread polling loop """
        self._stop_signal.set()


class QuTau(Base, SlowCounterInterface):
    """ A QuTau time-to-digital converter.

    Can serve as a photon counter (implementing SlowCounterInterface)
    Also provides methods for collecting a start-stop histogram for second-
    order Hanbury Brown and Twiss photon correlation experimnents.

    Note that in all methods the channel numbers correspond to the actual
    channels printed on the front of the QuTAU.

    Example config for copy-paste:

    qutau:
        module.Class: 'qutau.qutau.QuTau'
        enabled_channels: [1, 2]
    """

    #######################
    # Configuration options
    #######################

    _dll_name = ConfigOption('dll_name', default='tdcbase.dll')
    _dll_path = ConfigOption(
        'dll_path',
        default="C:\\Program Files (x86)\\qutools\\quTAU\\userlib\\lib64\\"
    )
    _enabled_channels = ConfigOption('enabled_channels', missing='error')
    _default_clock = ConfigOption('default_clock_freq', default=10)
    _default_binwidth = ConfigOption('default_binwidth', default=2)
    _default_bincount = ConfigOption('default_bincount', default=512)
    _default_delays = ConfigOption('default_delays', default=[0])
    _enable_histogram = ConfigOption('enable_histogram', default=False)

    # If this is true, sum up all channels for slow_counter_interface methods
    _sum_all_channels = ConfigOption('sum_all_channels', default=False)

    _timeout = ConfigOption('counter_timeout', 5)

    ###############
    # Class methods
    ###############

    def on_activate(self):
        """ Starts up qutau on module activation.
        """
        # Create QuTau object and try to connect (to any available device)
        self.qutau = qutaupy.QuTau(self._dll_name, self._dll_path)

        try:
            self.qutau.init(-1)
        except qutaupy.QuTauError as err:
            if err.value == qutaupy.errors.TDC_NotConnected:
                self.log.warn('No QuTau detected. Continuing in demo mode.')
            else:
                raise err

        self.channel_bitmask = 0
        self.enabled_channels = []

        # This is used for blocking execution in get_counter for correct time
        self.last_called_time = 0

        # Get enabled channels
        for channel in range(1, 9):
            if channel in list(self._enabled_channels):
                self.channel_bitmask = 2**(channel-1) | self.channel_bitmask
                self.enabled_channels.append(channel)
        # Enable channels
        self.qutau.enableChannels(self.channel_bitmask)

        # Set defaults
        self.enable_histogram(self._enable_histogram)

        self.hist_exposure_time = 0

        if self.startstop_enabled:
            self.set_delays(self._default_delays)
            self.set_histogram_params(
                self._default_binwidth, self._default_bincount)

        # Set qutau exposure time
        self.set_up_clock(clock_frequency=self._default_clock)

        # Start count polling thread
        self.count_poller = CountPoller(
            self.qutau.getCoincCounters, timeout=self._timeout)

        self.count_poller.start()

    def on_deactivate(self):
        """ Shuts down qutau on module deactivation.
        """
        self.count_poller.stop()
        self.qutau.deInit()

    ################################
    # Start-stop histogram functions
    ################################

    def enable_histogram(self, enable=True, histograms=[]):
        """ Enables histogram calculations

        @param bool enable: Enable/disable histogram module (True/False)
        
        @param list histograms: List of (startCh, stopCh, enable) lists,
        specifying which histograms to enable/disable.
        """
        self.qutau.enableStartStop(enable)
        self.startstop_enabled = enable

        for hist in histograms:
            self.log.debug('Adding histogram {}'.format(hist))
            self.qutau.addHistogram(*hist)

    def set_histogram_params(self, bin_width, bin_count):
        """ Sets parameters for the acquired start-stop histogram.

        @param int bin_width: Number of hardware bins to sum (should be an
                even number due to QuTau's internal architecture - see the 
                manual)
        @param int bin_count: Number of summed bins to include in histogram
        """
        if not self.startstop_enabled:
            self.enable_histogram()

        if bin_width % 2 != 0:
            self.log.warn('Using an even number of hardware bins for the '
                          'bin width is recommended due to the unequal length of '
                          'alternate hardware bins - see QuTAU manual. '
                          'Bin width is currently set to {} bins.'.format(bin_width))

        self.qutau.setHistogramParams(bin_width, bin_count)

    def get_histogram_params(self):
        """ Gets the current bin width and bin count.

        bin_width is returned as the integer number of hardware bins being
        summed to form the start-stop histogram. bin_count is the number of
        these summed bins.

        @return tuple (bin_width, bin_count)
        """
        if not self.startstop_enabled:
            self.enable_histogram()

        r = self.qutau.getHistogramParams()

        return r['binWidth'], r['binCount']

    def get_histogram(self, start_channel, stop_channel, reset=False, normalise=False):
        """ Get start-stop histogram.

        @param int start_channel: Start channel (1-8)
        @param int stop_channel: Stop channel (1-8)
        @param bool reset: Reset accumulated histogram after read (default false)
        @param bool normalise: Normalise histogram (default false)

        @return 2D array (binCount, 2): histogram data with axis 0 as time delay; 
                axis 1 as counts (normalised if normalise parameter is set)
        """
        data = self.qutau.getHistogram(start_channel-1, stop_channel-1, reset)

        hist = np.zeros((data['binCount'], 2))

        # Calculate time axis
        bin_time = self.qutau.getTimebase()*data['binWidth']
        hist[:, 0] = np.linspace(
            0, bin_time*data['binCount'], data['binCount'])

        if normalise:
            hist[:, 1] = data['data'] / data['count']
        else:
            hist[:, 1] = data['data']

        self.hist_exposure_time = data['expTime']

        return hist

    def freeze_buffers(self, freeze=True):
        """ Freezes buffers, stopping updates on the histogram.

        @param bool freeze: Freeze/unfreeze buffer
        """
        self.qutau.freezeBuffers(freeze)

    def clear_histogram(self):
        """ Clears all histograms
        """
        self.qutau.clearAllHistograms()

    def set_delays(self, delays=[]):
        """ Sets delays on each channel 1-8.

        @param delays: list of delays, up to one for each channel
            Any delay not specified will be set to zero.
        """
        self.qutau.setChannelDelays(delays)

    def get_bin_length(self):
        """ Gets hardware bin length in seconds
        """
        return self.qutau.getTimebase()

    def get_histogram_channels(self):
        """ Gets list of channels that can contribute to the histogram

        @return list: all enabled channels on the Qutau as strings.
        """
        return [str(channel) for channel in self.enabled_channels]

    def record_timestamps(self, filename):
        """ Starts recording timestamps to file.

        Timestamps are recorded in binary format with a 40-byte header, 
        8 bytes containing the timestamp and 2 bytes indicating the channel. 
        Little-endian byte order.

        @param filename: Fully-specified filename for saving timestamps on disk
        """
        self.qutau.writeTimestamps(
            filename, qutaupy.TDC_FileFormat.FORMAT_BINARY)

    def stop_recording(self):
        """ Stops recording timestamps to file. """
        self.record_timestamps('')

    #####################################
    # SlowCounterInterface implementation
    #####################################

    def get_constraints(self):
        """ Returns hardware limits on qutau's counting ability.

        @return SlowCounterConstraints: object with constraints.
        """
        c = SlowCounterConstraints()
        c.max_detectors = 8

        # Highest count frequency limited by min exposure time (1 ms)
        c.max_count_frequency = 1/1e-3

        # Lowest count frequency limited by max exposure time (65536 ms)
        # or preset timeout, whichever is lower
        c.min_count_frequency = 1/min(65.5, self._timeout)

        c.counting_mode = [CountingMode.CONTINUOUS]

        return c

    def set_up_clock(self, clock_frequency=None, clock_channel=None):
        """ Sets exposure time on the Qutau.

        This function uses the reciprocal of the clock_frequency parameter to 
        set the exposure time on the qutau.

        @param float clock_frequency: Set update frequency in Hz
        Ignores clock_channel.
        """
        if clock_frequency is None:
            # Set default clock if none specified
            self.clock_frequency = self._default_clock
        else:
            self.clock_frequency = clock_frequency

        # self.clock_frequency is in Hz, setExposureTime needs milliseconds
        self.qutau.setExposureTime(round(1000/(self.clock_frequency)))

        return 0

    def set_up_counter(
            self, counter_channels=None, sources=None, clock_channel=None,
            counter_buffer=None):
        """ No-op

        counter_logic calls this without arguments, so we can hopefully ignore
        it
        """
        return 0

    def get_counter(self, samples=1):
        """ Returns the current counts per second of the counter.

        counter_logic expects this function to block execution until new counts
        are available.

        This function therefore blocks execution until the qutau
        reports that it has updated its internal counters.

        @param int samples: Optional: read this many samples from the counter

        @return numpy.array of photon counts per second for each channel
                (dtype=uint32) <- not sure if this is necessary but it is
                                    specified in slow_counter_interface
        """

        try:
            data = np.zeros((len(self.enabled_channels),
                             samples), dtype=np.uint32)
            for sample in range(samples):
                # Get data using qutau polling thread
                raw_countdata = self.count_poller.get_counts()
                for num, channel in enumerate(self.enabled_channels):
                    # Restrict to enabled channels only and convert to cps
                    data[num, sample] = raw_countdata[channel-1] * \
                        self.clock_frequency

        except TimeoutError:
            # Return -1 in 'expected format' if hardware times out (NB this is
            # inconsistent with the dtype=uint32 specified in the interface)
            # Raising the exception would be more robust, but counter_logic
            # expects errors through return values.
            return np.ones((len(self.enabled_channels), samples))*-1

        if self._sum_all_channels:
            # Sum all channels together and return 1 count trace
            output_sum = np.zeros((1, samples), dtype=np.uint32)
            for channel in self.enabled_channels:
                output_sum[0, :] += data[channel-1, :]
            return output_sum
        else:
            return data

    def get_counter_channels(self):
        """ Returns the list of counter channel names.

        If the sum_all_channels option is set, just returns ['Sum'].

        Can use get_histogram_channels() to always get a list of enabled
        hardware channels.

        @return list(str): channel names
        """
        if self._sum_all_channels:
            return ['Sum']
        else:
            return [str(channel) for channel in self.enabled_channels]

    def close_counter(self):
        """ No-op

        @return int: 0
        """

        return 0

    def close_clock(self):
        """ No-op

        @return int: 0
        """
        return 0
