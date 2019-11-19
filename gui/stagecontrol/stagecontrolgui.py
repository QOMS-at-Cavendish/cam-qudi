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
import pyqtgraph as pg
import functools

from qtwidgets.joystick import Joystick

from gui.colordefs import QudiPalettePale as palette

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

        # Set up counts vs z plot
        self._mw.plot.setLabel('left', 'Counts', units='cps')
        self._mw.plot.setLabel('bottom', 'Z position', units='steps')
        self.plotdata = pg.PlotDataItem(pen=pg.mkPen(palette.c1, width=4))
        self._mw.plot.addItem(self.plotdata)

        # Flag to keep track of optimisation state
        self.sweep_run = False

        # Connect events from z-optimisation routines
        self.stagecontrol_logic.sigCountDataUpdated.connect(self.update_plot)
        self.stagecontrol_logic.sigOptimisationDone.connect(self.optimisation_done)

        ###################
        # Connect UI events
        ###################

        # Direction jog buttons
        self._mw.stop_btn.clicked.connect(self.stop_movement)

        self._mw.xy_move_widget.moved.connect(self.xy_moved)
        self.direction = (0, 0)

        self._mw.z_up_btn.pressed.connect(self.z_up)
        self._mw.z_down_btn.pressed.connect(self.z_down)

        self._mw.z_up_btn.released.connect(self.direction_btn_released)
        self._mw.z_down_btn.released.connect(self.direction_btn_released)

        # Parameter get/set buttons
        self._mw.set_x_btn.clicked.connect(self.set_x_params)
        self._mw.set_y_btn.clicked.connect(self.set_y_params)
        self._mw.set_z_btn.clicked.connect(self.set_z_params)
        self._mw.get_param_btn.clicked.connect(self.update_params)

        # Optimisation start/stop button
        self._mw.optimisation_btn.clicked.connect(self.optimise_btn_clicked)

        # Get params on load
        self.update_params(None)

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

    def xy_moved(self, direction):
        angle, magnitude = direction
        
        new_direction = (0, 0)

        if magnitude > 0.3:
            # Have a small dead-zone
            # Then quantise angles into 8 segments
            if angle > 337.5 or angle <= 22.5:
                # Right
                new_direction = (1, 0)
            elif angle <= 67.5:
                # Right, Up
                new_direction = (1, 1)
            elif angle <= 112.5:
                # Up
                new_direction = (0, 1)
            elif angle <= 157.5:
                # Left, Up
                new_direction = (-1, 1)
            elif angle <= 202.5:
                # Left
                new_direction = (-1, 0)
            elif angle <= 247.5:
                # Left, Down
                new_direction = (-1, -1)
            elif angle <= 292.5:
                # Down
                new_direction = (0, -1)
            elif angle <= 337.5:
                # Right, Down
                new_direction = (1, -1)

        # Check if the new direction is the same as the old one, and command
        # stage logic to move the stage appropriately if not.

        # X-axis
        if new_direction[0] == 0 and self.direction[0] != 0:
            self.stagecontrol_logic.stop_axis('x')

        elif new_direction[0] == -1 and self.direction[0] != -1:
            self.x_left()
        
        elif new_direction[0] == 1 and self.direction[0] != 1:
            self.x_right()
        
        # Y-axis
        if new_direction[1] == 0 and self.direction[1] != 0:
            self.stagecontrol_logic.stop_axis('y')
            
        elif new_direction[1] == -1 and self.direction[1] != -1:
            self.y_down()
        
        elif new_direction[1] == 1 and self.direction[1] != 1:
            self.y_up()
            
        self.direction = new_direction

    def x_left(self):
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('x', True)
        else:
            self.stagecontrol_logic.step('x', -1)

    def x_right(self):
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('x', False)
        else:
            self.stagecontrol_logic.step('x', 1)

    def y_up(self):
        """Direction button callback"""
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('y', False)
        else:
            self.stagecontrol_logic.step('y', 1)

    def y_down(self):
        """Direction button callback"""
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('y', True)
        else:
            self.stagecontrol_logic.step('y', -1)

    def z_up(self):
        """Direction button callback"""
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('z', False)
        else:
            self.stagecontrol_logic.step('z', 1)

    def z_down(self):
        """Direction button callback"""
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('z', True)
        else:
            self.stagecontrol_logic.step('z', -1)

    def direction_btn_released(self):
        """Direction button release callback"""
        self.stop_movement()

    @value_error_handler
    def set_x_params(self,msg):
        freq = float(self._mw.x_freq.text())
        volt = float(self._mw.x_voltage.text())
        self.stagecontrol_logic.set_axis_params('x', volt, freq)

    @value_error_handler
    def set_y_params(self,msg):
        freq = float(self._mw.y_freq.text())
        volt = float(self._mw.y_voltage.text())
        self.stagecontrol_logic.set_axis_params('y', volt, freq)

    @value_error_handler
    def set_z_params(self,msg):
        freq = float(self._mw.z_freq.text())
        volt = float(self._mw.z_voltage.text())
        self.stagecontrol_logic.set_axis_params('z', volt, freq)

    @value_error_handler
    def optimise_btn_clicked(self,msg):
        if self.sweep_run == False:
            if self._mw.step_search.isChecked():
                steps = int(self._mw.optimise_steps.text())
            else:
                steps = 0

            if self._mw.volt_search.isChecked():
                volts = int(self._mw.optimise_volts.text())
            else:
                volts = 0

            self.stagecontrol_logic.optimise_z(steps, volts)
            self.sweep_run = True
            self._mw.optimisation_btn.setText("Stop optimisation")
        else:
            self.stagecontrol_logic.abort_optimisation()
            self.sweep_run = False
            self._mw.optimisation_btn.setText("Start optimisation")

    def update_params(self,msg):
        """Get parameters from stepper & update GUI"""
        try:
            volt, freq = self.stagecontrol_logic.get_axis_params('x')
            self._mw.x_freq.setText(freq)
            self._mw.x_voltage.setText(volt)

            volt, freq = self.stagecontrol_logic.get_axis_params('y')
            self._mw.y_freq.setText(freq)
            self._mw.y_voltage.setText(volt)

            volt, freq = self.stagecontrol_logic.get_axis_params('z')
            self._mw.z_freq.setText(freq)
            self._mw.z_voltage.setText(volt)
        except TypeError:
            # TypeError can happen if there's a hw error
            # such that get_axis_params returns None.
            self.log.error('Unable to update axis parameters')

    def update_plot(self):
        counts = self.stagecontrol_logic.sweep_counts
        sweep_len = self.stagecontrol_logic.sweep_length
        steps = np.arange(-sweep_len,len(counts)-sweep_len)
        self.plotdata.setData(steps, counts)

    def optimisation_done(self):
        self._mw.optimisation_btn.setText("Start optimisation")
        self.sweep_run = False