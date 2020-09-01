# -*- coding: utf-8 -*-
"""
This file contains Qudi automation logic, for running predefined functions
in an order specified by the automation GUI.

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

from core.util.models import ListTableModel
from core.connector import Connector
from logic.generic_logic import GenericLogic
from qtpy import QtCore
import logic.automation_tasks as automation_tasks
import inspect
from ast import literal_eval
import time
import csv

class AutomationLogic(GenericLogic):
    """ Logic for running predefined Python functions.

    Attributes:
        model: core.util.models.ListTableModel containing the tasks to run.
            Each 'row' of the model is a task, and it contains 3 columns
            corresponding to:

            0. the name of the function to run (from `automation_tasks.py`)
            1. the arguments to the function, as a string
                - this will be evaluated by `literal_eval` and therefore uses
                  Python syntax for positional arguments (i.e. `<arg1>, <arg2>` etc)
            2. the status of the function, which is either None, 'Running' or the
                return value of the function.

            Access values using model[row, column] notation; values must also be 
            set this way to ensure the table model is updated properly.

        tasks: Dict of available tasks, with the keys being the function names.
            Each item in the dict is another dict, with keys:
                - 'func': Callable that is run for the task
                - 'description': Description taken from the docstring of the function.

    Example config for copy-paste:

    automationlogic:
        module.Class: 'automation_logic.AutomationLogic'
        connect:
            confocallogic: 'scannerlogic'

    NOTE: Add more connectors for optimizer, poimanager, hbt, spectro etc
        depending on which functions you need to use and what connectors they require.
        See automation_tasks.py, or try it and look for errors.
    """
    # Connectors
    optimizerlogic = Connector(interface='OptimizerLogic', optional=True)
    poimanagerlogic = Connector(interface='PoiManagerLogic', optional=True)
    confocallogic = Connector(interface='ConfocalLogic', optional=True)
    odmrlogic = Connector(interface='ODMRLogic', optional=True)
    hbtlogic = Connector(interface='HbtLogic', optional=True)
    spectrometerlogic = Connector(interface='SpectrometerLogic', optional=True)
    slacklogic = Connector(interface='SlackNotifierLogic', optional=True)

    # Internal signals
    _sig_run_task_list = QtCore.Signal()

    def on_activate(self):
        """ Prepare logic module for work.
        """
        self.model = ListTableModel()
        self.model.headers = ['Name', 'Arguments', 'Status']
        self.tasks = dict()
        reserved_names = ('start_loop', 'end_loop', 'wait')

        # Add 'special' tasks that affect the automation logic itself
        self.tasks['start_loop'] = {
            'description':'Mark start point of loop.\n\nArg: number of loop iterations '
                'that should be executed before continuing. (-1 for no limit).\n'
                'Note: loops cannot be nested.'
        }
        self.tasks['end_loop'] = {
            'description':'Mark the end point of a loop started with start_loop.'
        }
        self.tasks['wait'] = {
            'description':'Wait for the specified number of seconds.\n\n'
                'Arg: time to wait (in whole seconds)'
        }

        for t in inspect.getmembers(automation_tasks):
            name = t[0]
            if name in reserved_names:
                self.log.warning('Function name {} is reserved, please rename it'.format(name))
                continue
            func = t[1]
            if inspect.isfunction(func):
                self.tasks[name] = {
                    'func':func,
                    'description':func.__doc__
                }

        # Connect stuff
        self.connections = (
            self._sig_run_task_list.connect(self._run_task_list),
        )

    def on_deactivate(self):
        """ Deactivate module.
        """
        for conn in self.connections:
            QtCore.QObject.disconnect(conn)

    def run_task_list(self):
        """Run task list (returns immediately)
        
        module_state() will be 'running' while the run is in progress, and
        will return to 'idle' when it is done.
        """
        self._sig_run_task_list.emit()

    def request_stop(self):
        """Request to stop at the next available time"""
        self.stop_requested = True

    def load_automation(self, filename):
        """Load automation from csv file"""
        # Clear out current model values
        while self.model.pop(0) is not None:
            pass

        with open(filename, newline='') as csvfile:
            csv_reader = csv.reader(csvfile, delimiter='\t', quotechar='|')
            for line in csv_reader:
                self.model.append([*line, ''])


    def save_automation(self, filename):
        """Save automation to csv file"""
        with open(filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter='\t', quotechar='|')
            for item in self.model:
                csv_writer.writerow(item)

        self.log.info('Saved automation procedure to {}'.format(filename))

    def _run_task_list(self):
        """Run task list"""
        self.module_state.run()
        i = 0
        try:
            self.start_loop_idx = 0
            self.iterations = 1
            self.max_iterations = 0
            self.stop_requested = False
            while i < self.model.rowCount() and not self.stop_requested:
                task = self.model[i]

                ###############
                # Special tasks
                ###############
                if task[0] == 'start_loop':
                    self.start_loop_idx = i + 1
                    self.max_iterations = int(task[1])
                    self.iterations = 1
                    i += 1
                    continue
                elif task[0] == 'end_loop':
                    if self.iterations == -1:
                        self.model[i, 2] = 'Finished'
                        i += 1
                        continue
                    self.model[i, 2] = 'Run {} times'.format(self.iterations)
                    if self.iterations < self.max_iterations or self.max_iterations == -1:
                        i = self.start_loop_idx
                        self.iterations += 1
                        continue
                    else:
                        i += 1
                        continue
                elif task[0] == 'wait':
                    time_slept = 0
                    while time_slept < int(task[1]) and not self.stop_requested:
                        self.model[i, 2] = 'Waiting {} s'.format(time_slept+1)
                        time.sleep(1)
                        time_slept += 1
                    i += 1
                    continue

                ################################
                # Tasks from automation_tasks.py
                ################################
                func = self.tasks[task[0]]['func']

                # Translate argument string to dict:
                try:
                    args = literal_eval('[' + task[1] + ']')

                except ValueError:
                    self.log.error('Problem with argument string for task #{}'.format(i+1))

                self.model[i, 2] = 'Running'
                try:
                    retval = func(self, *args)
                except StopIteration:
                    self.model[i, 2] = 'StopIteration'
                    # Skip forward to end_loop
                    while i < self.model.rowCount():
                        if self.model[i, 0] == 'end_loop':
                            self.iterations = -1
                            break
                        i += 1
                    continue
                    
                self.model[i, 2] = retval

                i += 1

        except Exception as err:
            self.log.error(err)
            self.model[i, 2] = 'Error'
        
        finally:
            self.module_state.stop()
