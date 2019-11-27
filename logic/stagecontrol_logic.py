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
from core.configoption import ConfigOption

from core.util.mutex import Mutex

from interface.positioner_interface import PositionerError, PositionerOutOfRange, PositionerNotReferenced, AxisError, AxisConfigError

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
        except PositionerError as err:
            self.log.error(err)
    return check

class StagecontrolLogic(GenericLogic):
    """ Logic module for moving Attocube.
    """

    stagehardware = Connector(interface='PositionerInterface')
    counterlogic = Connector(interface='CounterLogic')
    xboxlogic = Connector(interface='XboxLogic')

    # Signals to trigger GUI updates
    sigOptimisationDone = QtCore.Signal()
    sigCountDataUpdated = QtCore.Signal()
    sigPositionUpdated = QtCore.Signal(dict)
    sigHitTarget = QtCore.Signal()

    # Signals to trigger stage moves
    sigStartJog = QtCore.Signal(tuple)
    sigStartStep = QtCore.Signal(tuple)
    sigStopAxis = QtCore.Signal(str)

    # Config option to invert axes for jog operations
    invert_axes = ConfigOption('jog_invert_axes', [])

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

        # Delay used between requesting stepper motion and requesting count-rate while optimising z-axis.
        # TODO: Make this a configuration option.
        self.optimise_delay = 100
        self.cl_optimise_delay = 200
        self.abort = False

        # Delay used for polling stage position
        # TODO: Make this a config option
        self.poll_interval = 500
        self.start_poll()
        
    def on_deactivate(self):
        """ Deactivate module.
        """
        pass

    def start_jog(self, axis, direction):
        """Start stage movement in specified direction.
        Uses a signal to actually start movement, so this can be 
        safely called from the GUI thread without blocking the GUI.
        """
        self.on_target = False
        if axis in self.invert_axes:
            direction = not direction

        self.sigStartJog.emit((axis, direction))
        
    def step(self, axis, steps):
        """Step stage in specified direction.
        Uses a signal to actually start movement, so this can be 
        safely called from the GUI thread without blocking the GUI.
        """
        self.on_target = False
        if axis in self.invert_axes:
            steps = -steps
        self.sigStartStep.emit((axis, steps))

    def stop_axis(self, axis):
        """Stop specified axis.
        Uses a signal to actually start movement, so this can be 
        safely called from the GUI thread without blocking the GUI.
        """
        self.sigStopAxis.emit(axis)

    @hwerror_handler
    def _do_jog(self, param_list):
        """Internal method to start jog. Connected to sigStartJog"""
        # Zero offset voltage
        self.stage_hw.set_axis_config(param_list[0], offset_voltage=0)

        # Do stage move
        self.stage_hw.start_continuous_motion(*param_list)

    @hwerror_handler
    def _do_step(self, param_list):
        """Internal method to start jog. Connected to sigStartStep"""
        # Zero offset voltage
        self.stage_hw.set_axis_config(param_list[0], offset_voltage=0)

        # Do stage move
        self.stage_hw.move_steps(*param_list)
    
    @hwerror_handler
    def _stop_axis(self, axis):
        """Internal method to stop axis. Connected to sigStopAxis"""
        self.stage_hw.stop_axis(axis)
        self.stage_hw.set_axis_config(axis, offset_voltage=0)
    

    @hwerror_handler
    def stop(self):
        self.stage_hw.stop_all()

    @hwerror_handler
    def set_axis_params(self,axis,volt,freq):
        self.stage_hw.set_axis_config(axis, step_voltage=volt, frequency=freq)

    @hwerror_handler
    def get_axis_params(self,axis):
        volt = self.stage_hw.get_axis_config(axis, 'step_voltage')
        freq = self.stage_hw.get_axis_config(axis, 'frequency')
        return volt, freq

    @hwerror_handler
    def get_velocities(self):
        velocity_dict = {}
        velocity_dict['x'] = self.stage_hw.get_axis_config('x', 'velocity')
        velocity_dict['y'] = self.stage_hw.get_axis_config('y', 'velocity')
        velocity_dict['z'] = self.stage_hw.get_axis_config('z', 'velocity')
        return velocity_dict
    
    @hwerror_handler
    def set_velocities(self, velocity_dict):
        if 'x' in velocity_dict.keys():
            self.stage_hw.set_axis_config('x', velocity=velocity_dict['x'])
        if 'y' in velocity_dict.keys():
            self.stage_hw.set_axis_config('y', velocity=velocity_dict['y'])
        if 'z' in velocity_dict.keys():
            self.stage_hw.set_axis_config('z', velocity=velocity_dict['z'])

    def optimise_z(self, steps, volts):
        """Perform z sweep while recording count rate to optimise focus"""

        # Initialise variables
        self.sweep_length = steps
        self.v_sweep_length = volts
        self.abort = False

        if steps > 0:
            # Stepping optimisation
            self._start_step_optimisation()

        elif volts > 0:
            # Offset V optimisation
            self._start_volt_optimisation()
    
    def _start_step_optimisation(self):
        # Start stepping optimisation routine
        self.current_step = -self.sweep_length
        self.sweep_counts = []

        # Zero offset voltage for stepping operations
        self.stage_hw.set_axis_config('z', offset_voltage=0)

        # Move to end of search range
        try:
            self.stage_hw.move_steps('z', steps=self.current_step)
        except PositionerError as err:
            self.log.error('Aborting sweep due to hardware error: {}'.format(err))
            return

        # Start counter running
        self.counter_logic.startCount()

        # Start QTimer (first delay 4x as long to allow counter extra time to start)
        QtCore.QTimer.singleShot(self.optimise_delay*4, self._optimisation_step)

    def _start_volt_optimisation(self):
        # Start offset voltage (fine) optimisation routine
        self.current_v_step = 0
        self.sweep_counts = []

        # Move one step back and an additional 1 step per 20 V in volt sweep
        steps = self.v_sweep_length // 20 + 1
        self.log.debug('Moving {} steps back'.format(steps))
        self.stage_hw.move_steps('z', steps=-steps)

        # Start counter running
        self.counter_logic.startCount()

        # Start QTimer (first delay 4x as long to allow counter extra time to start)
        QtCore.QTimer.singleShot(self.optimise_delay*4, self._volt_optimisation_step)

    @thread_lock
    def _volt_optimisation_step(self):
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
        
            if (self.current_v_step < self.v_sweep_length):
                try:
                    self.stage_hw.set_axis_config('z', offset_voltage=self.current_v_step)
                except PositionerError as err:
                    self.log.error("Aborting sweep due to hardware error: {}".format(err))
                    self.counter_logic.stopCount()
                    return

                self.current_v_step += 1

                # Start timer for next iteration
                QtCore.QTimer.singleShot(self.optimise_delay, self._volt_optimisation_step)

            else:
                # Sweep done - stop counter (not necessary)
                #self.counter_logic.stopCount()

                # Find index of maximum point, which will equal required offset voltage
                max_index = np.argmax(self.sweep_counts)
                self.log.debug('Optimum at {} volts'.format(max_index))

                # Set offset voltage to this maximum.
                try:
                    self.stage_hw.set_axis_config('z', offset_voltage=max_index)
                except PositionerError as err:
                    self.log.error('Could not return stage to optimum position due to hardware error: {}'.format(err))

                self.sigOptimisationDone.emit()

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
                try:
                    self.stage_hw.move_steps('z', 1)
                except PositionerError as err:
                    self.log.error("Aborting sweep due to hardware error: {}".format(err))
                    self.counter_logic.stopCount()
                    return

                self.current_step += 1

                # Start timer for next iteration
                QtCore.QTimer.singleShot(self.optimise_delay, self._optimisation_step)
            else:
                # Sweep done - stop counter (not actually necessary, left for reference)
                # self.counter_logic.stopCount()

                # Find index of maximum point, and calculate how far back to move
                max_index = np.argmax(self.sweep_counts)
                steps = 2*self.sweep_length - max_index
                self.log.debug('Optimum at {} steps from current position'.format(steps))

                # Do the movement
                try:
                    if steps > 0:
                        # Move stage if needed (note steps=0 seems to give continuous motion)
                        self.stage_hw.move_steps('z', -steps)
                except PositionerError as err:
                    self.log.error('Could not return stage to optimum position due to hardware error: {}'.format(err))

                if self.v_sweep_length > 0:
                    # If fine voltage sweep requested, start it after small delay
                    QtCore.QTimer.singleShot(self.optimise_delay*4, self._start_volt_optimisation)
                else:
                    # Otherwise emit Optimisation Done signal and return
                    self.sigOptimisationDone.emit()                   

        else:
            self.log.error("Sweep aborted: counter unexpectedly stopped.")

    @thread_lock
    def abort_optimisation(self):
        self.abort = True

    # Xbox control commands
    def xbox_button_press(self,button):
        self.on_target = False
        # D-pad: click x and y
        if button == 'left_down':
            # D-pad down
            self.step('y', -1)

        elif button == 'left_up':
            # D-pad up
            self.step('y', 1)

        if button == 'left_left':
            # D-pad left
            self.step('x', -1)

        elif button == 'left_right':
            # D-pad right
            self.step('x', 1)

        elif button == 'right_right':
            # B button
            self.stop()

        # Shoulder buttons: left - z down, right - z up
        if button == 'left_shoulder':
            # Left shoulder
            self.step('z', -1)

        elif button == 'right_shoulder':
            # Right shoulder
            self.step('z', 1)
    
    def xbox_joystick_move(self,joystick_state):
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
        # Attocube controller.

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

    def start_poll(self):
        self.poll = True
        QtCore.QTimer.singleShot(self.poll_interval, self._poll_position)

    def _poll_position(self):
        """
        Poll the stage for its current position
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

    def home_axis(self, axis='all'):
        self.stage_hw.reference_axis(axis)

    def move_abs(self, move_dict):
        self.on_target = False
        if 'x' in move_dict.keys():
            self.stage_hw.set_position('x', move_dict['x'])
        if 'y' in move_dict.keys():
            self.stage_hw.set_position('y', move_dict['y'])
        if 'z' in move_dict.keys():
            self.stage_hw.set_position('z', move_dict['z'])

    def move_rel(self, move_dict):
        self.on_target = False
        if 'x' in move_dict.keys():
            self.stage_hw.set_position('x', move_dict['x'], True)
        if 'y' in move_dict.keys():
            self.stage_hw.set_position('y', move_dict['y'], True)
        if 'z' in move_dict.keys():
            self.stage_hw.set_position('z', move_dict['z'], True)

    def is_moving(self):
        if (
            self.stage_hw.get_axis_status('x', 'on_target') and
            self.stage_hw.get_axis_status('y', 'on_target') and
            self.stage_hw.get_axis_status('z', 'on_target')
            ):
            return False
        else:
            return True

    def optimise_microns(self, microns):
        """Perform closed-loop Z sweep."""
        self.clsweep_length = microns
        
        # Choose step size so there are 20 points in the scan
        self.clsweep_step = microns / 10
        
        self.abort = False

        self.clsweep_current_pos = -self.clsweep_length
        self.sweep_counts = []
        self.clsweep_pos = []

        # Move to end of sweep range
        self.stage_hw.set_position('z', -self.clsweep_length, relative=True)

        # Start counter running
        if self.counter_logic.module_state() != 'locked':
            self.counter_logic.startCount()

        # Start QTimer
        QtCore.QTimer.singleShot(self.cl_optimise_delay, self._closedloop_optimisation_step)     

    @thread_lock
    def _closedloop_optimisation_step(self):
        """
        Do step in closed-loop optimisation
        """
        if self.abort:
            self.counter_logic.stopCount()
            return

        if not self.stage_hw.get_axis_status('z', 'on_target'):
            # If the stage is still moving, wait for another optimise_delay
            QtCore.QTimer.singleShot(self.cl_optimise_delay, self._closedloop_optimisation_step)
            return
        
        if self.counter_logic.module_state() == 'locked':
            # Get current stage position
            pos = self.stage_hw.get_position('z')
            self.clsweep_pos.append(pos)

            # Get last count value and store
            counts = self.counter_logic.countdata[-1, -2]
            self.sweep_counts.append(counts)

            # Emit event that can be caught by GUI to update
            self.sigCountDataUpdated.emit()

            # Check if at end of sweep
            if self.clsweep_current_pos < self.clsweep_length:
                # If not already at end of sweep, move stage 1 step
                # Calc next position
                self.clsweep_current_pos += self.clsweep_step

                self.stage_hw.set_position('z', self.clsweep_step, relative=True)

                # Start timer for next iteration
                QtCore.QTimer.singleShot(self.cl_optimise_delay, self._closedloop_optimisation_step)
            else:
                # Optimisation done
                # Find max counts
                max_index = np.argmax(self.sweep_counts)

                # Find actual stage position of max counts
                max_pos = self.clsweep_pos[max_index]

                # And go to it
                self.stage_hw.set_position('z', max_pos)

                # Emit 'finished' signal to update GUI
                self.sigOptimisationDone.emit()

    def get_hw_manufacturer(self):
        return self.stage_hw.hw_info()['manufacturer']