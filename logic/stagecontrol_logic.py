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

import numpy as np
import functools

# Decorator to ensure thread locking is done correctly
def thread_lock(func):
    @functools.wraps(func)
    def check(self,*args,**kwargs):
        with self.threadlock:
            func(self,*args,**kwargs)
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

    def start_jog(self,axis,direction):
        self.stage_hw.move_stepper(axis,'cont',direction)
    
    def step(self,axis,direction,steps):
        self.stage_hw.move_stepper(axis,'step',direction,steps=steps)

    def stop(self):
        self.stage_hw.stop_all()

    def set_axis_params(self,axis,volt,freq):
        self.stage_hw.set_step_amplitude(axis,volt)
        self.stage_hw.set_step_freq(axis,freq)

    def optimise_z(self,steps):
        """Perform z sweep while recording count rate to optimise focus"""

        # Initialise variables
        self.sweep_length = steps
        self.sweep_counts = []
        self.current_step = -steps
        self.abort = False

        # Move to end of search range
        self.stage_hw.move_stepper('z','step','out',steps=steps)

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
            counts = self.counter_logic.countdata_smoothed[-1, -2]
            self.sweep_counts.append(counts)

            # Emit event that can be caught by GUI to update
            self.sigCountDataUpdated.emit()

            if self.current_step < self.sweep_length:
                # If not already at end of sweep move stage 1 step
                self.stage_hw.move_stepper('z','step','in',steps=1)
                self.current_step += 1

                # Start timer for next iteration
                QtCore.QTimer.singleShot(self.optimise_delay, self._optimisation_step)
            else:
                # Sweep done - stop counter
                self.counter_logic.stopCount()

                # Find index of maximum point, and calculate how far back to move
                max_index = np.argmax(self.sweep_counts)
                steps = 2*self.sweep_length - max_index

                # Do the movement
                self.stage_hw.move_stepper('z','step','out',steps=steps)
                self.sigOptimisationDone.emit()

        else:
            self.log.error("Sweep aborted: counter unexpectedly stopped.")

    @thread_lock
    def abort_optimisation(self):
        self.abort = True
