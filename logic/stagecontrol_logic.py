# -*- coding: utf-8 -*-
"""
Stage control logic for hardware implementing PositionerInterface.

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

from logic.generic_logic import GenericLogic
from collections import OrderedDict
from core.connector import Connector
from qtpy import QtCore
from core.configoption import ConfigOption
from core.statusvariable import StatusVar

from core.util.mutex import Mutex

from interface.positioner_interface import PositionerError, \
    PositionerOutOfRange, PositionerNotReferenced, AxisError, AxisConfigError

import numpy as np
import functools

class StagecontrolLogic(GenericLogic):
    """ Logic module for moving stage hardware with GUI and gamepad.
    """

    stagehardware = Connector(interface='PositionerInterface')
    xboxlogic = Connector(interface='XboxLogic')

    # Signals to trigger GUI updates
    sigPositionUpdated = QtCore.Signal(dict)
    sigHitTarget = QtCore.Signal()
    sigVelocityUpdated = QtCore.Signal(dict)

    # Signals to trigger stage moves
    sigStartJog = QtCore.Signal(tuple)
    sigStartStep = QtCore.Signal(tuple)
    sigStopAxis = QtCore.Signal(str)

    # Config option to invert axes for jog operations
    invert_axes = ConfigOption('jog_invert_axes', [])
    
    # Set polling interval for stage position (ms)
    poll_interval = ConfigOption('poll_interval', 500)

    preset_velocities = StatusVar(
            default={
                'slow': {'x':0.01, 'y':0.01, 'z':0.005},
                'medium': {'x':0.05, 'y':0.05, 'z':0.005},
                'fast': {'x':0.5, 'y':0.5, 'z':0.5}
            })

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
        self.xbox_logic = self.xboxlogic()

        self.xbox_logic.sigButtonPress.connect(self.xbox_button_press)
        self.xbox_logic.sigJoystickMoved.connect(self.xbox_joystick_move)

        self.on_target = False

        # Connect stage move signals
        self.sigStartJog.connect(self._do_jog)
        self.sigStartStep.connect(self._do_step)
        self.sigStopAxis.connect(self._stop_axis)

        # Variable to keep track of joystick state (avoid excessive number of 
        # commands to cube) - this is 0 for no motion, or +1 or -1 depending on 
        # direction.
        self.x_joystick_jog_running = 0
        self.y_joystick_jog_running = 0
        self.z_joystick_jog_running = 0

        self.start_poll()
        
    def on_deactivate(self):
        """ Deactivate module.
        """
        pass

    #######################
    # Stage control methods
    #######################
    
    def get_hw_manufacturer(self):
        """ Gets hardware info from stage hardware """
        return self.stage_hw.hw_info()

    def move_abs(self, move_dict):
        """ Moves stage to an absolute position.

        @param move_dict: dict of positions, with axis names as keys and 
            axis target positions as items. If an axis is not specified, it
            remains at its current position.
        """
        self.on_target = False
        if 'x' in move_dict.keys():
            self.stage_hw.set_position('x', move_dict['x'])
        if 'y' in move_dict.keys():
            self.stage_hw.set_position('y', move_dict['y'])
        if 'z' in move_dict.keys():
            self.stage_hw.set_position('z', move_dict['z'])

    def move_rel(self, move_dict):
        """ Moves stage to a relative position.

        @param move_dict: dict of positions, with axis names as keys and 
            axis move distances as items. If an axis is not specified, it
            remains at its current position.
        """
        self.on_target = False
        if 'x' in move_dict.keys():
            self.stage_hw.set_position('x', move_dict['x'], True)
        if 'y' in move_dict.keys():
            self.stage_hw.set_position('y', move_dict['y'], True)
        if 'z' in move_dict.keys():
            self.stage_hw.set_position('z', move_dict['z'], True)

    def is_moving(self):
        """ Returns True if any axis is currently moving.
        """
        if (self.stage_hw.get_axis_status('x', 'on_target') and
                self.stage_hw.get_axis_status('y', 'on_target') and
                self.stage_hw.get_axis_status('z', 'on_target')):
            return False
        else:
            return True

    def start_jog(self, axis, direction):
        """ Start stage movement on axis in specified direction.

        @param axis: str, move along this axis
        @param direction: bool, move in forward direction if True, backward if false.
        """
        self.on_target = False
        # pylint: disable=unsupported-membership-test
        if axis in self.invert_axes:
            direction = not direction

        self.sigStartJog.emit((axis, direction))
        
    def step(self, axis, steps):
        """ Steps stage in specified direction.
        
        @param axis str: axis to move.
        """
        self.on_target = False
        # pylint: disable=unsupported-membership-test
        if axis in self.invert_axes:
            steps = -steps
        self.sigStartStep.emit((axis, steps))

    def stop_axis(self, axis):
        """ Stops specified axis.
        
        @param axis str: axis to stop.
        """
        self.sigStopAxis.emit(axis)

    def stop(self):
        """ Stops all axes immediatey. """
        self.stage_hw.stop_all()

    def set_axis_config(self, axis, **config_options):
        """ Sets axis config options
        
        Accepts config options as kwargs to pass through to the hardware.
        """
        self.stage_hw.set_axis_config(axis, **config_options)

    def get_axis_config(self, axis, option=None):
        """ Gets axis parameters.
        
        @param axis str: Axis to get parameters from
        @param option str: (optional) Parameter to retrieve. If not specified, 
            return dict of all available config options.
        """
        return self.stage_hw.get_axis_config(axis, option)

    def home_axis(self, axis=None):
        """ Homes stage
        
        @param axis str: If specified, home this axis only. Otherwise home
            all axes. """
        self.stage_hw.reference_axis(axis)

    ##################
    # Velocity presets
    ##################

    def set_velocity_to_preset(self, preset):
        """ Sets velocities to the preset values.

        @param preset str: 'fast', 'medium' or 'slow'.
        """
        allowed_values = ('fast', 'medium', 'slow')
        if preset not in allowed_values:
            raise ValueError("Preset must be one of {}".format(allowed_values))

        # pylint: disable=unsubscriptable-object
        for axis, velocity in self.preset_velocities[preset].items():
            self.stage_hw.set_axis_config(axis, velocity=velocity)
            
        self.sigVelocityUpdated.emit(self.preset_velocities[preset])

    def set_preset_values(self, slow=None, medium=None, fast=None):
        """ Sets values for velocity presets.

        Any missing kwargs are left unchanged.

        @param slow tuple(float): Set slow velocities for (x, y, z) axes.
        @param medium tuple(float): Set medium velocities for (x, y, z) axes.
        @param fast tuple(float): Set fast velocities for (x, y, z) axes.
        """
        axes = ('x', 'y', 'z')

        # pylint: disable=unsupported-assignment-operation
        if slow is not None:
            self.preset_velocities['slow'] = dict(zip(axes, slow))

        if medium is not None:
            self.preset_velocities['medium'] = dict(zip(axes, medium))

        if fast is not None:
            self.preset_velocities['fast'] = dict(zip(axes, fast))

    ##############################
    # Internal stage control slots
    ##############################

    @QtCore.Slot(dict)
    def _do_jog(self, param_list):
        """ Internal method to start jog. Slot for sigStartJog"""
        self.stage_hw.start_continuous_motion(*param_list)

    @QtCore.Slot(dict)
    def _do_step(self, param_list):
        """ Internal method to start jog. Slot for sigStartStep"""
        self.stage_hw.move_steps(*param_list)
    
    @QtCore.Slot(str)
    def _stop_axis(self, axis):
        """ Internal method to stop axis. Slot for sigStopAxis"""
        self.stage_hw.stop_axis(axis)
        self.stage_hw.set_axis_config(axis, offset_voltage=0)

    ##################
    # Position polling
    ##################

    def start_poll(self):
        """ Start polling the stage position """
        self.poll = True
        QtCore.QTimer.singleShot(self.poll_interval, self._poll_position)

    def _poll_position(self):
        """ Poll the stage for its current position.

        Designed to be triggered by timer; emits sigPositionUpdated every time
        the position is polled, and sigHitTarget the first time the stage
        reports that no axes are moving after a move was started.
        """
        if not self.poll:
            return

        pos_dict = {}

        try:
            pos_dict['x'] = self.stage_hw.get_position('x')
            pos_dict['y'] = self.stage_hw.get_position('y')
            pos_dict['z'] = self.stage_hw.get_position('z')

            if not self.is_moving():
                if not self.on_target:
                    self.sigHitTarget.emit()
                    self.on_target = True
            else:
                if self.on_target:
                    self.on_target = False

        except PositionerError:
            # Ignore hardware errors.
            pass

        self.sigPositionUpdated.emit(pos_dict)
        QtCore.QTimer.singleShot(self.poll_interval, self._poll_position)

    ###################
    # Gamepad interface
    ###################

    @QtCore.Slot(str)
    def xbox_button_press(self,button):
        """ Moves stage according to inputs from the Xbox controller buttons.

        Slot for sigButtonPressed from xboxlogic module."""
        self.on_target = False
        # D-pad: click x and y
        if button == 'left_down':
            # D-pad down
            self.step('y', -1)

        elif button == 'left_up':
            # D-pad up
            self.step('y', 1)

        elif button == 'left_left':
            # D-pad left
            self.step('x', -1)

        elif button == 'left_right':
            # D-pad right
            self.step('x', 1)

        # Shoulder buttons: left - z down, right - z up
        elif button == 'left_shoulder':
            # Left shoulder
            self.step('z', -1)

        elif button == 'right_shoulder':
            # Right shoulder
            self.step('z', 1)

        # A, B, X, Y
        elif button == 'right_down':
            # A button
            self.set_velocity_to_preset('slow')
        elif button == 'right_up':
            # Y button
            self.set_velocity_to_preset('fast')
        elif button == 'right_left':
            # X button
            self.set_velocity_to_preset('medium')
        elif button == 'right_right':
            # B button
            self.stop()
    
    @QtCore.Slot(dict)
    def xbox_joystick_move(self,joystick_state):
        """ Moves stage according to inputs from the Xbox controller joysticks.

        Slot for sigJoystickMoved from xboxlogic module."""

        self.on_target = False
        # Z-control on y-axis of right-hand joystick
        z = joystick_state['y_right']

        if z == 0 and self.z_joystick_jog_running != 0:
            # If joystick zeroed and cube is currently moving, stop.
            self.stop_axis('z')
            self.z_joystick_jog_running = 0

        elif np.sign(z) != np.sign(self.z_joystick_jog_running):
            # Otherwise, move in appropriate direction if needed.
            if z > 0:
                self.start_jog('z', False)
                self.z_joystick_jog_running = 1
            elif z < 0:
                self.start_jog('z', True)
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
        # stage controller.

        if required_x == 0 and self.x_joystick_jog_running != 0:
            # Stop x
            self.stop_axis('x')
            self.x_joystick_jog_running = 0
            
        if required_y == 0 and self.y_joystick_jog_running != 0:
            # Stop y
            self.stop_axis('y')
            self.y_joystick_jog_running = 0

        if (required_y != 0 and
            (np.sign(self.y_joystick_jog_running) != np.sign(required_y) 
            or self.y_joystick_jog_running == 0)):
            # Move y
            if y > 0:
                self.start_jog('y', True)
                self.y_joystick_jog_running = 1
            elif y < 0:
                self.start_jog('y', False)
                self.y_joystick_jog_running = -1
        
        if (required_x != 0 and
            (np.sign(self.x_joystick_jog_running) != np.sign(required_x) 
            or self.x_joystick_jog_running == 0)):
            # Move x
            if x > 0:
                self.start_jog('x', True)
                self.x_joystick_jog_running = 1
            elif x < 0:
                self.start_jog('x', False)
                self.x_joystick_jog_running = -1
