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
import pandas

from qtwidgets.joystick import Joystick

from gui.colordefs import QudiPalettePale as palette

from core.connector import Connector
from gui.guibase import GUIBase

# Decorator to catch ValueError exceptions in functions which cast UI input text to other types.
def value_error_handler(func):
    @functools.wraps(func)
    def check(self,*args,**kwargs):
        try:
            return func(self,*args,**kwargs)
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
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()

class StageSettingsDialog(QtWidgets.QDialog):
    """ Dialog for getting settings """

    def __init__(self):
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_settingsdialog.ui')
        super().__init__()
        uic.loadUi(ui_file, self)

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

        # Settings dialog
        self._sd = StageSettingsDialog()

        # Hide central widget (so entire interface is dockwidgets)
        self._mw.centralwidget.hide()

        # Ensure table headers visible
        self._mw.position_TableWidget.horizontalHeader().setVisible(True)
        self._mw.position_TableWidget.verticalHeader().setVisible(True)

        # Connect events from logic
        self.stagecontrol_logic.sigPositionUpdated.connect(self.update_position)
        self.stagecontrol_logic.sigVelocityUpdated.connect(self.update_velocity)
        self.stagecontrol_logic.sigHitTarget.connect(self.hit_target)

        ###################
        # Connect UI events
        ###################

        # Show settings
        self._mw.show_settings_Action.triggered.connect(self.show_settings)

        # Accept settings dialog
        self._sd.accepted.connect(self.update_settings)

        # Direction jog buttons
        self._mw.stop_all_Action.triggered.connect(self.stop_movement)

        self._mw.xy_move_widget.moved.connect(self.xy_moved)
        self.direction = (0, 0)

        self._mw.z_up_btn.pressed.connect(self.z_up)
        self._mw.z_down_btn.pressed.connect(self.z_down)

        self._mw.z_up_btn.released.connect(self.z_released)
        self._mw.z_down_btn.released.connect(self.z_released)

        # Velocity buttons
        self._mw.get_vel_btn.clicked.connect(self.get_velocities)
        self._mw.set_vel_btn.clicked.connect(self.set_velocities)
        self._mw.slow_preset_pushButton.clicked.connect(
            lambda: self.stagecontrol_logic.set_velocity_to_preset('slow'))
        self._mw.med_preset_pushButton.clicked.connect(
            lambda: self.stagecontrol_logic.set_velocity_to_preset('medium'))
        self._mw.fast_preset_pushButton.clicked.connect(
            lambda: self.stagecontrol_logic.set_velocity_to_preset('fast'))

        # Home buttons
        self._mw.home_stage_Action.triggered.connect(self.home_all)

        # Move buttons
        self._mw.goto_btn.clicked.connect(self.goto_position)
        self._mw.rel_move_btn.clicked.connect(self.goto_position_rel)

        # Checkboxes
        self._mw.x_pos_entry.textChanged.connect(self.x_changed)
        self._mw.y_pos_entry.textChanged.connect(self.y_changed)
        self._mw.z_pos_entry.textChanged.connect(self.z_changed)

        # Position saving buttons
        self._mw.add_item_pushButton.clicked.connect(self.save_position)
        self._mw.delete_item_pushButton.clicked.connect(self.delete_position)
        self._mw.goto_saved_pushButton.clicked.connect(self.goto_saved_position)
        self._mw.savetofile_pushButton.clicked.connect(self.save_positions_to_file)
        self._mw.loadfromfile_pushButton.clicked.connect(self.load_positions_from_file)
        
    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        """ Deactivate the module
        """
        self._mw.close()

    ########################
    # Slots for jog controls
    ########################

    @QtCore.Slot()
    def stop_movement(self):
        """ Stop button pressed"""
        self.stagecontrol_logic.stop()

    @QtCore.Slot(tuple)
    def xy_moved(self, direction):
        """ XY joystick moved on panel.

        Handles deciding which direction to move the stage based on joystick
        input from GUI.
        """
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
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('y', False)
        else:
            self.stagecontrol_logic.step('y', 1)

    def y_down(self):
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('y', True)
        else:
            self.stagecontrol_logic.step('y', -1)

    @QtCore.Slot()
    def z_up(self):
        """Direction button callback"""
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('z', False)
        else:
            self.stagecontrol_logic.step('z', 1)

    @QtCore.Slot()
    def z_down(self):
        """Direction button callback"""
        if self._mw.continuous.isChecked():
            self.stagecontrol_logic.start_jog('z', True)
        else:
            self.stagecontrol_logic.step('z', -1)

    @QtCore.Slot()
    def z_released(self):
        """Z button release callback"""
        self.stagecontrol_logic.stop_axis('z')

    #############################
    # Slots for positioning panel
    #############################

    @QtCore.Slot()
    def home_all(self):
        """ Homes all axes after displaying confirmation messagebox.
        """
        check = QtWidgets.QMessageBox.question(
            self._mw,
            'Confirm home', 
            "This will move all axes to the home position. Continue?", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, 
            QtWidgets.QMessageBox.No)
        if check == QtWidgets.QMessageBox.Yes:
            self.stagecontrol_logic.home_axis()

    @QtCore.Slot(str)
    def x_changed(self, text):
        """ On text changed in x position box """
        self._mw.x_enable.setChecked(text != '')

    @QtCore.Slot(str)
    def y_changed(self, text):
        """ On text changed in y position box """
        self._mw.y_enable.setChecked(text != '')
    
    @QtCore.Slot(str)
    def z_changed(self, text):
        """ On text changed in z position box """
        self._mw.z_enable.setChecked(text != '')

    @value_error_handler
    @QtCore.Slot()
    def goto_position(self):
        """ Moves to absolute position
        """
        x_pos = ''
        y_pos = ''
        z_pos = ''

        # Get position from UI
        if self._mw.x_enable.isChecked():
            x_pos = self._mw.x_pos_entry.text()
        
        if self._mw.y_enable.isChecked():
            y_pos = self._mw.y_pos_entry.text()

        if self._mw.z_enable.isChecked():
            z_pos = self._mw.z_pos_entry.text()

        # Construct move_dict
        move_dict = {}
        if x_pos != '':
            move_dict['x'] = float(x_pos)/1e3

        if y_pos != '':
            move_dict['y'] = float(y_pos)/1e3

        if z_pos != '':
            move_dict['z'] = float(z_pos)/1e3

        self.stagecontrol_logic.move_abs(move_dict)

    @value_error_handler
    @QtCore.Slot()
    def goto_position_rel(self):
        """ Moves to relative position
        """
        # Get position from UI
        x_pos = self._mw.x_pos_entry_2.text()
        y_pos = self._mw.y_pos_entry_2.text()
        z_pos = self._mw.z_pos_entry_2.text()

        # Construct move_dict
        move_dict = {}
        if x_pos != '':
            move_dict['x'] = float(x_pos)/1e3

        if y_pos != '':
            move_dict['y'] = float(y_pos)/1e3

        if z_pos != '':
            move_dict['z'] = float(z_pos)/1e3

        self.stagecontrol_logic.move_rel(move_dict)

    # Slots for logic signals

    @QtCore.Slot(dict)
    def update_position(self, pos_dict):
        """ Updates position in GUI when signalled by logic. """
        try:
            if 'x' in pos_dict.keys():
                self._mw.x_pos.setText("{:7.5f}".format(pos_dict['x']*1e3))
            else:
                self._mw.x_pos.setText("--")
            if 'y' in pos_dict.keys():
                self._mw.y_pos.setText("{:7.5f}".format(pos_dict['y']*1e3))
            else:
                self._mw.y_pos.setText("--")
            if 'z' in pos_dict.keys():
                self._mw.z_pos.setText("{:7.5f}".format(pos_dict['z']*1e3))
            else:
                self._mw.z_pos.setText("--")
                
        except KeyError as err:
            self.log.warn('Could not update all positions. {}'.format(err))
        except ValueError:
            self._mw.x_pos.setText('')
            self._mw.y_pos.setText('')
            self._mw.z_pos.setText('')

    @QtCore.Slot()
    def hit_target(self):
        """ Updates GUI when stage hits target """
        # Disable all positioning enable checkboxes
        self._mw.x_enable.setChecked(False)
        self._mw.y_enable.setChecked(False)
        self._mw.z_enable.setChecked(False)

    ##########################
    # Slots for velocity panel
    ##########################

    @value_error_handler
    @QtCore.Slot()
    def set_velocities(self):
        """ Sets velocity according to values in text boxes"""
        x_vel = self._mw.x_vel.text()
        y_vel = self._mw.y_vel.text()
        z_vel = self._mw.z_vel.text()

        if x_vel != '':
            self.stagecontrol_logic.set_axis_config('x', velocity=float(x_vel/1e3))

        if y_vel != '':
            self.stagecontrol_logic.set_axis_config('y', velocity=float(y_vel/1e3))

        if z_vel != '':
            self.stagecontrol_logic.set_axis_config('z', velocity=float(z_vel/1e3))

    @QtCore.Slot()
    def get_velocities(self):
        """ Gets velocities from hardware and displays in boxes"""
        self._mw.x_vel.setText(
            str(self.stagecontrol_logic.get_axis_config('x', 'velocity')*1e3))
        self._mw.y_vel.setText(
            str(self.stagecontrol_logic.get_axis_config('y', 'velocity')*1e3))
        self._mw.z_vel.setText(
            str(self.stagecontrol_logic.get_axis_config('z', 'velocity')*1e3))

    @QtCore.Slot(dict)
    def update_velocity(self, velocity_dict):
        """ Updates velocity boxes when signalled by the logic. """
        for axis, velocity in velocity_dict.items():
            if axis == 'x':
                self._mw.x_vel.setText('{}'.format(velocity*1e3))
            elif axis == 'y':
                self._mw.y_vel.setText('{}'.format(velocity*1e3))
            elif axis == 'z':
                self._mw.z_vel.setText('{}'.format(velocity*1e3))

    ###########################
    # Slots for saved positions
    ###########################

    @QtCore.Slot()
    def delete_position(self):
        """ Deletes row from saved positions TableWidget """
        row = self._mw.position_TableWidget.currentRow()
        if row is not None:
            self._mw.position_TableWidget.removeRow(row)

    @QtCore.Slot()
    def goto_saved_position(self):
        """ Starts move to selected position in TableWidget """
        row = self._mw.position_TableWidget.currentRow()
        x = self._mw.position_TableWidget.item(row, 0)
        y = self._mw.position_TableWidget.item(row, 1)
        z = self._mw.position_TableWidget.item(row, 2)     

        # Construct move_dict
        move_dict = {}
        if x is not None and x.text() != '':
            move_dict['x'] = float(x.text())/1e3

        if y is not None and y.text() != '':
            move_dict['y'] = float(y.text())/1e3

        if z is not None and z.text() != '':
            move_dict['z'] = float(z.text())/1e3

        self.stagecontrol_logic.move_abs(move_dict)

    @QtCore.Slot()
    def save_position(self):
        """ Saves current position to TableWidget """
        row_count = self._mw.position_TableWidget.rowCount()
        self._mw.position_TableWidget.setRowCount(row_count + 1)
        x_item = QtWidgets.QTableWidgetItem(self._mw.x_pos.text())
        y_item = QtWidgets.QTableWidgetItem(self._mw.y_pos.text())
        z_item = QtWidgets.QTableWidgetItem(self._mw.z_pos.text())

        self._mw.position_TableWidget.setItem(row_count, 0, x_item)
        self._mw.position_TableWidget.setItem(row_count, 1, y_item)
        self._mw.position_TableWidget.setItem(row_count, 2, z_item)

    @QtCore.Slot()
    def save_positions_to_file(self):
        """ Saves position list to file """
        filename = QtWidgets.QFileDialog.getSaveFileName(self._mw, "Save position list", filter='*.csv')

        if filename[0] == '':
            return

        self.log.info("Saved position list to {}".format(filename[0]))

        row_count = self._mw.position_TableWidget.rowCount()

        position_data = []

        for row in range(0, row_count):
            x_item = self._mw.position_TableWidget.item(row, 0)
            y_item = self._mw.position_TableWidget.item(row, 1)
            z_item = self._mw.position_TableWidget.item(row, 2)
            description_item = self._mw.position_TableWidget.item(row, 3)

            if x_item is None:
                x = ''
            else:
                x = x_item.text()
            if y_item is None:
                y = ''
            else:
                y = y_item.text()
            if z_item is None:
                z = ''
            else:
                z = z_item.text()
            if description_item is None:
                description = ''
            else:
                description = description_item.text()

            position_data.append([x, y, z, description])

        df = pandas.DataFrame(position_data, columns=['x', 'y', 'z', 'description'])

        df.to_csv(filename[0])
            
    @QtCore.Slot()
    def load_positions_from_file(self):
        """ Loads position list from file """
        filename = QtWidgets.QFileDialog.getOpenFileName(self._mw, "Load position list", filter='*.csv')

        if filename[0] == '':
            return

        data = pandas.read_csv(filename[0])

        data.fillna('', inplace=True)

        current_row_count = self._mw.position_TableWidget.rowCount()

        self._mw.position_TableWidget.setRowCount(len(data.index) + current_row_count)

        for index, row in data.iterrows():
            x_item = QtWidgets.QTableWidgetItem('{:.5f}'.format(row['x']))
            y_item = QtWidgets.QTableWidgetItem('{:.5f}'.format(row['y']))
            z_item = QtWidgets.QTableWidgetItem('{:.5f}'.format(row['z']))
            description_item = QtWidgets.QTableWidgetItem(str(row['description']))

            self._mw.position_TableWidget.setItem(index + current_row_count, 0, x_item)
            self._mw.position_TableWidget.setItem(index + current_row_count, 1, y_item)
            self._mw.position_TableWidget.setItem(index + current_row_count, 2, z_item)
            self._mw.position_TableWidget.setItem(index + current_row_count, 3, description_item)

    ###########################
    # Slots for settings dialog
    ###########################

    @QtCore.Slot()
    def show_settings(self):
        """ Shows settings dialog with latest values from logic """
        preset = self.stagecontrol_logic.preset_velocities
        self._sd.x_slow_preset_lineEdit.setText(str(preset['slow']['x']*1e3))
        self._sd.y_slow_preset_lineEdit.setText(str(preset['slow']['y']*1e3))
        self._sd.z_slow_preset_lineEdit.setText(str(preset['slow']['z']*1e3))

        self._sd.x_med_preset_lineEdit.setText(str(preset['medium']['x']*1e3))
        self._sd.y_med_preset_lineEdit.setText(str(preset['medium']['y']*1e3))
        self._sd.z_med_preset_lineEdit.setText(str(preset['medium']['z']*1e3))

        self._sd.x_fast_preset_lineEdit.setText(str(preset['fast']['x']*1e3))
        self._sd.y_fast_preset_lineEdit.setText(str(preset['fast']['y']*1e3))
        self._sd.z_fast_preset_lineEdit.setText(str(preset['fast']['z']*1e3))

        self._sd.exec()
        
    @value_error_handler
    @QtCore.Slot()
    def update_settings(self):
        """ Updates logic with settings from dialog """
        slow = (
            float(self._sd.x_slow_preset_lineEdit.text()/1e3),
            float(self._sd.y_slow_preset_lineEdit.text()/1e3),
            float(self._sd.z_slow_preset_lineEdit.text()/1e3))

        medium = (
            float(self._sd.x_med_preset_lineEdit.text()/1e3),
            float(self._sd.y_med_preset_lineEdit.text()/1e3),
            float(self._sd.z_med_preset_lineEdit.text()/1e3))
        

        fast = (
            float(self._sd.x_fast_preset_lineEdit.text()/1e3),
            float(self._sd.y_fast_preset_lineEdit.text()/1e3),
            float(self._sd.z_fast_preset_lineEdit.text()/1e3))

        self.stagecontrol_logic.set_preset_values(slow=slow, medium=medium, fast=fast)
        