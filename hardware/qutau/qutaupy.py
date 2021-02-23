# -*- coding: utf-8 -*-
"""
qutaupy
=======

Python wrapper for Qutau DLL.

Copyright John Jarman 2020

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This code also includes function descriptions in docstrings modified from QuTAU 
header files, available from qutools.com. These parts are copyright qutools 
GmbH, and are used under the qutools software licence, reproduced below.

qutools software licence (for function docstrings):

    This software can be used and distributed freely.
    The authors grant the following rights to every user:

    - to use the software without any restrictions

    - to redistribute the unchanged software

    - to change the components of the software that are
    provided in human readable form and to distribute changed
    components separately from the rest of the software.
"""

import ctypes as ct
import enum
import numpy as np
import copy
import os


class errors(enum.IntEnum):
    """
    Return codes
    """
    TDC_OK = 0
    TDC_Error = -1
    TDC_Timeout = 1
    TDC_NotConnected = 2
    TDC_DriverError = 3
    TDC_DeviceLocked = 7
    TDC_Unknown = 8
    TDC_NoDevice = 9
    TDC_OutOfRange = 10
    TDC_CantOpen = 11
    TDC_NotInitialized = 12
    TDC_NotEnabled = 13
    TDC_NotAvailable = 14


class TDC_DevType(enum.IntEnum):
    """
    Device types
    """
    DEVTYPE_ANY = -1
    DEVTYPE_1A = 0  # 1A: QuTAU - no signal conditioning
    DEVTYPE_1B = 1  # 1B: QuTAU - 8 channel signal conditioning
    DEVTYPE_1C = 2  # 1C: QuPSI - 3 channel signal conditioning
    DEVTYPE_2A = 3  # 2A: QuTAG - 5 channel signal conditioning
    DEVTYPE_NONE = 4


class TDC_FileFormat(enum.IntEnum):
    """
    File formats for saving/loading timestamps
    """
    FORMAT_ASCII = 0
    FORMAT_BINARY = 1
    FORMAT_COMPRESSED = 2
    FORMAT_NONE = 3


class TDC_SignalCond(enum.IntEnum):
    """
    Signal conditioning modes
    """
    SCOND_TTL = 0
    SCOND_LVTTL = 1
    SCOND_NIM = 2
    SCOND_MISC = 3
    SCOND_NONE = 4


class QuTauError(Exception):
    """ Exception raised for QuTAU errors.

    Attributes
    ---
    - 'value': Error code. This is the return code from the QuTAU DLL function
        that caused the exception to be raised.
    - 'msg': Human-readable description of the error (one of the values in the
        errors enum)
    """

    def __init__(self, value, msg=''):
        """
        @param int value: Return code
        @param str msg: Optional message to add to exception
        """
        super().__init__(self)
        self.value = value
        try:
            self.msg = errors(value).name
        except ValueError:
            self.msg = 'Unknown error'

        if msg:
            self.msg += (': ' + msg)

    def __str__(self):
        return "{}: {}".format(self.value, self.msg)

    def __repr__(self):
        return "{}: {}".format(self.value, self.msg)

    def __eq__(self, other):
        return self.value == other

    def __hash__(self):
        return hash(self.value)

    def __ne__(self, other):
        return self.value != other


