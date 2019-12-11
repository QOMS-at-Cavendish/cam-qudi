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

        # Ensure table headers visible
        self._mw.position_TableWidget.horizontalHeader().setVisible(True)
        self._mw.position_TableWidget.verticalHeader().setVisible(True)

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
        self.stagecontrol_logic.sigPositionUpdated.connect(self.update_position)
        self.stagecontrol_logic.sigHitTarget.connect(self.hit_target)

        # Show or hide attocube tab depending on reported hardware
        if self.stagecontrol_logic.get_hw_manufacturer() != 'Attocube':
            # Remove attocube tab
            self._mw.tabWidget.removeTab(3)

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

        self._mw.get_vel_btn.clicked.connect(self.get_velocities)
        self._mw.set_vel_btn.clicked.connect(self.set_velocities)

        # Optimisation start/stop button
        self._mw.optimisation_btn.clicked.connect(self.optimise_btn_clicked)

        # Home buttons
        self._mw.home_x.clicked.connect(self.home_x)
        self._mw.home_y.clicked.connect(self.home_y)
        self._mw.home_z.clicked.connect(self.home_z)
        self._mw.home_all.clicked.connect(self.home_all)

        # Move buttons
        self._mw.goto_btn.clicked.connect(self.goto_position)
        self._mw.rel_move_btn.clicked.connect(self.goto_position_rel)

        # Checkboxes
        self._mw.x_pos_entry.textChanged.connect(self.x_changed)
        self._mw.y_pos_entry.textChanged.connect(self.y_changed)
        self._mw.z_pos_entry.textChanged.connect(self.z_changed)

        # Position saving buttons
        self._mw.add_item_pushButton.clicked.connect(self.add_position)
        self._mw.delete_item_pushButton.clicked.connect(self.delete_position)
        self._mw.save_position_pushButton.clicked.connect(self.save_position)
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
            if self._mw.search_closedloop.isChecked():
                microns = abs(float(self._mw.optimise_microns.text()))
                self.stagecontrol_logic.optimise_microns(microns)
            if self._mw.step_search.isChecked():
                steps = abs(int(self._mw.optimise_steps.text()))
            else:
                steps = 0

            if self._mw.volt_search.isChecked():
                volts = abs(int(self._mw.optimise_volts.text()))
            else:
                volts = 0

            self.stagecontrol_logic.optimise_z(steps, volts)
            self.sweep_run = True
            self._mw.optimisation_btn.setText("Stop optimisation")
        else:
            self.stagecontrol_logic.abort_optimisation()
            self.sweep_run = False
            self._mw.optimisation_btn.setText("Start optimisation")

    def home_x(self):
        check = QtWidgets.QMessageBox.question(
            self._mw,
            'Confirm home', 
            "This will move the x-axis stage to the home position. Continue?", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, 
            QtWidgets.QMessageBox.No)
        if check == QtWidgets.QMessageBox.Yes:
            self.stagecontrol_logic.home_axis('x')

    def home_y(self):
        check = QtWidgets.QMessageBox.question(
            self._mw,
            'Confirm home', 
            "This will move the y-axis stage to the home position. Continue?", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, 
            QtWidgets.QMessageBox.No)
        if check == QtWidgets.QMessageBox.Yes:
            self.stagecontrol_logic.home_axis('y')

    def home_z(self):
        check = QtWidgets.QMessageBox.question(
            self._mw,
            'Confirm home', 
            "This will move the z-axis stage to the home position. Continue?", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, 
            QtWidgets.QMessageBox.No)
        if check == QtWidgets.QMessageBox.Yes:
            self.stagecontrol_logic.home_axis('z')

    def home_all(self):
        check = QtWidgets.QMessageBox.question(
            self._mw,
            'Confirm home', 
            "This will move all axes to the home position. Continue?", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, 
            QtWidgets.QMessageBox.No)
        if check == QtWidgets.QMessageBox.Yes:
            self.stagecontrol_logic.home_axis()

    def update_position(self, pos_dict):
        try:
            if 'x' in pos_dict.keys():
                self._mw.x_pos.setText("{:2.5f}".format(pos_dict['x']))
            else:
                self._mw.x_pos.setText("--")
            if 'y' in pos_dict.keys():
                self._mw.y_pos.setText("{:2.5f}".format(pos_dict['y']))
            else:
                self._mw.y_pos.setText("--")
            if 'z' in pos_dict.keys():
                self._mw.z_pos.setText("{:2.5f}".format(pos_dict['z']))
            else:
                self._mw.z_pos.setText("--")
                
        except KeyError as err:
            self.log.warn('Could not update all positions. {}'.format(err))
        except ValueError:
            self._mw.x_pos.setText('')
            self._mw.y_pos.setText('')
            self._mw.z_pos.setText('')

    def hit_target(self):
        """ Stage hit target """
        # Disable all positioning enable checkboxes
        self._mw.x_enable.setChecked(False)
        self._mw.y_enable.setChecked(False)
        self._mw.z_enable.setChecked(False)

    def x_changed(self, text):
        """ On text changed in x position box """
        self._mw.x_enable.setChecked(text != '')

    def y_changed(self, text):
        """ On text changed in y position box """
        self._mw.y_enable.setChecked(text != '')
    
    def z_changed(self, text):
        """ On text changed in z position box """
        self._mw.z_enable.setChecked(text != '')

    @value_error_handler
    def goto_position(self, msg):
        """
        Goto absolute position
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
            move_dict['x'] = float(x_pos)

        if y_pos != '':
            move_dict['y'] = float(y_pos)

        if z_pos != '':
            move_dict['z'] = float(z_pos)

        self.stagecontrol_logic.move_abs(move_dict)

    @value_error_handler
    def goto_position_rel(self, msg):
        """
        Goto relative position
        """
        # Get position from UI
        x_pos = self._mw.x_pos_entry_2.text()
        y_pos = self._mw.y_pos_entry_2.text()
        z_pos = self._mw.z_pos_entry_2.text()

        # Construct move_dict
        move_dict = {}
        if x_pos != '':
            move_dict['x'] = float(x_pos)

        if y_pos != '':
            move_dict['y'] = float(y_pos)

        if z_pos != '':
            move_dict['z'] = float(z_pos)

        self.stagecontrol_logic.move_rel(move_dict)

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

    def get_velocities(self):
        velocity_dict = self.stagecontrol_logic.get_velocities()
        self._mw.x_vel.setText(str(velocity_dict['x']))
        self._mw.y_vel.setText(str(velocity_dict['y']))
        self._mw.z_vel.setText(str(velocity_dict['z']))

    @value_error_handler
    def set_velocities(self, msg):
        # Get velocities from UI
        x_vel = self._mw.x_vel.text()
        y_vel = self._mw.y_vel.text()
        z_vel = self._mw.z_vel.text()

        # Construct velocity_dict
        velocity_dict = {}
        if x_vel != '':
            velocity_dict['x'] = float(x_vel)

        if y_vel != '':
            velocity_dict['y'] = float(y_vel)

        if z_vel != '':
            velocity_dict['z'] = float(z_vel)

        self.stagecontrol_logic.set_velocities(velocity_dict)

    def add_position(self):
        row_count = self._mw.position_TableWidget.rowCount()
        self._mw.position_TableWidget.setRowCount(row_count + 1)

    def delete_position(self):
        row = self._mw.position_TableWidget.currentRow()
        if row is not None:
            self._mw.position_TableWidget.removeRow(row)

    def goto_saved_position(self):
        row = self._mw.position_TableWidget.currentRow()
        x = self._mw.position_TableWidget.item(row, 0)
        y = self._mw.position_TableWidget.item(row, 1)
        z = self._mw.position_TableWidget.item(row, 2)     

        # Construct move_dict
        move_dict = {}
        if x is not None and x.text() != '':
            move_dict['x'] = float(x.text())

        if y is not None and y.text() != '':
            move_dict['y'] = float(y.text())

        if z is not None and z.text() != '':
            move_dict['z'] = float(z.text())

        self.stagecontrol_logic.move_abs(move_dict)


    def save_position(self):
        row_count = self._mw.position_TableWidget.rowCount()
        self._mw.position_TableWidget.setRowCount(row_count + 1)
        x_item = QtWidgets.QTableWidgetItem(self._mw.x_pos.text())
        y_item = QtWidgets.QTableWidgetItem(self._mw.y_pos.text())
        z_item = QtWidgets.QTableWidgetItem(self._mw.z_pos.text())
        self.log.debug(x_item.text())
        self._mw.position_TableWidget.setItem(row_count, 0, x_item)
        self._mw.position_TableWidget.setItem(row_count, 1, y_item)
        self._mw.position_TableWidget.setItem(row_count, 2, z_item)

    def save_positions_to_file(self):
        """Save position list to file"""
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
            
    def load_positions_from_file(self):
        """Load position list from file"""
        filename = QtWidgets.QFileDialog.getOpenFileName(self._mw, "Load position list", filter='*.csv')

        if filename[0] == '':
            return

        data = pandas.read_csv(filename[0])

        data.fillna('', inplace=True)

        current_row_count = self._mw.position_TableWidget.rowCount()

        self._mw.position_TableWidget.setRowCount(len(data.index) + current_row_count)

        for index, row in data.iterrows():
            x_item = QtWidgets.QTableWidgetItem(str(row['x']))
            y_item = QtWidgets.QTableWidgetItem(str(row['y']))
            z_item = QtWidgets.QTableWidgetItem(str(row['z']))
            description_item = QtWidgets.QTableWidgetItem(str(row['description']))

            self._mw.position_TableWidget.setItem(index + current_row_count, 0, x_item)
            self._mw.position_TableWidget.setItem(index + current_row_count, 1, y_item)
            self._mw.position_TableWidget.setItem(index + current_row_count, 2, z_item)
            self._mw.position_TableWidget.setItem(index + current_row_count, 3, description_item)