# -*- coding: utf-8 -*-

""" LabView RSRC file format instrument info / save record.

    Various general properties of the RSRC file.
"""

# Copyright (C) 2013 Jessica Creighton <jcreigh@femtobit.org>
# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import enum

from hashlib import md5
from io import BytesIO
from types import SimpleNamespace
from ctypes import *

from LVmisc import *
from LVblock import *


class VI_TYPE(enum.Enum):
    """ VI Type from LVSR/LVIN field
    """
    Invalid = 0	# invalid VI type
    Standard = 1	# VI that contains a front panel and block diagram
    Control = 2	# subVI that defines a custom control or indicator
    Global = 3	# subVI generated when creating global variables
    Polymorph = 4	# subVI that is an instance of a polymorphic VI
    Config = 5	# Configuration VI
    Subsystem = 6	# subVI that can be only placed on a simulation diagram
    Facade = 7	# subVI that represents a Facade ability, which defines the appearance of an XControl
    Method = 8	# subVI added to the XControl Library for each XControl method
    StateChart = 9	# subVI that you can place only on a statechart diagram


class VI_FP_FLAGS(enum.Enum):
    """ VI Front Panel Flags
    """
    ShowScrollBar = ((1 << 0) | (1 << 1))	 # Indicates whether to display the scroll bars on the front panel.
    Bit2 = 1 << 2	# unknown
    ToolBarVisible = 1 << 3	# Indicates whether to display the toolbar while the VI runs.
    ShowMenuBar = 1 << 4	# 	Indicates whether to display the menu bar on the front panel while the VI runs.
    AutoCenter = 1 << 5	# Marked as deprecated in LV2019
    SizeToScreen = 1 << 6	# Marked as deprecated in LV2019
    NoRuntimePopUp = 1 << 7	# Indicates whether to display shortcut menus for front panel objects while the VI runs.
    MarkReturnBtn = 1 << 8	# Indicates whether to highlight Boolean controls that have a shortcut key of <Enter>.
    Bit9 = 1 << 9	# unknown
    Bit10 = 1 << 10	# unknown
    Bit11 = 1 << 11	# unknown
    Bit12 = 1 << 12	# unknown
    Bit13 = 1 << 13	# unknown
    Bit14 = 1 << 14	# unknown
    Bit15 = 1 << 15	# unknown


class VI_BTN_HIDE_FLAGS(enum.Enum):
    """ VI Tool Bar Buttons Hidding flags
    """
    RunButton = 1 << 0	# Indicates whether to display the Run button on the toolbar while the VI runs.
    Bit1 = 1 << 1	# unknown
    Bit2 = 1 << 2	# unknown
    Bit3 = 1 << 3	# unknown
    Bit4 = 1 << 4	# unknown
    FreeRunButton = 1 << 5	# Indicates whether to display the Run Continuously button on the toolbar while the VI runs.
    Bit6 = 1 << 6	# unknown
    AbortButton = 1 << 7	# Indicates whether to display the Abort Execution button on the toolbar while the VI runs.
    Bit8 = 1 << 8	# unknown
    Bit9 = 1 << 9	# unknown
    Bit10 = 1 << 10	# unknown
    Bit11 = 1 << 11	# unknown
    Bit12 = 1 << 12	# unknown
    Bit13 = 1 << 13	# unknown
    Bit14 = 1 << 14	# unknown
    Bit15 = 1 << 15	# unknown


class VI_IN_ST_FLAGS(enum.Enum):
    """ VI Insrument State flags
    """
    Bit0 = 1 << 0	# Indicates whether to display the Run button on the toolbar while the VI runs.
    Bit1 = 1 << 1	# unknown
    Bit2 = 1 << 2	# unknown
    Bit3 = 1 << 3	# unknown
    Bit4 = 1 << 4	# unknown
    Bit5 = 1 << 5	# unknown
    Bit6 = 1 << 6	# unknown
    Bit7 = 1 << 7	# unknown
    Bit8 = 1 << 8	# unknown
    DebugCapable = 1 << 9	# Whether you can use debugging tools on the VI. For example, you can set breakpoints, create probes, enable execution highlighting, and single-step through execution.
    Bit10 = 1 << 10	# unknown
    Bit11 = 1 << 11	# unknown
    Bit12 = 1 << 12	# unknown
    Bit13 = 1 << 13	# unknown
    Bit14 = 1 << 14	# unknown
    Bit15 = 1 << 15	# unknown


class VI_EXEC_FLAGS(enum.Enum):
    """ VI Execution flags
    """
    Bit0 = 1 << 0	# Indicates whether to display the Run button on the toolbar while the VI runs.
    Bit1 = 1 << 1	# unknown
    Bit2 = 1 << 2	# unknown
    Bit3 = 1 << 3	# unknown
    Bit4 = 1 << 4	# unknown
    Bit5 = 1 << 5	# unknown
    Bit6 = 1 << 6	# unknown
    Bit7 = 1 << 7	# unknown
    Bit8 = 1 << 8	# unknown
    Bit9 = 1 << 9	# unknown
    Bit10 = 1 << 10	# unknown
    Bit11 = 1 << 11	# unknown
    Bit12 = 1 << 12	# unknown
    Bit13 = 1 << 13	# unknown
    Bit14 = 1 << 14	# unknown
    Bit15 = 1 << 15	# unknown


class LVSRData(RSRCStructure):
    # sizes mostly confirmed in lvrt
    _fields_ = [('version', c_uint32),	#0
                ('flags04', c_uint32),	#4 see VI_EXEC_FLAGS
                ('field08', c_uint32),	#8 flag 0x0001 = viSuppressBackup, 0x0020 = viIsTemplate, 0x40000000 = viRemoteClientPanel
                ('field0C', c_uint32),	#12
                ('flags10', c_uint16),	#16
                ('field12', c_uint16),	#18
                ('buttonsHidden', c_uint16),	#20 set based on value of viType,  see VI_BTN_HIDE_FLAGS
                ('field16', c_uint16),	#18 see VI_FP_FLAGS
                ('instrState', c_uint32),	#24 see VI_IN_ST_FLAGS
                ('execState', c_uint32),	#28 valid values under mask 0xF
                ('field20', c_uint16),	#32
                ('viType', c_uint16),	#34 Type of VI
                ('field24', c_uint32),	#36
                ('field28', c_uint32),	#40 linked value 1/3
                ('field2C', c_uint32),	#44 linked value 2/3
                ('field30', c_uint32),	#48 linked value 3/3
                ('viSignature', c_ubyte * 16),	#52 A hash identifying the VI file; used by LV while registering for events
                ('field44', c_uint32),	#68
                ('field48', c_uint32),	#72
                ('field4C', c_uint16),	#76
                ('field4E', c_uint16),	#78
                ('field50_md5', c_ubyte * 16),	#80
                ('libpass_md5', c_ubyte * 16),	#96
                ('field70', c_uint32),	#112
                ('field74', c_uint32),	#116
                ('field78_md5', c_ubyte * 16),	#120
                ('inlineStg', c_ubyte),	#136 inline setting, valid value 0..2
                ('inline_padding', c_ubyte * 3),	#137 
                ('field8C', c_uint32),	#140 
    ]

    def __init__(self, po):
        self.po = po
        pass


