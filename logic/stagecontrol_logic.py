# -*- coding: utf-8 -*-
"""
Stage controller

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

from logic.generic_logic import GenericLogic
from collections import OrderedDict
from core.connector import Connector
from qtpy import QtCore

from core.util.mutex import Mutex

from interface.stepper_interface import StepperError, StepperOutOfRange, AxisError, AxisConfigError

import numpy as np
import functools

# Decorator to ensure thread locking is done correctly
def thread_lock(func):
    @functools.wraps(func)
    def check(self,*args,**kwargs):
        with self.threadlock:
            return func(self,*args,**kwargs)
    return check

# Decorator to throw away exceptions from hardware for non-critical operations
def hwerror_handler(func):
    @functools.wraps(func)
    def check(self,*args,**kwargs):
        try:
            return func(self,*args,**kwargs)
        except StepperError as err:
            self.log.error(err)
    return check

class StagecontrolLogic(GenericLogic):
    """ Logic module for moving Attocube.
    """

    stagehardware = Connector(interface='StepperInterface')
    counterlogic = Connector(interface='CounterLogic')

    # Signals to trigger GUI updates
    sigOptimisationDone = QtCore.Signal()
    sigCountDataUpdated = QtCore.Signal()

    def __init__(self, config, **kwargs):
        """ Create logic object

          @param dict config: configuration in a dict
          @param dict kwargs: additional parameters as a dict
        """
        super().__init__(config=config, **kwargs)

        self.threadlock = Mutex()

    def on_activate(self):
        """ Prepare logic module for work.
        """
        self.stage_hw = self.stagehardware()
        self.counter_logic = self.counterlogic()

        # Delay used between requesting stepper motion and requesting count-rate while optimising z-axis.
        # TODO: Make this a configuration option.
        self.optimise_delay = 100
        self.abort = False
        
    def on_deactivate(self):
        """ Deactivate module.
        """
        pass

    @hwerror_handler
    def start_jog(self, axis, direction):
        self.stage_hw.start_continuous_motion(axis, direction)
    
    @hwerror_handler
    def step(self, axis, steps):
        self.stage_hw.move_steps(axis, steps)

    @hwerror_handler
    def stop(self):
        self.stage_hw.stop_all()

    @hwerror_handler
    def set_axis_params(self,axis,volt,freq):
        self.stage_hw.set_axis_config(axis, 
            {
            'step-voltage':volt,
            'frequency':freq
            })

    @hwerror_handler
    def get_axis_params(self,axis):
        volt = self.stage_hw.get_axis_config(axis, 'step-voltage')
        freq = self.stage_hw.get_axis_config(axis, 'frequency')
        return volt, freq

    def optimise_z(self,steps):
        """Perform z sweep while recording count rate to optimise focus"""

        # Initialise variables
        self.sweep_length = steps
        self.sweep_counts = []
        self.current_step = -steps
        self.abort = False

        # Move to end of search range
        try:
            self.stage_hw.move_steps('z', steps=-steps)
        except StepperError as err:
            self.log.error('Aborting sweep due to hardware error: {}'.format(err))
            return

        # Start counter running
        self.counter_logic.startCount()

        # Start QTimer (first delay twice as long to allow counter extra time to start)
        QtCore.QTimer.singleShot(self.optimise_delay*2, self._optimisation_step)
    
    @thread_lock
    def _optimisation_step(self):
        """Function called when optimise_timer expires."""
        if self.abort:
            self.counter_logic.stopCount()
            return

        # Check if counter logic module is locked (i.e. if counter is running)
        if self.counter_logic.module_state() == 'locked':
            # Get last count value and store
            counts = self.counter_logic.countdata_smoothed[-2, -2]
            self.sweep_counts.append(counts)

            # Emit event that can be caught by GUI to update
            self.sigCountDataUpdated.emit()

            if self.current_step < self.sweep_length:
                # If not already at end of sweep move stage 1 step
                try:
                    self.stage_hw.move_steps('z', 1)
                except StepperError as err:
                    self.log.error("Aborting sweep due to hardware error: {}".format(err))
                    self.counter_logic.stopCount()
                    return

                self.current_step += 1

                # Start timer for next iteration
                QtCore.QTimer.singleShot(self.optimise_delay, self._optimisation_step)
            else:
                # Sweep done - stop counter
                self.counter_logic.stopCount()

                # Find index of maximum point, and calculate how far back to move
                max_index = np.argmax(self.sweep_counts)
                steps = 2*self.sweep_length - max_index
                self.log.debug('Optimum at {} steps from current position'.format(steps))

                # Do the movement
                try:
                    if steps > 0:
                        # Move stage if needed (note steps=0 seems to give continuous motion)
                        self.stage_hw.move_steps('z', -steps)
                except StepperError as err:
                    self.log.error('Could not return stage to optimum position due to hardware error: {}'.format(err))
                self.sigOptimisationDone.emit()

        else:
            self.log.error("Sweep aborted: counter unexpectedly stopped.")

    @thread_lock
    def abort_optimisation(self):
        self.abort = True
