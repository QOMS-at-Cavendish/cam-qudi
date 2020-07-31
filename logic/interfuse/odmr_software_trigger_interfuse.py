# -*- coding: utf-8 -*-

"""
Interfuse to perform ODMR scans using software frequency sweeping on the MW
source. Provides and expects ODMRCounterInterface and MicrowaveInterface.

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

from core.connector import Connector
from logic.generic_logic import GenericLogic
from interface.odmr_counter_interface import ODMRCounterInterface
from interface.microwave_interface import MicrowaveInterface
from interface.microwave_interface import TriggerEdge

class ODMRSoftwareTriggerInterfuse(GenericLogic, ODMRCounterInterface,
                                    MicrowaveInterface):
    """
    Interfuse to enable software triggering of a microwave source.

    This interfuse connects the ODMR logic with a ODMR counter and MW device.
    """

    odmrcounter = Connector(interface='ODMRCounterInterface')
    microwave = Connector(interface='MicrowaveInterface')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_activate(self):
        self._microwave = self.microwave()
        self._counter = self.odmrcounter()

    def on_deactivate(self):
        pass

    ######################
    # ODMRCounterInterface
    ######################

    # Re-implemented methods
    #=======================

    def count_odmr(self, length = 100):
        """ Sweeps the microwave and returns the counts on that sweep.

        @param int length: length of microwave sweep in pixel

        @return float[]: the photon counts per second
        """

        counts = np.zeros((len(self.get_odmr_channels()), length))

        for i in range(length):
            # Get ODMR counts - raw_count contains a list of 1-length numpy
            # arrays, one per ODMR channel
            error, raw_count = self._counter.count_odmr(length=1)

            if error:
                self.log.error('Error acquiring ODMR count data')
                return True, counts

            # Convert the 1-length numpy arrays to scalars and store in output
            # array as [channel, counts]
            counts[:, i] = [ct[0] for ct in raw_count]
            
            # Trigger next frequency in the sweep
            self.trigger()

        return False, counts

    # Pass-through methods
    #=====================

    def set_up_odmr_clock(self, *args, **kwargs):    
        return self._counter.set_up_odmr_clock(*args, **kwargs)

    def set_up_odmr(self, *args, **kwargs):
        return self._counter.set_up_odmr(*args, **kwargs)

    def close_odmr(self):
        return self._counter.close_odmr()

    def close_odmr_clock(self):
        return self._counter.close_odmr_clock()

    def get_odmr_channels(self):
        return self._counter.get_odmr_channels()

    def set_odmr_length(self, *args, **kwargs):
        return self._counter.set_odmr_length(*args, **kwargs)

    @property
    def lock_in_active(self):
        return self._counter.lock_in_active
    
    @lock_in_active.setter
    def lock_in_active(self, val):
        self._counter.lock_in_active = val
    
    @property
    def oversampling(self):
        return self._counter._oversampling

    @oversampling.setter
    def oversampling(self, val):
        self._counter._oversampling = val

    ####################
    # MicrowaveInterface
    ####################

    # Pass-through methods
    #=====================

    def trigger(self):
        return self._microwave.trigger()

    def off(self):
        return self._microwave.off()

    def get_status(self):
        return self._microwave.get_status()

    def get_power(self):
        return self._microwave.get_power()

    def get_frequency(self):
        return self._microwave.get_frequency()

    def cw_on(self):
        return self._microwave.cw_on()

    def set_cw(self, *args, **kwargs):
        return self._microwave.set_cw(*args, **kwargs)

    def list_on(self):
        return self._microwave.list_on()

    def set_list(self, *args, **kwargs):
        return self._microwave.set_list(*args, **kwargs)

    def reset_listpos(self):
        return self._microwave.reset_listpos()

    def sweep_on(self):
        return self._microwave.sweep_on()

    def set_sweep(self, *args, **kwargs):
        return self._microwave.set_sweep(*args, **kwargs)

    def reset_sweeppos(self):
        return self._microwave.reset_sweeppos()

    def set_ext_trigger(self, *args, **kwargs):
        return self._microwave.set_ext_trigger(*args, **kwargs)

    def get_limits(self):
        return self._microwave.get_limits()
