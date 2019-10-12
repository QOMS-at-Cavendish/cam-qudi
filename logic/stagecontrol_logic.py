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

    def on_activate(self):
        """ Prepare logic module for work.
        """
        self.stage_hw = self.stagehardware()
        
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

    def optimise_z(self,steps,step_amplitude):
        """Perform z sweep while recording count rate to optimise focus"""
        self.stage_hw.set_step_amplitude('z',step_amplitude)

        # Move to end of search range
        self.stage_hw.move_stepper('z','step','out',steps=steps)

        # Start QTimer