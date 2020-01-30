# -*- coding: utf-8 -*-

"""
A module for reading an Xbox 360 controller via joystick interface.

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

from core.module import Connector
from core.configoption import ConfigOption
from logic.generic_logic import GenericLogic
from qtpy import QtCore
import numpy as np


class XboxLogic(GenericLogic):
    """ Poll Xbox hardware controller using joystick interface.
    
    Emits sigJoystickMoved and sigButtonPress in response to 
    gamepad inputs.

    Example configuration
        xboxlogic:
            module.Class: 'xbox_logic.XboxLogic'
            poll_freq: 100
            dead_zone: 0.2
            connect:
                hardware: dummy_joystick
    """

    # declare connectors
    hardware = Connector(interface='JoystickInterface')

    # Polling frequency
    _poll_freq = ConfigOption('poll_freq', 100)

    # Analogue stick dead-zone
    _dead_zone = ConfigOption('dead_zone', 0.2)

    # Public signals
    sigJoystickMoved = QtCore.Signal(dict)  # Analogue stick moved
    sigButtonPress = QtCore.Signal(str) # Button pressed

    _enabled = False

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.poll_joystick)
        self.start_poll()

    def on_deactivate(self):
        """ Perform required deactivation.
        """
        self.stop_poll()

    def start_poll(self):
        self._enabled = True
        self._prev_btn_state = {}
        self._prev_joystick_state = {
            'x_left':0.0,
            'y_left':0.0,
            'x_right':0.0,
            'y_right':0.0
        }
        self._timer.start(1000 / self._poll_freq)
    
    def stop_poll(self):
        self._enabled = False

    def poll_joystick(self):
        """ Poll gamepad for button and joystick states """
        if not self._enabled:
            return
        
        state = self.hardware().get_state()

        for button, pressed_state in state['buttons'].items():
            if pressed_state:
                # If button state is True (i.e. currently pressed)
                if not button in self._prev_btn_state:
                    # Check we haven't already emitted signal
                    self.sigButtonPress.emit(button)
                    self._prev_btn_state[button] = True
            else:
                if button in self._prev_btn_state:
                    # Remove previous button state flag from dict
                    self._prev_btn_state.pop(button,None)
        
        # Do joystick stuff

        # Left joystick on gamepad
        x_left = state['axis']['left_horizontal']
        y_left = state['axis']['left_vertical']

        x_left, y_left = self._calculate_dead_zone(x_left, y_left)

        #Right joystick on gamepad
        x_right = state['axis']['right_horizontal']
        y_right = state['axis']['right_vertical']

        x_right, y_right = self._calculate_dead_zone(x_right, y_right)

        if self._prev_joystick_state['x_left'] == x_left and \
           self._prev_joystick_state['y_left'] == y_left and \
           self._prev_joystick_state['x_right'] == x_right and \
           self._prev_joystick_state['y_right'] == y_right:
            # If current joystick state is exactly the same as before, do nothing.
            pass
        else:
            # Otherwise store joystick state and emit signal
            joystick_state = {
                'x_left':x_left,
                'y_left':y_left,
                'x_right':x_right,
                'y_right':y_right
            }
            self.sigJoystickMoved.emit(joystick_state)
            self._prev_joystick_state = joystick_state

        self._timer.start(1000/self._poll_freq)

    def _calculate_dead_zone(self,x,y):
        """ Calculate circular dead-zone around centre of analogue stick
            @param float x: raw x-axis value
            @param float y: raw y-axis value
            @return tuple: corrected x and y values
        """
        # Create circular dead-zone around centre
        magnitude = np.sqrt(x**2 + y**2)
        if magnitude < self._dead_zone:
            # If inside dead-zone set x and y to zero
            corrected_x = 0
            corrected_y = 0
        else:
            # Otherwise calculate corrected x, y values accounting for dead-zone
            magnitude_corrected = magnitude - self._dead_zone
            corrected_x = (x / magnitude) * magnitude_corrected
            corrected_y = (y / magnitude) * magnitude_corrected

            # Renormalise
            corrected_x = corrected_x * (1+self._dead_zone)
            corrected_y = corrected_y * (1+self._dead_zone)

        return corrected_x, corrected_y