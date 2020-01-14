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

from core.module import Base
from core.configoption import ConfigOption
from interface.slow_counter_interface import SlowCounterInterface
from interface.slow_counter_interface import SlowCounterConstraints, CountingMode

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

        if self.startstop_enabled:
            self.set_delays(self._default_delays)
            self.set_histogram_params(
                self._default_binwidth, self._default_bincount)

        # Set qutau exposure time
        self.set_up_clock(clock_frequency=self._default_clock)      

    def on_deactivate(self):
        """ Shuts down qutau on module deactivation.
        """
        self.qutau.deInit()

    ################################
    # Start-stop histogram functions
    ################################

    def enable_histogram(self, enable=True):
        """ Enables histogram calculations

        @param bool enable: Enable/disable (True/False)
        """
        self.qutau.enableStartStop(enable)
        self.startstop_enabled = enable

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
        hist[:, 0] = np.linspace(0, bin_time*data['binCount'], data['binCount'])

        if normalise:
            hist[:, 1] = data['data'] / data['count']
        else:
            hist[:, 1] = data['data']

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
        c.min_count_frequency = 1/65.5

        c.counting_mode = [CountingMode.CONTINUOUS]

        return c

    def set_up_clock(self, clock_frequency = None, clock_channel = None):
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

    def get_counter(self, samples=None):
        """ Returns the current counts per second of the counter.

        counter_logic expects this function to block execution until new counts
        are available.

        This function therefore blocks execution until both 1/clock_frequency 
        time has passed since the last call of this function and the qutau
        reports that it has updated its internal counters.

        @param int samples: Optional: read this many samples from the counter

        @return numpy.array of photon counts per second for each channel
                (dtype=uint32) <- not sure if this is necessary but it is
                                    specified in slow_counter_interface
        """
        delay = 1/self.clock_frequency
        current_time = time.monotonic()
        if current_time - self.last_called_time < delay:
            # Block execution if not enough time has passed since last call
            time.sleep(self.last_called_time + delay - current_time)

        self.last_called_time = time.monotonic()

        # Get data from qutau, or spin if there hasn't been an update yet.
        data = None
        num_updates = 0
        while num_updates == 0:
            r = self.qutau.getCoincCounters()
            data = r['data']
            num_updates = r['updates']
            if num_updates == 0:
                time.sleep(1e-3)

        if self._sum_all_channels:
            # Sum all channels together and return 1 count trace
            output_sum = 0
            for channel in self.enabled_channels:
                output_sum += data[channel-1] * self.clock_frequency
            output_data = np.zeros((1,1), dtype=np.uint32)
            output_data[0,0] = output_sum
            return output_data
        else:
            # Restrict data to enabled channels and return all separately
            output_data = np.zeros((len(self.enabled_channels),1), dtype=np.uint32)
            for channel in self.enabled_channels:
                output_data[channel-1, 0] = data[channel-1] * self.clock_frequency
            return output_data

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