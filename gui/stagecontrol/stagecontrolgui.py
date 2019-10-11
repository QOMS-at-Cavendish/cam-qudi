# -*- coding: utf-8 -*-

"""
This file contains a Qudi gui module for stage movements.

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

"""

import os
import numpy as np
from itertools import cycle
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import uic
import functools

from core.connector import Connector
from gui.guibase import GUIBase

# Decorator to catch ValueError exceptions in functions which cast UI input text to other types.
def value_error_handler(func):
    @functools.wraps(func)
    def check(self,*args,**kwargs):
        try:
            func(self,*args,**kwargs)
        except ValueError:
            self.log.warn("ValueError when converting UI input - check input values")
    return check

class StagecontrolMainWindow(QtWidgets.QMainWindow):

    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'stagecontrol.ui')

        # Load it
        super(StagecontrolMainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()

class StagecontrolGui(GUIBase):

    # declare connectors
    stagecontrollogic = Connector(interface='StagecontrolLogic')

    sigStartCounter = QtCore.Signal()
    sigStopCounter = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """

        self.stagecontrol_logic = self.stagecontrollogic()

        # Create main window instance
        self._mw = StagecontrolMainWindow()

        # Connect UI events

        # Direction jog buttons
        self._mw.stop_btn.clicked.connect(self.stop_movement)

        self._mw.x_left_btn.pressed.connect(self.x_left)
        self._mw.x_right_btn.pressed.connect(self.x_right)
        self._mw.y_up_btn.pressed.connect(self.y_up)
        self._mw.y_down_btn.pressed.connect(self.y_down)
        self._mw.z_up_btn.pressed.connect(self.z_up)
        self._mw.z_down_btn.pressed.connect(self.z_down)

        self._mw.x_left_btn.released.connect(self.direction_btn_released)
        self._mw.x_right_btn.released.connect(self.direction_btn_released)
        self._mw.y_up_btn.released.connect(self.direction_btn_released)
        self._mw.y_down_btn.released.connect(self.direction_btn_released)
        self._mw.z_up_btn.released.connect(self.direction_btn_released)
        self._mw.z_down_btn.released.connect(self.direction_btn_released)

        # Parameter set buttons
        self._mw.set_z_btn.clicked.connect(self.set_z_params)

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        # FIXME: !
        """ Deactivate the module
        """
        self._mw.close()

    #Button callbacks
    def stop_movement(self):
        """Stop button callback"""
        self.stagecontrol_logic.stop()

    def x_left(self):
        """Direction button callback"""
        print("x-axis left")

    def x_right(self):
        """Direction button callback"""
        print("x-axis right")

    def y_up(self):
        """Direction button callback"""
        print("y-axis up")

    def y_down(self):
        """Direction button callback"""
        print("y-axis down")

    def z_up(self):
        """Direction button callback"""
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('z','in')
        else:
            self.stagecontrol_logic.step('z','in',1)

    def z_down(self):
        """Direction button callback"""
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('z','out')
        else:
            self.stagecontrol_logic.step('z','out',1)

    def direction_btn_released(self):
        """Direction button release callback"""
        self.stop_movement()

    @value_error_handler
    def set_z_params(self,msg):
        freq = float(self._mw.z_freq.text())
        volt = float(self._mw.z_voltage.text())
        self.stagecontrol_logic.set_axis_params('z',volt,freq)