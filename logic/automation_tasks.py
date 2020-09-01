# -*- coding: utf-8 -*-
"""
This file contains Qudi automation functions. These appear in the automation
GUI automatically, with the docstring of the function displayed to explain
its purpose (ensure the docstring makes sense!)

Each function receives a reference to the automation logic object as its first
argument. Useful attributes of this object:

    - iteration: Loop iteration number (one-based)
    - stop_requested: Set to True to stop execution

The automation logic object also has various connectors as attributes. Use these
for inter-module communication by instatntiating, e.g.:

    opt_logic = automation_logic.optimizerlogic()

and check that the returned connector is not None (if it is, it hasn't been
connected in the Qudi config file).

Other positional arguments can be specified in the automation GUI.

Return a string that will be displayed as the 'status' in the GUI.

----

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

import time
import logging

def log_info(automation_logic, log_text=''):
    """Log an information message.

    Args:
        log_text (str): Message to log
    """
    automation_logic.log.info(log_text)
    return 'Completed'

def post_to_slack(automation_logic, message=None):
    """Post message to Slack

    Args:
        message (str): Message to send
    """
    slacklogic = automation_logic.slacklogic()
    if slacklogic is None:
        raise NameError('Please connect Slack logic module to automation')

    if message is None:
        return

    slacklogic.send_message(message)

def refind_POI(automation_logic):
    """Refind the currently selected POI.

    This is the same as clicking the 'Refind POI' button in the POI manager.
    """
    poimanager_logic = automation_logic.poimanagerlogic()
    optimizer_logic = automation_logic.optimizerlogic()

    if poimanager_logic is None:
        raise NameError('Please connect POI logic module to automation')

    if optimizer_logic is None:
        raise NameError('Please connect Optimizer logic module to automation')

    # Request optimization from POI manager
    poimanager_logic.optimise_poi_position()
    
    # Wait for it to start
    time.sleep(1)

    # Wait for optimisation to finish
    while optimizer_logic.module_state() == 'locked':
        time.sleep(0.1)
    
    return 'Completed'

def start_ODMR(automation_logic):
    """Start ODMR scan.

    Starts an ODMR scan, then returns as soon as it's running.
    """
    odmr_logic = automation_logic.odmrlogic()
    if odmr_logic is None:
        raise NameError('Please connect ODMR logic module to automation')

    # Start ODMR
    odmr_logic.start_odmr_scan()

    while odmr_logic.module_state() != 'locked':
        time.sleep(0.1)

    return "Completed"

def stop_ODMR(automation_logic):
    """Stop ODMR scan.

    Stops an ODMR scan, then returns as soon as it's actually stopped.
    """
    odmr_logic = automation_logic.odmrlogic()
    if odmr_logic is None:
        raise NameError('Please connect ODMR logic module to automation')

    # Start ODMR
    odmr_logic.stop_odmr_scan()

    while odmr_logic.module_state() == 'locked':
        time.sleep(0.1)

    return "Completed"

def acquire_confocal_scan(automation_logic):
    """Acquire confocal x,y map
    
    Blocks until complete.
    """
    confocal = automation_logic.confocallogic()
    if confocal is None:
        raise NameError('Please connect confocal logic module to automation')

    confocal.start_scanning()
    while True:
        time.sleep(1)
        if confocal.module_state() != 'locked':
            break
    
    return 'Completed'