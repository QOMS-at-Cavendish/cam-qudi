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
    xboxlogic = Connector(interface='XboxLogic')

    sigStartCounter = QtCore.Signal()
    sigStopCounter = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """

        self.stagecontrol_logic = self.stagecontrollogic()
        self.xbox_logic = self.xboxlogic()

        self.xbox_logic.sigButtonPress.connect(self.xbox_button_press)
        self.xbox_logic.sigJoystickMoved.connect(self.xbox_joystick_move)

        # Create main window instance
        self._mw = StagecontrolMainWindow()

        # Set up counts vs z plot
        self._mw.plot.setLabel('left', 'Counts', units='cps')
        self._mw.plot.setLabel('bottom', 'Z position', units='steps')
        self.plotdata = pg.PlotDataItem(pen=pg.mkPen('0BF', width=4))
        self._mw.plot.addItem(self.plotdata)

        # Flag to keep track of optimisation state
        self.sweep_run = False

        # Variable to keep track of joystick state (avoid excessive number of 
        # commands to cube) - this is 0 for no motion, or +1 or -1 depending on 
        # direction.
        self.x_joystick_jog_running = 0
        self.y_joystick_jog_running = 0
        self.z_joystick_jog_running = 0

        # Connect events from z-optimisation routines
        self.stagecontrol_logic.sigCountDataUpdated.connect(self.update_plot)
        self.stagecontrol_logic.sigOptimisationDone.connect(self.optimisation_done)

        ###################
        # Connect UI events
        ###################

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

    # Xbox control commands
    def xbox_button_press(self,button):
        if not self._mw.xbox_enable.isChecked():
            # If Xbox control checkbox is unticked, then return
            return

        # D-pad: click x and y
        if button == 'left_down':
            # D-pad down
            self.stagecontrol_logic.step('y', -1)

        elif button == 'left_up':
            # D-pad up
            self.stagecontrol_logic.step('y', 1)

        if button == 'left_left':
            # D-pad left
            self.stagecontrol_logic.step('x', -1)

        elif button == 'left_right':
            # D-pad right
            self.stagecontrol_logic.step('x', 1)

        elif button == 'right_right':
            # B button
            self.stop_movement()

        # Shoulder buttons: left - z down, right - z up
        if button == 'left_shoulder':
            # Left shoulder
            self.stagecontrol_logic.step('z', -1)

        elif button == 'right_shoulder':
            # Right shoulder
            self.stagecontrol_logic.step('z', 1)
    
    def xbox_joystick_move(self,joystick_state):
        if not self._mw.xbox_enable.isChecked():
            # If Xbox control checkbox is unticked, then return
            return

        # Z-control on y-axis of right-hand joystick
        z = joystick_state['y_right']

        if z == 0 and self.z_joystick_jog_running != 0:
            # If joystick zeroed and cube is currently moving, stop.
            self.stagecontrol_logic.stop_axis('z')
            self.z_joystick_jog_running = 0

        elif np.sign(z) != np.sign(self.z_joystick_jog_running):
            # Otherwise, move in appropriate direction if needed.
            if z > 0:
                self.stagecontrol_logic.start_jog('z', False)
                self.z_joystick_jog_running = 1
            elif z < 0:
                self.stagecontrol_logic.start_jog('z', True)
                self.z_joystick_jog_running = -1

        # x,y control on left-hand joystick
        # Use sectors defined by lines with y = 2x and x = 2y for pure y or x
        # motion, otherwise do diagonal movement.
        x = joystick_state['x_left']
        y = joystick_state['y_left']

        required_x = 0
        required_y = 0

        if np.sqrt(x**2 + y**2) < 0.1:
            # Circular dead-zone
            pass

        elif abs(y) > abs(2*x):
            # If in the exclusive y motion sector, just move in y
            required_y = np.sign(y)

        elif abs(x) > abs(2*y):
            # If in the exclusive x motion sector, just move in x
            required_x = np.sign(x)

        else:
            # If somewhere else, move if the axis is non-zero.
            if x != 0:
                required_x = np.sign(x)
            if y != 0:
                required_y = np.sign(y)

        # Do required movements, checking flags to minimise commands sent to
        # Attocube controller.

        if required_x == 0 and self.x_joystick_jog_running != 0:
            # Stop x
            self.stagecontrol_logic.stop_axis('x')
            self.x_joystick_jog_running = 0
            
        if required_y == 0 and self.y_joystick_jog_running != 0:
            # Stop y
            self.stagecontrol_logic.stop_axis('y')
            self.y_joystick_jog_running = 0

        if (required_y != 0 and
            (np.sign(self.y_joystick_jog_running) != np.sign(required_y) 
            or self.y_joystick_jog_running == 0)):
            # Move y
            if y > 0:
                self.stagecontrol_logic.start_jog('y', True)
                self.y_joystick_jog_running = 1
            elif y < 0:
                self.stagecontrol_logic.start_jog('y', False)
                self.y_joystick_jog_running = -1
        
        if (required_x != 0 and
            (np.sign(self.x_joystick_jog_running) != np.sign(required_x) 
            or self.x_joystick_jog_running == 0)):
            # Move x
            if x > 0:
                self.stagecontrol_logic.start_jog('x', True)
                self.x_joystick_jog_running = 1
            elif x < 0:
                self.stagecontrol_logic.start_jog('x', False)
                self.x_joystick_jog_running = -1

    #Button callbacks
    def stop_movement(self):
        """Stop button callback"""
        self.stagecontrol_logic.stop()

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
            steps = int(self._mw.optimise_steps.text())
            self.stagecontrol_logic.optimise_z(steps)
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