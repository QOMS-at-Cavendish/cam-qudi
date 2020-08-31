# -*- coding: utf-8 -*-
"""
This file contains the Qudi automation GUI.

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

import os

from core.connector import Connector
from gui.guibase import GUIBase
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic


class AutomationGui(GUIBase):
    """ Graphical interface for arranging tasks without using Python code.
    
    Reads the Python functions contained in `automation_tasks.py`.

    Toolbar buttons:
    1. Run
        Run the current task list from top to bottom
    2. Stop
        Stop the execution of the task list as soon as possible (usually needs to
        wait for the current task to finish first)
    3. Add
        Select a function and fill in values for its arguments if needed 
        (using normal Python syntax, i.e. comma-separated values).
        Can also add the special functions 'start_loop', 'end_loop' and 'wait'.
        Selecting a function will show its documentation in the Add dialog box.
        Add inserts above the selected item, if any, otherwise it inserts at the 
        bottom.
    4. Edit
        Opens a dialog box to allow editing of the currently selected task.
    5. Remove
        Removes currently selected item, if any. If multiple are selected, remove
        the first one.

    Menu items:
    1. File -> Save
        Save the current list of tasks to file in .qudiauto format (tab-delim csv)
    2. File -> Load
        Load a task list from file (note this will empty the list first)
    
    Example config for copy-paste:
    
    automation:
        module.Class: 'automation.automationgui.AutomationGui'
        connect:
            automationlogic: 'automationlogic'
    """

    # declare connectors
    automationlogic = Connector(interface='AutomationLogic')

    def on_activate(self):
        """Create all UI objects and show the window.
        """
        self._mw = AutomationMainWindow()
        self._task_dialog = TaskDialog()
        self.restoreWindowPos(self._mw)
        self.logic = self.automationlogic()
        self._mw.autoTableView.setModel(self.logic.model)

        self._task_dialog.func_comboBox.addItems(self.logic.tasks.keys())

        self._edited_task_idx = None

        # Connect signals
        self.connections = (
            self._mw.actionAdd.triggered.connect(self._add_task),
            self._mw.actionEdit.triggered.connect(self._edit_task),
            self._mw.actionRemove.triggered.connect(self._remove_task),
            self._mw.actionRun.triggered.connect(self._run),
            self._mw.actionStop.triggered.connect(self._stop),
            self._mw.actionSave.triggered.connect(self._save),
            self._mw.actionLoad.triggered.connect(self._load),
            self._task_dialog.func_comboBox.currentTextChanged.connect(self._func_changed),
            self._task_dialog.accepted.connect(self._task_dialog_accept),
            self.logic.model.data_changed_proxy.connect(self._data_changed),
            self.logic.module_state.sigStateChanged.connect(self._logic_state_change)
        )

        self.show()

    def show(self):
        """Make sure that the window is visible and at the top.
        """
        self._mw.show()

    def on_deactivate(self):
        """ Deactivate module
        """
        for conn in self.connections:
            QtCore.QObject.disconnect(conn)
        self.saveWindowPos(self._mw)
        self._mw.close()

    ###########
    # GUI slots
    ###########

    @QtCore.Slot()
    def _add_task(self):
        name = self._task_dialog.func_comboBox.currentText()
        self._func_changed(name)
        self._task_dialog.func_args_lineEdit.setText('')
        self._task_dialog.setWindowTitle('Add task')
        self._edited_task_idx = None
        self._task_dialog.exec_()

    @QtCore.Slot()
    def _edit_task(self):
        index = self._mw.autoTableView.selectedIndexes()
        if len(index) > 0:
            name = self.logic.model[index[0].row(), 0]
            args = self.logic.model[index[0].row(), 1]
            self._task_dialog.func_comboBox.setCurrentText(name)
            self._func_changed(name)
            self._task_dialog.func_args_lineEdit.setText(args)
            self._task_dialog.setWindowTitle('Edit task')
            self._edited_task_idx = index[0].row()
            self._task_dialog.exec_()

    @QtCore.Slot()
    def _remove_task(self):
        index = self._mw.autoTableView.selectedIndexes()
        if len(index) > 0:
            self.logic.model.pop(index[0].row())

    @QtCore.Slot()
    def _run(self):
        self.logic.run_task_list()

    @QtCore.Slot()
    def _stop(self):
        self._mw.actionStop.setEnabled(False)
        self.logic.request_stop()

    @QtCore.Slot()
    def _load(self):
        filename = QtWidgets.QFileDialog.getOpenFileName(self._mw, "Open automation list", filter='*.qudiauto')[0]
        if filename != '':
            self.logic.load_automation(filename)

    @QtCore.Slot()
    def _save(self):
        filename = QtWidgets.QFileDialog.getSaveFileName(self._mw, "Save automation list", filter='*.qudiauto')[0]
        if filename != '':
            self.logic.save_automation(filename)

    @QtCore.Slot()
    def _task_dialog_accept(self):
        name = self._task_dialog.func_comboBox.currentText()
        args = self._task_dialog.func_args_lineEdit.text()
        if self._edited_task_idx is None:
            index = self._mw.autoTableView.selectedIndexes()
            if len(index) > 0:
                self.logic.model.insert(index[0].row(),
                                        [name, args, ''])
            else:
                self.logic.model.append([name, args, ''])
        else:
            self.logic.model[self._edited_task_idx, 0] = name
            self.logic.model[self._edited_task_idx, 1] = args
            self.logic.model[self._edited_task_idx, 2] = ''

    @QtCore.Slot(str)
    def _func_changed(self, text):
        self._task_dialog.func_info.setText(self.logic.tasks[text]['description'])

    @QtCore.Slot(object)
    def _logic_state_change(self, e):
        if e.dst == 'running':
            enabled = False
        elif e.dst == 'idle':
            enabled = True
        
        self._mw.actionAdd.setEnabled(enabled)
        self._mw.actionEdit.setEnabled(enabled)
        self._mw.actionRemove.setEnabled(enabled)
        self._mw.actionRun.setEnabled(enabled)
        self._mw.actionStop.setEnabled(not enabled)

    @QtCore.Slot()
    def _data_changed(self):
        self.logic.model.actually_emit_changed_signal()

class TaskDialog(QtWidgets.QDialog):
    """ Dialog for getting task settings """
    def __init__(self):
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'task_settings.ui')
        super().__init__()
        uic.loadUi(ui_file, self)

class AutomationMainWindow(QtWidgets.QMainWindow):
    """ Helper class for window loaded from UI file.
    """
    def __init__(self):
        """ Create the switch GUI window.
        """
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_autogui.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()
