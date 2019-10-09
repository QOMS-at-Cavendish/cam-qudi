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

class StagecontrolLogic(GenericLogic):
    """ Logic module for moving mechanical stage.
    """

    stagehardware = Connector(interface='MotorInterface')

    def __init__(self, config, **kwargs):
        """ Create logic object

          @param dict config: configuration in a dict
          @param dict kwargs: additional parameters as a dict
        """
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Prepare logic module for work.
        """
        self._stage_hw = self.stagehardware()
        print("Logic module activated")
        pass
        
    def on_deactivate(self):
        """ Deactivate modeule.
        """
        pass

    def stage_logic_method(self): 
        print(self._stage_hw.get_status())