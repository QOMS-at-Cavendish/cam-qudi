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
from qtpy import QtGui
from qtpy import uic
import pyqtgraph as pg
import functools

from core.connector import Connector
from gui.guibase import GUIBase

class MimicMainWindow(QtWidgets.QMainWindow):

    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'fibre_switch.ui')

        # Load it
        super(MimicMainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()


class MimicGui(GUIBase):

    xseries = Connector(interface='NationalInstrumentsXSeries')

    channel = '/Dev1/PFI9'

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        
        self.nicard = self.xseries()

        # Create main window instance
        self._mw = MimicMainWindow()

        this_dir = os.path.dirname(__file__)

        self.fibre_sw_on_pixmap =  QtGui.QPixmap(
            os.path.join(this_dir, "fibre_switch_on.png"))

        self.fibre_sw_off_pixmap =  QtGui.QPixmap(
            os.path.join(this_dir, "fibre_switch_off.png"))

        # Initialise module with fibre switch off
        self.fibre_switch_off()

        ###################
        # Connect UI events
        ###################

        self._mw.fibre_sw_off_btn.clicked.connect(self.fibre_switch_off)
        self._mw.fibre_sw_on_btn.clicked.connect(self.fibre_switch_on)


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

    def fibre_switch_off(self):
        self._mw.fibre_sw_mimic.setPixmap(self.fibre_sw_off_pixmap)
        self.nicard.digital_channel_switch(self.channel, False)

    def fibre_switch_on(self):
        self._mw.fibre_sw_mimic.setPixmap(self.fibre_sw_on_pixmap)
        self.nicard.digital_channel_switch(self.channel, True)