class QuTau:
    """
    Python wrapper around QuTau DLL functions.

    Functions are methods of this class, with the leading TDC_ removed
    compared to the Qutau DLL header files.

    Non-zero return values from DLL methods raise QuTauError.
    DLL functions that return multiple values via pointers return these values
    in a dict with keys that correspond to the variable names given in the C
    header files.
    """

    def __init__(self, dll_name='tdcbase.dll',
                 dll_path="C:\\Program Files (x86)\\qutools\\quTAU\\userlib\\lib64\\"):
        """Loads qutau DLL and sets up ctypes argtypes and restypes.
        @param str dll_name: Optional - name of DLL. Defaults to 'tdcbase.dll'
        @param str dll_path: Optional - path to DLL. Defaults to qutau install
            directory. Adds this to os.environ['PATH'] by default. Set to None 
            to suppress this behaviour.
        """
        # Load qutau DLL
        if dll_path is not None:
            os.environ["PATH"] += os.pathsep + dll_path
        self.tdcbase = ct.windll.LoadLibrary(dll_name)

        # Set argument and return types as defined in header files

        ###########
        # tdcbase.h
        ###########
        self.tdcbase.TDC_getVersion.restype = ct.c_double

        self.tdcbase.TDC_perror.argtypes = [ct.c_int]
        self.tdcbase.TDC_perror.restype = ct.c_char_p

        self.tdcbase.TDC_getTimebase.argtypes = [ct.POINTER(ct.c_double)]
        self.tdcbase.TDC_getTimebase.restype = ct.c_int

        self.tdcbase.TDC_init.argtypes = [ct.c_int]
        self.tdcbase.TDC_init.restype = ct.c_int

        self.tdcbase.TDC_deInit.restype = ct.c_int

        self.tdcbase.TDC_getDevType.restype = ct.c_int

        self.tdcbase.TDC_checkFeatureHbt.restype = ct.c_bool

        self.tdcbase.TDC_checkFeatureLifeTime.restype = ct.c_bool

        self.tdcbase.TDC_configureSignalConditioning.argtypes = [
            ct.c_int, ct.c_int, ct.c_bool, ct.c_bool, ct.c_double]
        self.tdcbase.TDC_configureSignalConditioning.restype = ct.c_int

        self.tdcbase.TDC_getSignalConditioning.argtypes = [ct.c_int, ct.POINTER(
            ct.c_bool), ct.POINTER(ct.c_bool), ct.POINTER(ct.c_double)]
        self.tdcbase.TDC_getSignalConditioning.restype = ct.c_int

        self.tdcbase.TDC_getSyncDivider.argtypes = [
            ct.POINTER(ct.c_int), ct.POINTER(ct.c_bool)]
        self.tdcbase.TDC_getSyncDivider.restype = ct.c_int

        self.tdcbase.TDC_configureSyncDivider.argtypes = [ct.c_int, ct.c_bool]
        self.tdcbase.TDC_configureSyncDivider.restype = ct.c_int

        self.tdcbase.TDC_enableChannels.argtypes = [ct.c_int]
        self.tdcbase.TDC_enableChannels.restype = ct.c_int

        self.tdcbase.TDC_setCoincidenceWindow.argtypes = [ct.c_int]
        self.tdcbase.TDC_setCoincidenceWindow.restype = ct.c_int

        self.tdcbase.TDC_setExposureTime.argtypes = [ct.c_int]
        self.tdcbase.TDC_setExposureTime.restype = ct.c_int

        self.tdcbase.TDC_getDeviceParams.argtypes = [ct.POINTER(
            ct.c_int), ct.POINTER(ct.c_int), ct.POINTER(ct.c_int)]
        self.tdcbase.TDC_getDeviceParams.restype = ct.c_int

        self.tdcbase.TDC_setChannelDelays.argtypes = [ct.POINTER(ct.c_int)]
        self.tdcbase.TDC_setChannelDelays.restype = ct.c_int

        self.tdcbase.TDC_getChannelDelays.argtypes = [ct.POINTER(ct.c_int)]
        self.tdcbase.TDC_getChannelDelays.restype = ct.c_int

        self.tdcbase.TDC_setDeadTime.argtypes = [ct.c_int]
        self.tdcbase.TDC_setDeadTime.restype = ct.c_int

        self.tdcbase.TDC_getDeadTime.argtypes = [ct.POINTER(ct.c_int)]
        self.tdcbase.TDC_getDeadTime.restype = ct.c_int

        self.tdcbase.TDC_configureSelftest.argtypes = [
            ct.c_int, ct.c_int, ct.c_int, ct.c_int]
        self.tdcbase.TDC_configureSelftest.restype = ct.c_int

        self.tdcbase.TDC_getDataLost.argtypes = [ct.POINTER(ct.c_bool)]
        self.tdcbase.TDC_getDataLost.restype = ct.c_int

        self.tdcbase.TDC_setTimestampBufferSize.argtypes = [ct.c_int]
        self.tdcbase.TDC_setTimestampBufferSize.restype = ct.c_int

        self.tdcbase.TDC_getTimestampBufferSize.argtypes = [
            ct.POINTER(ct.c_int)]
        self.tdcbase.TDC_getTimestampBufferSize.restype = ct.c_int

        self.tdcbase.TDC_enableTdcInput.argtypes = [ct.c_bool]
        self.tdcbase.TDC_enableTdcInput.restype = ct.c_int

        self.tdcbase.TDC_freezeBuffers.argtypes = [ct.c_bool]
        self.tdcbase.TDC_freezeBuffers.restype = ct.c_int

        self.tdcbase.TDC_getCoincCounters.argtypes = [
            ct.POINTER(ct.c_int), ct.POINTER(ct.c_int)]
        self.tdcbase.TDC_getCoincCounters.restype = ct.c_int

        self.tdcbase.TDC_getLastTimestamps.argtypes = [ct.c_bool, ct.POINTER(
            ct.c_int64), ct.POINTER(ct.c_int8), ct.POINTER(ct.c_int)]
        self.tdcbase.TDC_getLastTimestamps.restype = ct.c_int

        self.tdcbase.TDC_writeTimestamps.argtypes = [ct.c_char_p, ct.c_int]
        self.tdcbase.TDC_writeTimestamps.restype = ct.c_int

        self.tdcbase.TDC_readTimestamps.argtypes = [ct.c_char_p, ct.c_int]
        self.tdcbase.TDC_readTimestamps.restype = ct.c_int

        self.tdcbase.TDC_inputTimestamps.argtypes = [ct.POINTER(
            ct.c_int64), ct.POINTER(ct.c_int8), ct.POINTER(ct.c_int)]
        self.tdcbase.TDC_inputTimestamps.restype = ct.c_int

        self.tdcbase.TDC_generateTimestamps.argtypes = [
            ct.c_int, ct.POINTER(ct.c_double), ct.c_int]
        self.tdcbase.TDC_generateTimestamps.restype = ct.c_int

        ################
        # tdcstartstop.h
        ################
        self.tdcbase.TDC_enableStartStop.argtypes = [ct.c_bool]
        self.tdcbase.TDC_enableStartStop.restype = ct.c_int

        self.tdcbase.TDC_setHistogramParams.argtypes = [ct.c_int, ct.c_int]
        self.tdcbase.TDC_setHistogramParams.restype = ct.c_int

        self.tdcbase.TDC_getHistogramParams.argtypes = [
            ct.POINTER(ct.c_int), ct.POINTER(ct.c_int)]
        self.tdcbase.TDC_getHistogramParams.restype = ct.c_int

        self.tdcbase.TDC_clearAllHistograms.restype = ct.c_int

        self.tdcbase.TDC_getHistogram.argtypes = [
            ct.c_int, ct.c_int, ct.c_bool] + [ct.POINTER(ct.c_int)] * 6 + [ct.POINTER(ct.c_int64)]
        self.tdcbase.TDC_getHistogram.restype = ct.c_int

    #####################
    # tdcbase.h functions
    #####################
    def getVersion(self):
        """
        Get version of dll
        @return float: version number
        """
        return self.tdcbase.TDC_getVersion()

    def _perror(self, rc):
        """
        Get readable message from return code
        @param int rc: return code
        @return str: error message
        """
        return self.tdcbase.TDC_perror(rc).value.decode('utf-8')

    def getTimebase(self):
        """
        Get timebase in seconds
        @return float: timebase in seconds (usually ~8.09552722121028e-11)
        """
        timebase = ct.c_double()
        rc = self.tdcbase.TDC_getTimebase(timebase)
        if rc != 0:
            raise QuTauError(rc)
        return timebase.value

    def init(self, deviceId=-1):
        """
        Initialise device
        @param int deviceId: Look for a device with this deviceId
        """
        rc = self.tdcbase.TDC_init(deviceId)
        if rc != 0:
            raise QuTauError(rc)

    def deInit(self):
        """
        De-initialise device
        """
        rc = self.tdcbase.TDC_deInit()
        if rc != 0:
            raise QuTauError(rc)

    def getDevType(self):
        """
        Get device type
        @return int: device type (enumerated in TDC_DevType)
        """
        return self.tdcbase.TDC_getDevType()

    def checkFeatureHbt(self):
        """
        Check if HBT calculating feature is available
        @return int: 1 = feature available, 0 = unavailable
        """
        return self.tdcbase.TDC_checkFeatureHbt()

    def checkFeatureLifeTime(self):
        """
        Check if Lifetime calculating feature is available
        @return int: 1 = feature available, 0 = unavailable
        """
        return self.tdcbase.TDC_checkFeatureLifeTime()

    def configureSignalConditioning(self, channel, conditioning, edge, term, threshold):
        """
        Configure signal conditioning for specific channel
        @param int channel: Channel number
        @param int conditioning: Signal conditioning (one of the values in the 
            enum TDC_SignalCond)
        @param bool edge: Rising (true) or falling (false) edge
        @param bool term: 50 ohm termination on (true) or off (false)
        @param double threshold: Voltage threshold that is used to identify 
            events, in V. Allowed range is -2 ... 3V; internal resolution is 
            1.2mV
        """
        rc = self.tdcbase.TDC_configureSignalConditioning(
            channel, conditioning, edge, term, threshold)
        if rc != 0:
            raise QuTauError(rc)

    def getSignalConditioning(self, channel):
        """
        Read-back signal conditioning values
        @param int channel: Channel number
        @return dict: Signal conditioning values, as follows:
            'on':bool signal conditioning enabled
            'edge':bool rising (true)/falling (false)
            'term':bool 50 ohm termination on (true) or off (false)
            'threshold':float Voltage threshold (V)
        """
        on = ct.c_bool()
        edge = ct.c_bool()
        threshold = ct.c_double()

        rc = self.tdcbase.TDC_getSignalConditioning(
            channel, on, edge, threshold)

        if rc != 0:
            raise QuTauError(rc)

        return {
            'on': on.value,
            'edge': edge.value,
            'term': term.value,
            'threshold': threshold.value
        }

    def configureSyncDivider(self, divider, reconstruct):
        """
        Configures the input divider of channel 0 if available.
        The divider does not work if the signal conditioning is switched off
         (see configureSignalConditioning).
        @param int divider: Number of events to skip before one is passed + 1.
            Only the following values are allowed:
            1A:  Function not available, TDC_OutOfRange is returned
            1B:  1, 8, 16, 32, 64, 128
            1C:  Ignored, divider is always 1024
            2A:  1, 2, 4, 8
        @param bool reconstruct: Reconstruct the skipped events in software.
        """
        rc = self.tdcbase.TDC_configureSyncDivider(divider, reconstruct)
        if rc != 0:
            raise QuTauError(rc)

    def getSyncDivider(self):
        """
        Get status of sync divider on channel 0, if available
        @return dict: status of sync divider:
        'divider':int,
        'reconstruct':bool,
        'return_code':int
        """
        divider = ct.c_int()
        reconstruct = ct.c_bool()
        rc = self.tdcbase.TDC_getSyncDivider(divider, reconstruct)
        if rc != 0:
            raise QuTauError(rc)
        return {
            'divider': divider.value,
            'reconstruct': reconstruct.value
        }

    def enableChannels(self, channelMask):
        """
         Enable TDC Channels

         Selects the channels that contribute to the output stream.
         @param int channelMask  Bitfield with activation flags for every TDC 
            channel. (e.g. 5 means activate channels 1 and 3)
        """
        rc = self.tdcbase.TDC_enableChannels(channelMask)
        if rc != 0:
            raise QuTauError(rc)

    def setChannelDelays(self, delays=[]):
        """
        Set Channel Delay Times

        Different signal runtimes cause relative delay times of the signals
        at different channels. The function allows to configure a delay per
        channel that will be compensated including the changed sorting of events.
        If not set, all delays are 0.
        The compensation is carried out in hardware for 2a devices (fast),
        and in PC software for 1a, 1b, and 1c (CPU consuming).
        The software runtime compensation consumes a lot of CPU power
        (caused by the required timstamp reordering) and therefore limits
        the available data rate seriously.
        If all delays are 0, the expensive reordering is circumvented.
        @param list of ints delays  Input: channel delays, in TDC units.
                        If list is less than 8 members long, delays for
                        unspecified channels are set to zero. All set to zero if
                        no delays specified.
        """
        if len(delays) > 8:
            raise IndexError('delays must be a list of length 8 or smaller')

        int_array = ct.c_int * 8
        c_delays = int_array(*delays)

        rc = self.tdcbase.TDC_setChannelDelays(c_delays)
        if rc != 0:
            raise QuTauError(rc)

    def getChannelDelays(self):
        """
        Read back Channel Delay Times

        Reads back the delay times as set with @ref TDC_setChannelDelays.
        @return delays: list of channel delays, in TDC units.
        """
        int_array = ct.c_int * 8
        delays = int_array()
        rc = self.tdcbase.TDC_getChannelDelays(delays)
        if rc != 0:
            raise QuTauError(rc)
        return np.ctypeslib.as_array(delays, shape=8)

    def setDeadTime(self, dTime):
        """
        Set Dead Time

        Sets a dead time for all input channels. After detecting an event,
        all subsequent events on the same channel are ignored for this time.
        The feature is only available in 2a (quTAG) devices; in other cases
        @ref TDC_OutOfRange is returned.
        @param  dTime   Dead time for all channels, in ps.
                        Must be positive.
        """
        rc = self.tdcbase.TDC_setDeadTime(dTime)
        if rc != 0:
            raise QuTauError(rc)

    def getDeadTime(self):
        """
        Read back Dead Time

        Reads back the dead time as set with @ref TDC_setDeadTime.
        @param  dTime   Ouput: dead time, in ps
        """
        dTime = ct.c_int
        rc = self.tdcbase.TDC_getDeadTime(dTime)
        if rc != 0:
            raise QuTauError(rc)
        return dTime.value

    def setCoincidenceWindow(self, coincWin):
        """
        Set Coincidence Window

        Sets the coincidence time window for the integrated coincidence counting.
        @param int coincWin   Coincidence window in bins, Range = 0 ... 65535,
                        see @ref TDC_getTimebase
        """
        rc = self.tdcbase.TDC_setCoincidenceWindow(coincWin)
        if rc != 0:
            raise QuTauError(rc)

    def setExposureTime(self, time):
        """
        Set Exposure Time

        Sets the exposure time (or integration time) of the internal coincidence
        counters.
        @param int expTime   Exposure time in ms, Range = 0 ... 65535
        """
        rc = self.tdcbase.TDC_setExposureTime(time)
        if rc != 0:
            raise QuTauError(rc)

    def getDeviceParams(self, channelMask, coincWin, expTime):
        """
        Read Back Device Parameters

        Reads the device parameters back from the device.
        @return dict of parameters:
        'channelMask' int: 	Enabled channels, see @ref TDC_enableChannels
        'coincWin' int: 	Coincidence window, see @ref TDC_setCoincidenceWindow
        'expTime' int:     	Output: Exposure time, see @ref TDC_setExposureTime
        """
        channelMask = ct.c_int()
        coincWin = ct.c_int()
        expTime = ct.c_int()
        rc = self.tdcbase.TDC_getDeviceParams(channelMask, coincWin, expTime)
        if rc != 0:
            raise QuTauError(rc)
        return {
            'channelMask': channelMask.value,
            'coincWin': coincWin.value,
            'expTime': expTime.value
        }

    def configureSelftest(self, channelMask, period, burstSize, burstDist):
        """
        Configure Selftest

        The function enables the internal generation of test signals that are
        input to the device. It is mainly used for testing.
        @param int channelMask  Bitfield that selects the channels to be fired internally
                             (e.g. 5 means signal generation on channels 1 and 3)
        @param int period       Period of all test singals in units of 20ns, Range = 2 ... 60
        @param int burstSize    Number of periods in a burst, Range = 1 ... 65535
        @param int burstDist    Distance between bursts in units of 80ns, Range = 0 ... 10000
        """
        rc = self.tdcbase.TDC_configureSelftest(
            channelMask, period, burstSize, burstDist)
        if rc != 0:
            raise QuTauError(rc)

    def getDataLost(self):
        """
        Check for data loss

        Timestamps of events detected by the device can get lost if their rate
        is too high for the USB interface or if the PC is unable to receive the
        data in time. The TDC recognizes this situation and signals it to the
        PC (with high priority).

        The function checks if a data loss situation is currently detected or if
        it has been latched since the last call. If you are only interested in
        the current situation, call the function twice; the first call will
        delete the latch.
        @return bool: Current and latched data loss state.
        """
        lost = ct.c_bool()
        rc = self.tdcbase.TDC_getDataLost(lost)
        if rc != 0:
            raise QuTauError(rc)
        return lost.value

    def setTimestampBufferSize(self, size):
        """
        Set Timestamp Buffer Size

        Sets the size of a ring buffer that stores the timestamps of the last
        detected events. The buffer's contents can be retrieved with
        TDC_getLastTimestamps. By default, the buffersize is 0.
        When the function is called, the buffer is cleared.
        @param int size      Buffer size; Range = 1 ... 1000000
        """
        rc = self.tdcbase.TDC_setTimestampBufferSize(size)
        if rc != 0:
            raise QuTauError(rc)

    def getTimestampBufferSize(self):
        """
         Read back Timestamp Buffer Size

        Reads back the buffer size as set by @ref TDC_setTimestampBufferSize.
        @return int: Buffer size
        """
        size = ct.c_int()
        rc = self.tdcbase.TDC_getTimestampBufferSize(size)
        if rc != 0:
            raise QuTauError(rc)
        return size.value

    def enableTdcInput(self, enable):
        """
        Enable Physical Input

        Enables input from the physical channels of the TDC device or the
        internal selftest. If disabled, the software ignores those "real" events,
        the device and its coincidence counters are not affected.
        By default the input is enabled.

        When working with software input (@ref TDC_readTimestamps,
        @ref TDC_generateTimestamps, ...) this function can be used to avoid
        real and simulated input to be mixed up.
        @param bool enable    Enable (1) or disable (0) TDC input
        """
        rc = self.tdcbase.TDC_enableTdcInput(enable)
        if rc != 0:
            raise QuTauError(rc)

    def freezeBuffers(self, freeze):
        """
        Freeze internal Buffers

        The function can be used to freeze the internal buffers,
        allowing to retrieve multiple histograms with the same
        integration time. When frozen, no more events are added to
        the built-in histograms and timestamp buffer. The coincidence
        counters are not affected. Initially, the buffers are not frozen.
        All types of histograms calculated by software are affected.
        @param bool freeze    freeze (1) or activate (0) the buffers
        """
        rc = self.tdcbase.TDC_freezeBuffers(freeze)
        if rc != 0:
            raise QuTauError(rc)

    def getCoincCounters(self):
        """
        Retrieve Coincidence Counters

        Retrieves the most recent values of the built-in coincidence counters.
        The coincidence counters are not accumulated, i.e. the counter values for
        the last exposure (see @ref TDC_setExposureTime ) are returned.

        The array contains count rates for all 8 channels, and rates for
        two, three, and fourfold coincidences of events detected on different
        channels out of the first 4. Events are coincident if they happen
        within the coincidence window (see @ref TDC_setCoincidenceWindow ).
        @return dict of return values:
        'data':tuple     Output: Counter Values. The array must have at least
                         19 elements. The Counters come in the following order:
                         1, 2, 3, 4, 5, 6, 7, 8, 1/2, 1/3, 1/4, 2/3, 2/4, 3/4,
                         1/2/3, 1/2/4, 1/3/4, 2/3/4, 1/2/3/4
        'updates'   Output: Number of data updates by the device since the last call.
                         Pointer may be NULL.
        """
        datatype = ct.c_int * 31
        data = datatype()
        updates = ct.c_int()
        rc = self.tdcbase.TDC_getCoincCounters(data, updates)
        if rc != 0:
            raise QuTauError(rc)

        data_py = np.ctypeslib.as_array(data, shape=31)

        return {
            'data': data_py,
            'updates': updates.value
        }

    def getLastTimestamps(self, reset):
        """
        Retrieve Last Timestamp Values

        Retrieves the timestamp values of the last n detected events on all
        TDC channels. The buffer size must have been set with
        @ref setTimestampBufferSize , otherwise 0 data will be returned.
        @param bool reset      If the data should be cleared after retrieving.
        @return dict of values:
        'timestamps' numpy.array: Timestamps of the last events in base units,
                          see @ref TDC_getTimebase.
        'channels' numpy.array: Numbers of the channels where the events have been
                          detected. Every array element belongs to the timestamp
                          with the same index. Range is 0...7 for channels 1...8.
        'valid'          : Number of valid entries in the above arrays.
                          May be less than the buffer size if the buffer has been cleared.
        """
        bufsize = self.getTimestampBufferSize()
        timestamps = [ct.c_int64()] * bufsize
        channels = [ct.c_int8()] * bufsize
        valid = ct.c_int32()
        rc = self.tdcbase.TDC_getLastTimestamps(
            reset, timestamps, channels, valid)
        timestamps_py = np.ctypeslib.as_array(timestamps, shape=valid.value)
        channels_py = np.ctypeslib.as_array(channels, shape=valid.value)
        if rc != 0:
            raise QuTauError(rc)
        return {
            'timestamps': timestamps_py,
            'channels': channels_py,
            'valid': valid
        }

    def writeTimestamps(self, filename, f):
        """
        Write Timestamp Values to File

        Starts or stops writing the timestamp values to a file continously.
        The timestamps written are already corrected by the detector delays,
        see @ref TDC_setChannelDelays.

        Timestamps come in base units, see @ref TDC_getTimebase;
        channel Numbers range from 0 to 7 in binary formats, from 1 to 8 in ASCII.
        The follwing file formats are available:

        ASCII:      Timestamp values (int base units) and channel numbers
                    as decimal values in two comma separated columns.
                    Channel numbers range from 1 to 8 in this format.

        binary:     A binary header of 40 bytes, records of 10 bytes,
                    8 bytes for the timestamp, 2 for the channel number,
                    stored in little endian (Intel) byte order.

        compressed: A binary header of 40 bytes, records of 40 bits (5 bytes),
                    37 bits for the timestamp, 3 for the channel number,
                    stored in little endian (Intel) byte order.

        raw:        Like binary, but without header. Provided for backward
                    compatiblity.

        The header of the binary formats is dedicated for use in @ref TDC_readTimestamps;
        it should be skipped when evaluating with external tools.

        Writing in the ASCII format requires much more CPU power and about twice as much
        disk space than using the binary format. The compressed format again saves
        half of the disk space, allowing higher event rates with not-so-fast disks.
        The Timestamps are truncated in this format leading to an overflow every 11 s.
        It is possible to convert a binary file to ASCII format offline by using this
        function together with @ref TDC_readTimestamps.

        If the specified file exists it will be overwritten.
        The function checks if the file can be opened; write errors that occur
        later in the actual writing process (disk full e.g.) will not be reported.
        @param str filename   Name of the file to use. To stop writing, call 
                        the function with an empty or null filename.
        @param TDC_FileFormat format Output format. Meaningless if writing is to be stopped.
                        FORMAT_NONE also stops writing.
        """
        filename_bytes = ct.c_char_p(bytes(filename, encoding='utf-8'))
        rc = self.tdcbase.TDC_writeTimestamps(filename_bytes, f)
        if rc != 0:
            raise QuTauError(rc)

    def inputTimestamps(self, timestamps, channels):
        """
        Input Synthetic Timestamps

        The function allows to input synthetic timestamps for demonstration
        and simulation purposes. Timesamps are processed just like "raw"
        data from a real device.
        is connected; otherwise it will return an error.
        @param timestamps Input: Array of timestamps to process.
                          The timestamps should be in strictly increasing order,
                          otherwise some functions will fail.
        @param channels   Input: Array of corresponding channel numbers.
        """
        if len(timestamps) != len(channels):
            raise QuTauError(errors.TDC_OutOfRange,
                             msg='Timestamp and channel data must be same length')
        # Create appropriate datatypes for length of data
        c_long_array = ct.c_int64 * len(timestamps)
        c_byte_array = ct.c_int8 * len(channels)

        # Send timestamp data
        rc = self.tdcbase.TDC_inputTimestamps(
            c_long_array(*timestamps), c_byte_array(*channels))
        if rc != 0:
            raise QuTauError(rc)

    def readTimestamps(self, filename, f):
        """
        Read Timestamps

        The function allows to read timestamps from file for demonstration or
        delayed processing. It works only with files in a binary format
        (see @ref TDC_FileFormat). It can read files with or without the
        40 bytes header. When the header is present in demo mode (i.e. without
        a device connected), the HBT and Lifetime options from the source
        device come into effect.

        In the compressed format, the reconstruction of the original timestamps
        can't be guaranteed.  Detector delays (see @ref TDC_setChannelDelays)
        are @em not compensated in this function because this is already
        done in @ref TDC_writeTimestamps.
        @param str filename   Name of the binary input file
        @param TDC_FileFormat format     Input format. Only binary formats are valid.
                          If the file has a valid header, the parameter is not used;
                          the format is retrieved from the file itself.
        """
        filename_bytes = ct.c_char_p(bytes(filename, encoding='utf-8'))
        rc = self.tdcbase.TDC_readTimestamps(filename_bytes, f)
        if rc != 0:
            raise QuTauError(rc)

    def generateTimestamps(self, diff_type, par, count):
        """
        Generate Timestamps

        The function generates synthetic timestamps for demonstration
        and simulation purposes. Timesamps are processed just like "raw"
        data from a real device.

        The channel mask (see @ref TDC_enableChannels) is considered. At least
        one channel has to be enabled!
        @param diff_type int Type of time diff distribution (0 = flat, 1 = gaussian)
        @param par:    [centre, width] of time diff distribution
        @param count int           Number of timestamps to generate
        """
        double_array = ct.c_double * 2
        c_par = double_array(*par)
        rc = self.tdcbase.TDC_generateTimestamps(diff_type, c_par, count)
        if rc != 0:
            raise QuTauError(rc)

    ###############
    # tdcstartstop.h
    ###############
    def enableStartStop(self, enable):
        """
        Enable Start Stop Histograms

        Enables the calculation of start stop histograms. When enabled, all incoming
        events contribute to the histograms. When disabled, all corresponding functions
        are unavailable. Disabling saves a relevant amount of memory and CPU load.
        The function implicitly clears the histograms.
        Use @ref TDC_freezeBuffers to interrupt the accumulation of events without
        clearing the functions and @ref TDC_clearAllHistograms to clear without
        interrupt.
        @param bool enable  Enable or disable
        """
        rc = self.tdcbase.TDC_enableStartStop(enable)
        if rc != 0:
            raise QuTauError(rc)

    def setHistogramParams(self, binWidth, binCount):
        """
        Set Start Stop Histogram Parameters

        Sets parameters for the internally generated start stop histograms.
        If the function is not called, default values are in place.
        When the function is called, all collected histogram data are cleared.
        @param binWidth  Width of the histogram bins in units of the TDC Time Base,
                         see @ref TDC_getTimebase . Range = 1 ... 1000000, default = 1.
        @param binCount  Number of bins in the histogram buffers.
                         Range = 2 ... 1000000, default = 10000.
        """

        rc = self.tdcbase.TDC_setHistogramParams(binWidth, binCount)
        if rc != 0:
            raise QuTauError(rc)

    def getHistogramParams(self):
        """
        Read back Start Stop Histogram Parameters

        Reads back the parameters that have been set with @ref TDC_setHistogramParams.
        All output parameters may be NULL to ignore the value.
        @return dict:
        'binWidth'  int: Width of the histograms bins.
        'binCount'  int: Number of bins in the histogram buffers.
        """
        binWidth = ct.c_int()
        binCount = ct.c_int()
        rc = self.tdcbase.TDC_getHistogramParams(binWidth, binCount)
        if rc != 0:
            raise QuTauError(rc)
        return {
            'binWidth': binWidth.value,
            'binCount': binCount.value
        }

    def addHistogram(self, startCh, stopCh, add=True):
        """
        Adds or removes a histogram with specified start and stop channels.

        All time differences beween a start and the first following stop event
        will contribute to the histogram.

        A channel independent histogram that integrates all events is always
        provided and hasn't to be added, see @ref TDC_getHistogram.
        @param startCh channel number of the histogram's start channel, Range = 0...20
        @param stopCh  channel number of the histogram's stop channel, Range = 1...20
        @param add     add (true) or remove (false) the histogram. If an
                       existing histogram is added or a missing
                       histogram is removed, nothing happens.
        """
        self.tdcbase.TDC_addHistogram.argtypes = [ct.c_int, ct.c_int, ct.c_int]
        self.tdcbase.TDC_addHistogram.restype = ct.c_int
        
        rc = self.tdcbase.TDC_addHistogram(startCh, stopCh, add)
        if rc != 0:
            raise QuTauError(rc)

    def clearAllHistograms(self):
        """
        Clear Start Stop Histograms

        Clears all internally generated start stop histograms,
        i.e. all bins are set to 0.
        """

        rc = self.tdcbase.TDC_clearAllHistograms()
        if rc != 0:
            raise QuTauError(rc)

    def getHistogram(self, chanA, chanB, reset):
        """
        Retrieve Start Stop Histogram

        Retrieves one of the start stop histograms accumulated internally.
        One histogram is provided for the time differences of every event
        the device has detected (channel independent). 64 histograms are
        provided for the time differences of events detected on different
        channels. Events on the first channel reset the time counter,
        events on the second one integrate the current counter value in
        the Histogram.
        @param int chanA     First TDC channel of the channel pair. Range 0...7
                         begins with 0 for channel 1.
                         If this parameter is out of range (negative e.g.)
                         the channel independent histogram is retrieved.
        @param int chanB     Second TDC channel of the channel pair (0...7).
                         If this parameter is out of range (negative e.g.)
                         the channel independent histogram is retrieved.
        @param bool reset     If the histogram should be cleared after retrieving.
        @return dict of output:
        'data'      Output: Histogram data. The array must have at least
                         binCount (see @ref TDC_setHistogramParams ) elements.
                         A NULL pointer is allowed to ignore the data.
        'count'     Output: Total number of time diffs in the histogram.
                         A NULL pointer is allowed to ignore the data.
        'tooSmall'  Output: Number of time diffs that were smaller
                         than the smallest histogram bin.
                         A NULL pointer is allowed to ignore the data.
        'tooLarge'  Output: Number of time diffs that were bigger
                         than the biggest histogram bin.
                         A NULL pointer is allowed to ignore the data.
        'eventsA'   Output: Number of events detected on the first channel
                         contributing to the histogram.
                         A NULL pointer is allowed to ignore the data.
        'eventsB'   Output: Number of events detected on the second channel
                         contributing to the histogram.
                         A NULL pointer is allowed to ignore the data.
        'expTime'   Output: Total exposure time for the histogram: the time
                         difference between the first and the last event
                         that contribute to the histogram. In timebase units.
                         A NULL pointer is allowed to ignore the data.

        Also contains 'binCount' and 'binWidth' since it has to call
        getHistogramParams anyway.
        """
        # Get histogram size
        histogram_params = self.getHistogramParams()

        # Create array of appropriate size to receive data
        data_array = ct.c_int * histogram_params['binCount']
        data = data_array()
        count, tooSmall, tooLarge, eventsA, eventsB = [ct.c_int()] * 5
        expTime = ct.c_int64()

        rc = self.tdcbase.TDC_getHistogram(
            chanA,
            chanB,
            reset,
            data,
            count,
            tooSmall,
            tooLarge,
            eventsA,
            eventsB,
            expTime
        )

        # Convert to numpy array
        data_py = np.ctypeslib.as_array(
            data, shape=histogram_params['binCount'])

        if rc != 0:
            raise QuTauError(rc)

        return {
            'data': data_py,
            'count': count.value,
            'tooSmall': tooSmall.value,
            'tooLarge': tooLarge.value,
            'eventsA': eventsA.value,
            'eventsB': eventsB.value,
            'expTime': expTime.value,
            'binCount': histogram_params['binCount'],
            'binWidth': histogram_params['binWidth']
        }
