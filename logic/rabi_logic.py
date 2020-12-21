# -*- coding: utf-8 -*-
"""
Logic module for running a Rabi sweep with the Pulse Blaster card.

Work in progress: currently interacts directly with hardware etc -
doesn't follow the Qudi model at all.

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
from core.configoption import ConfigOption
from logic.generic_logic import GenericLogic
from qtpy import QtCore

import threading
import numpy as np
import spincore
import PyDAQmx as daq
import fysom
import random
import time
import os

from contextlib import contextmanager

class RabiLogic(GenericLogic):

    savelogic = Connector(interface='SaveLogic')
    optimizerlogic = Connector(interface='OptimizerLogic')
    scannerlogic = Connector(interface='ConfocalLogic')

    counter = ConfigOption('counter', '/Dev1/Ctr3')
    apd_terminal = ConfigOption('apd_terminal', '/Dev1/PFI0')
    gate_terminal = ConfigOption('gate_terminal', '/Dev1/PFI12')
    samples = ConfigOption('samples', 50000)

    spincore_lock = threading.Lock()

    _start = QtCore.Signal()

    def on_activate(self):
        self.stop_flag = threading.Event()
        self.autosave = True
        self.task = None
        self.mw_length_list = [122, 302, 182,  50, 392, 140, 452, 344, 248, 212,  38, 254, 230,
                               116, 296, 416, 326, 164, 386,  62, 404,  86,  80, 380,  68, 218,
                               482, 446, 176, 272, 320, 314, 152,  74, 458,  32, 398, 374,
                               104,  44, 284, 134, 200, 332, 188, 128, 170, 350, 476,  20, 278,
                               470, 290, 110, 362, 146, 440, 194, 260, 428,  98, 368, 158, 410,
                               356, 464, 308, 434, 266, 224,  92, 338, 422, 242, 206, 236,
                               26,  56, 500]
        with self.acquire_spincore_lock():
            spincore.pb_init()
            spincore.pb_core_clock(500)
            spincore.pb_close()

        self.save_path = 'C:\\Data\\rabi.npz'

        self._start.connect(self._start_experiment)
    
    def on_deactivate(self):
        self.stop()
        QtCore.QObject.disconnect(self._start)

    def start(self):
        self.stop_flag.clear()
        self._start.emit()

    def stop(self):
        self.stop_flag.set()

    def set_mw_lengths(self, mw_length_list, scramble=True):
        if self.module_state() == 'locked':
            self.log.error('Could not set MW length list: module busy')
        if scramble:
            random.shuffle(mw_length_list)
        self.mw_length_list = mw_length_list
        return self.mw_length_list

    def save_data(self):
        results_np = np.array(self.all_results)
        np.savez(self.save_path, results=results_np, time=self.mw_length_list)

    def _set_up_daq(self):
        # DAQ terminal configuration
        if self.task is not None:
            daq.DAQmxClearTask(self.task)
        self.task = daq.TaskHandle()
        daq.DAQmxCreateTask('PulsedCounter', daq.byref(self.task))

        # This task measures the semi-period of an input signal
        # in terms of the number of photon ticks arriving at
        # another input. Alternating samples therefore indicate
        # the number of counts arriving at 'high' and 'low' periods
        # of the input signal.

        # Configure semi-period measurement channel
        daq.DAQmxCreateCISemiPeriodChan(
            self.task,
            self.counter,
            'APD',
            0,    # Min counts
            3e7,  # Max counts
            daq.DAQmx_Val_Ticks,
            None
        )

        # Configure input terminal for gate signal
        daq.DAQmxSetCISemiPeriodTerm(
            self.task,
            self.counter,
            self.gate_terminal)

        # Configure input terminal for photon counts
        daq.DAQmxSetCICtrTimebaseSrc(
            self.task,
            self.counter,
            self.apd_terminal)

        # Configure number of samples
        daq.DAQmxCfgImplicitTiming(
            self.task,
            daq.DAQmx_Val_FiniteSamps,
            self.samples)

        # Read samples from beginning of acquisition, do not overwrite
        daq.DAQmxSetReadRelativeTo(self.task, daq.DAQmx_Val_CurrReadPos)

        # Do not read first sample
        daq.DAQmxSetReadOffset(self.task, 0)

        # Unread data in buffer is not overwritten
        daq.DAQmxSetReadOverWrite(
            self.task,
            daq.DAQmx_Val_DoNotOverwriteUnreadSamps)

    def _optimize_position(self):
        self.optimizerlogic().start_refocus(caller_tag='Rabi')
    
        # Wait for it to start
        time.sleep(0.5)

        # Wait for optimisation to finish
        while self.optimizerlogic().module_state() == 'locked':
            time.sleep(0.1)
            
        time.sleep(0.1)
        self.scannerlogic().set_position('Rabi',
                            x=self.optimizerlogic().optim_pos_x,
                            y=self.optimizerlogic().optim_pos_y,
                            z=self.optimizerlogic().optim_pos_z)

    @QtCore.Slot()
    def _start_experiment(self):
        # run Rabi experiment
        try:
            self.module_state.lock()
            self._update_save_path()
            
            self._set_up_daq()
            self.log.info('Starting Rabi')

            sweep_count = 0
            optimiser_counter = 0
            self.all_results = list()

            while not self.stop_flag.is_set():
                self.log.debug('Sweeps done: {}'.format(sweep_count))
                self.all_results.append(self._rabi_sweep())
                
                if optimiser_counter == 1:
                    if self.autosave:
                        self.save_data()
                    self.set_high(0b11)
                    self._optimize_position()
                    optimiser_counter = 0
                with self.acquire_spincore_lock():
                    spincore.pb_init()
                    spincore.pb_stop()
                    spincore.pb_close()

                sweep_count += 1
                optimiser_counter += 1
        except fysom.FysomError:
            self.log.error('Could not start Rabi: module busy')
        finally:
            self.module_state.unlock()
            if self.task is not None:
                daq.DAQmxClearTask(self.task)
                self.task = None

            self.log.info('Rabi stopped')

    def _rabi_sweep(self):
        results = np.zeros((len(self.mw_length_list), 2))
    
        for idx, mw_length in enumerate(self.mw_length_list):
            self._prog_rabi(mw_length)
            results[idx, :] = self._run_rabi()
    
        return results

    def _prog_rabi(self, mw_length):
        # Set pulse durations
        apd_time   = 1000
        init_time = 6e3
        mw_buffer1 = 600 #make this long enough to account for laser delay
        mw_buffer2 = 50
        max_t = np.amax(self.mw_length_list)
        
        # Define Channels 
        laser_chan = 0b0001
        apd_chan   = 0b0010
        mw_chan    = 0b0100
        daq_chan   = 0b1000
        dummy_chan = 0b0000

        # Pulse Sequence
        
        laser_pulse1   = (0,
                        init_time,
                        laser_chan)
        
        mw_pulse      = (init_time + mw_buffer1,
                        mw_length, 
                        mw_chan)
        
        apd_pulse = (init_time + mw_buffer1 + mw_length + mw_buffer2,
                    apd_time, 
                    apd_chan)
        
        laser_pulse2  = (init_time + mw_buffer1 + mw_length + mw_buffer2,
                        init_time,
                        laser_chan)
        
        
        dummy_pulse1   = (init_time*2 + mw_buffer1 + mw_length + mw_buffer2,
                        max_t-mw_length,
                        dummy_chan)
        
        laser_pulse3 = (init_time*2 + mw_buffer1 + mw_length + mw_buffer2 + (max_t-mw_length),
                        init_time,
                        laser_chan)
        
        
        apd_ref_pulse = (init_time*3 + 2*mw_buffer1 + 2*mw_length + 2*mw_buffer2 + (max_t-mw_length),
                        apd_time,
                        apd_chan)
        
        laser_pulse4 = (init_time*3 + 2*mw_buffer1 + 2*mw_length + 2*mw_buffer2 + (max_t-mw_length),
                    init_time,
                    laser_chan)
        
        dummy_pulse2 = (init_time*4 + 2*mw_buffer1 + 2*mw_length + 2*mw_buffer2 + (max_t-mw_length),
                    max_t-mw_length,
                    dummy_chan)
        
        daq_pulse     = (init_time*3 + mw_buffer1 + mw_length + mw_buffer2 + (max_t-mw_length),
                        mw_buffer1 + mw_length + mw_buffer2 + init_time + (max_t-mw_length),
                        daq_chan)
        

        # Send pulse sequence instructions to pulse blaster
        instr = spincore.pulse_to_instructions((apd_pulse, 
                                                laser_pulse1, 
                                                laser_pulse2,
                                                laser_pulse3,
                                                laser_pulse4,
                                                daq_pulse,
                                                mw_pulse,
                                                apd_ref_pulse,
                                            dummy_pulse1,
                                            dummy_pulse2))
        spincore.program_pulse_blaster(instr)
        return instr

    def _run_rabi(self):
        timeout = 20
        count_data = np.empty((self.samples), dtype=np.uint32)  #empty array for data

        daq.DAQmxStartTask(self.task)   #Start the task

        # Start Blaster
        with self.acquire_spincore_lock():
            if spincore.pb_init() != 0:
                raise Exception('Error starting Pulse Blaster')
            spincore.pb_start()
            spincore.pb_close()

        n_read_samples = daq.int32()

        # Read out result (waits until done)
        daq.DAQmxReadCounterU32(
            self.task,
            self.samples,
            timeout,
            count_data,
            self.samples,
            daq.byref(n_read_samples),
            None)

        # Stop Blaster
        daq.DAQmxStopTask(self.task)

        with self.acquire_spincore_lock():
            spincore.pb_init()
            spincore.pb_stop()
            spincore.pb_close()

        # Get sig and ref
        sig = np.array(count_data[:n_read_samples.value:2], dtype=np.int)
        ref = np.array(count_data[1:n_read_samples.value:2], dtype=np.int)

        return np.sum(sig), np.sum(ref)

    def set_high(self, channels):
        on = 0xE00000
        with self.acquire_spincore_lock():
            if spincore.pb_init() != 0:
                raise Exception('Error starting Pulse Blaster')
            try:
                spincore.pb_core_clock(500)
                spincore.pb_start_programming(0)
                spincore.pb_inst(channels|on, spincore.Inst.BRANCH, 0, 100)
                spincore.pb_stop_programming()
                spincore.pb_start()
            finally:
                spincore.pb_close()
        self.log.debug('Set channel states: {:04b}'.format(channels))

    @contextmanager
    def acquire_spincore_lock(self):
        result = self.spincore_lock.acquire(timeout=5)
        if result:
            try:
                yield
            finally:
                self.spincore_lock.release()
        else:
            raise TimeoutError('Spincore hardware lock timeout')

    def _update_save_path(self):
        self.save_path = os.path.join(self.savelogic().get_path_for_module('Rabi'),
                         self.savelogic().get_filename(filelabel='Rabi', 
                                                       extension='.npz'))
        self.log.info('Saving Rabi data to: ' + self.save_path)