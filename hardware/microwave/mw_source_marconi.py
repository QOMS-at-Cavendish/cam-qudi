# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware file to control Marconi 2023/2024.

John Jarman <jcj27@cam.ac.uk>

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

import visa
import numpy as np
import time

from core.module import Base
from core.configoption import ConfigOption
from interface.microwave_interface import MicrowaveInterface
from interface.microwave_interface import MicrowaveLimits
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge


class MicrowaveMarconi(Base, MicrowaveInterface):
    """ Hardware control file for Marconi Devices.

    The hardware file was tested using the model 2024.

    Example config for copy-paste:

    mw_source_marconi:
        module.Class: 'microwave.mw_source_marconi.MicrowaveMarconi'
        gpib_resource: 'GPIB0::22::INSTR'
        gpib_timeout: 100 # in seconds

    """

    _gpib_resource = ConfigOption('gpib_resource', 'GPIB0::22::INSTR', missing='warn')
    _gpib_timeout = ConfigOption('gpib_timeout', 100, missing='warn')

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self.rm = visa.ResourceManager()
        self._connection = self.rm.open_resource(
            resource_name=self._gpib_resource,
            timeout=self._gpib_timeout)

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """

        self._connection.close()
        self.rm.close()
        return

    def off(self):
        """ Switches off any microwave output.

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('RFLV:OFF')
        return 0

    def get_status(self):
        """
        Gets the current status of the MW source, i.e. the mode (cw, list or sweep) and
        the output state (stopped, running)

        @return str, bool: mode ['cw', 'list', 'sweep'], is_running [True, False]
        """
        mode_query = self._query('CFRQ?')['MODE']
        if mode_query == 'FIXED':
            mode = 'cw'
        elif mode_query == 'SWEPT':
            mode = 'sweep'
        else:
            raise ValueError('Unrecognised mode {} read from Marconi'.format(mode_query))

        is_running = 'ON' in self._query('RFLV?')

        return mode, is_running

    def get_power(self):
        """ Gets the microwave output power.

        @return float: the power set at the device in dBm
        """
        
        return float(self._query('RFLV?')['VALUE'])

    def get_frequency(self):
        """ Gets the frequency of the microwave output.

        @return float: frequency (in Hz), which is currently set for this device
        """
        return float(self._query('CFRQ?')['VALUE'])

    def cw_on(self):
        """ Switches on any preconfigured microwave output.

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('RFLV:ON')
        return 0

    def set_cw(self, freq=None, power=None, useinterleave=None):
        """ Sets the MW mode to cw and additionally frequency and power

        @param float freq: frequency to set in Hz
        @param float power: power to set in dBm
        @param bool useinterleave: If this mode exists you can choose it.

        @return int: error code (0:OK, -1:error)

        Interleave option is used for arbitrary waveform generator devices.
        """
        self._connection.write('CFRQ:MODE FIXED')
        
        if freq is not None:
            self.set_frequency(freq)
        if power is not None:
            self.set_power(power)
        if useinterleave is not None:
            self.log.warning("Interleave mode not implemented")
        
        return freq, power, 'cw'

    def list_on(self):
        """ Switches on the list mode.

        @return int: error code (1: ready, 0:not ready, -1:error)
        """
        raise NotImplementedError('List mode not implemented for Marconi')

    def set_list(self, freq=None, power=None):
        """ Unimplemented

        @param list freq: list of frequencies in Hz
        @param float power: MW power of the frequency list in dBm

        """
        raise NotImplementedError('List mode not implemented for Marconi')

    def reset_listpos(self):
        """ Reset of MW List Mode position to start from first given frequency

        @return int: error code (0:OK, -1:error)
        """
        raise NotImplementedError('List mode not implemented for Marconi')

    def sweep_on(self):
        """ Switches on the list mode.

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('RFLV:ON')
        return 0

    def set_sweep(self, start, stop, step, power=None):
        """

        @param start:
        @param stop:
        @param step:
        @param power:
        @return:
        """
        self._connection.write('CFRQ:MODE SWEPT')
        self._connection.write('SWEEP:MODE CONT')
        self._connection.write('SWEEP:TYPE LIN')
        self._connection.write('SWEEP:TRIG STEP')

        self._connection.write('SWEEP:START {:.6f} HZ'.format(start))
        self._connection.write('SWEEP:STOP {:.6f} HZ'.format(stop))
        self._connection.write('SWEEP:INC {:.6f} HZ'.format(step))

        if power is not None:
            self.set_power(power)

        return start, stop, step, power, 'sweep'

    def reset_sweeppos(self):
        """ Reset of MW List Mode position to start from first given frequency

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('SWEEP:RESET')
        return 0

    def set_ext_trigger(self, pol, timing):
        """ Set the external trigger for this device with proper polarization.

        @param str pol: polarisation of the trigger (basically rising edge or
                        falling edge)
        @param float timing: estimated time between triggers

        @return object, float: current trigger polarity [TriggerEdge.RISING, TriggerEdge.FALLING],
            trigger timing
        """
        return TriggerEdge.RISING, timing

    def trigger(self):
        """ Trigger the next element in the list or sweep mode programmatically.

        @return int: error code (0:OK, -1:error)
        """
        self._connection.write('*TRG')
        return 0

    def get_limits(self):
        limits = MicrowaveLimits()
        limits.supported_modes = (MicrowaveMode.CW, MicrowaveMode.SWEEP)

        limits.min_frequency = 9.0e3
        limits.max_frequency = 2.4e9

        limits.min_power = -144
        limits.max_power = -13

        limits.list_minstep = 0.1
        limits.list_maxstep = 3.0e9
        limits.list_maxentries = 4000

        limits.sweep_minstep = 0.1
        limits.sweep_maxstep = 3.0e9
        limits.sweep_maxentries = 10001

        return limits

    def set_power(self, power=0.):
        """ Sets the microwave output power.

        @param float power: the power (in dBm) set for this device

        @return int: error code (0:OK, -1:error)
        """
        if power < self.get_limits().min_power or power > self.get_limits().max_power:
            self.log.error("Power {} dBm out of range")
            return -1

        self._connection.write('RFLV:VALUE {:.2f} DBM'.format(power))
        return 0

    def set_frequency(self, freq=None):
        """ Sets the frequency of the microwave output.

        @param float freq: the frequency (in Hz) set for this device

        @return int: error code (0:OK, -1:error)
        """
        if freq < self.get_limits().min_frequency or freq > self.get_limits().max_frequency:
            self.log.error("Frequency {} Hz out of range".format(freq))
            return -1
        self._connection.write('CFRQ:VALUE {:.6f} HZ'.format(freq))
        return 0

    def _query(self, query):
        """
        Queries the hardware and parses the returned string into a dict

        @param str query: Query command to send to hardware

        @return dict: key:value pairs corresponding to hardware response
        """
        q = self._connection.query(query)
        q = q.split(':')[2]
        q_list = q.split(';')
        q_dict = {}
        for item in q_list:
            key, val = item.split(' ')
            q_dict[key.strip()] = val.strip()
        return q_dict
