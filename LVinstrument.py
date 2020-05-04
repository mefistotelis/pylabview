# -*- coding: utf-8 -*-

""" LabView RSRC file format instrument info / save record.

    Various general properties of the RSRC file.
"""

# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.


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
    Bit0 = 1 << 0	# unknown
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
    Bit16 = 1 << 16	# unknown
    Bit17 = 1 << 17	# unknown
    Bit18 = 1 << 18	# unknown
    Bit19 = 1 << 19	# unknown
    Bit20 = 1 << 20	# unknown
    Bit21 = 1 << 21	# unknown
    Bit22 = 1 << 22	# unknown
    Bit23 = 1 << 23	# unknown
    Bit24 = 1 << 24	# unknown
    Bit25 = 1 << 25	# unknown
    Bit26 = 1 << 26	# unknown
    Bit27 = 1 << 27	# unknown
    Bit28 = 1 << 28	# unknown
    Bit29 = 1 << 29	# unknown
    Bit30 = 1 << 30	# unknown
    Bit31 = 1 << 31	# unknown


class VI_EXEC_FLAGS(enum.Enum):
    """ VI Execution flags
    """
    BadSignal =		1 << 0	# bad signal
    BadNode =		1 << 1	# bad node
    BadSubVILink =	1 << 2	# bad SubVI link
    BadSubVI =		1 << 3	# bad SubVI
    NotReservable =	1 << 4	# not reservable
    IsReentrant =	1 << 5	# Indicates whether a VI can be reentrant (multiple instances of it can execute in parallel).
    CloseAfterCall = 1 << 6	# Indicates whether to close the front panel after the VI runs (auto reclose).
    PooledReentrancy = 1 << 7	# pooled Reentrancy
    LoadFP =		1 << 8	# load FP
    HasNoBD =		1 << 9	# BD not available
    ShowFPOnLoad =	1 << 10	# Indicates whether to show the front panel when the VI is loaded.
    DynamicDispatch = 1 << 11	# fails to always call Parent VI (dynamic dispatching)
    HasSetBD =		1 << 12	# BP Set
    LibProtected =	1 << 13	# The library which this VI is part of is protected(locked) from changes.
    RunOnOpen =		1 << 14	# Indicates whether to run the VI when it opens (load and go).
    ShowFPOnCall =	1 << 15	# Indicates whether to show the front panel when the VI is called (Auto window).
    BadCompile =	1 << 16	# Compile bad
    IsSubroutine =	1 << 17	# VI is Subroutine; this sets high priority.
    DSRecord =		1 << 18	# Record DS
    CompilerBug =	1 << 19	# Compiler Bug
    TypeDefVI =		1 << 20	# VI is typedef
    StrictTypeDefVI = 1 << 21	# VI is strict typedef
    BadDDO =		1 << 22	# Bad DDO
    CtlChanged =	1 << 23	# Ctl-edit changed
    SaveParallel =	1 << 24	# Save parallel
    LibIssuesNoRun =	1 << 25	# library for this VI has some problem so VI is not runnable
    AllowAutoPrealloc =	1 << 26	# Autopreallocation allowed
    EvalWatermark =		1 << 27	# Evaluation version watermark
    StdntWatermark =	1 << 28	# Student version watermark
    HasInsaneItems =	1 << 29	# VI contains insanity
    PropTypesIssues =	1 << 30	# PropTypes warnings other than SE warnings
    BrokenPolyVI =		1 << 31	# PolyVI broken for polyVI-specific reason(s)


class VI_FLAGS2(enum.Enum):
    """ VI Flags dword 2
    """
    TaggedAndNotEdited =	1 << 0	# vi was tagged and has not entered edit mode, backup is suppressed
    HideInstanceVICaption =	1 << 1	# Hide instance caption in the VI panel
    SystemVI =			1 << 2	# VI and subVIs not shown in hierwin, unopened subVIs, etc.
    VisibleVI =			1 << 3	# The VI is visible in hierwin, unopened subVIs, etc.
    XDebugWindowVI =	1 << 4	# unknown
    TemplateMask =		1 << 5	# temporary flag used to rename template VIs
    SuppressXaction =	1 << 6	# transactions are disabled - VI is a template
    AlwaysCallsParent =	1 << 7	# DynDispatch VI includes an unconditional use of Call Parent Node
    UndoRedoChangedNoTypes = 1 << 8	# UndoRedo changed no types
    InlinableDiagram =	1 << 9	# Typeprop says this VI's diagram is safe to Inline (used to be ObjIDChgOK)
    SourceOnly =		1 << 10	# code saved in a seperate file (.viobj)
    InlineIfPossible =	1 << 11	# this VI should be inlined into static callers if it is inlineable (has InlinableDiagram, VISettingsAreInlineSafe and VISupportsInlineFlag)
    TransactionFailing = 1 << 12	# a transaction is currently being failed
    SSEOptiMask =		1 << 13	# this VI has SSE optimization disabled
    StudentOnlyMask =	1 << 14	# can be loaded in LV Student Ed., not full LV system
    EvalOnlyMask =		1 << 15	# can be loaded in LV Evaluation, not full LV system
    AllowPolyTypeAdapt = 1 << 16	# PolyVI shows automatic & allows VI to adapt to type
    ShouldInline =		1 << 17	# this VI is inlined into static callers
    RecalcFPDSOs =		1 << 18	# cross compiled from a different alignment
    MarkForPolyVI =		1 << 19	# VI is polymorphic
    VICanPassLVClassToDLL = 1 << 20	# VI is authorized to pass LVClasses to Call Library nodes (for known safe callbacks into LV)
    UndoRedoInProgress = 1 << 21	# VI is currently undergoing undo/redo
    DrawInstanceIcon =	1 << 22	# set: draw instance icon;  unset: draw PolyVI icon
    ShowPolySelector =	1 << 23	# show PolySelector when new PolyVI icon is put on BD
    ClearIndMask =		1 << 24	# clear charts etc. on call
    DefaultGrownView =	1 << 25	# VI should be grown by default when dropped
    DoNotClone =		1 << 26	# do not clone this instance VI
    IsPrivateDataForUDClass = 1 << 27	# this ctl is private data for a LV class
    InstanceVI =		1 << 28	# instance VI (wizard-locked 'LabVIEW Blocks')
    DefaultErrorHandling = 1 << 29	# default error handling
    RemotePanel =		1 << 30	# VI is a remote panel VI
    SuppressInstanceHalo = 1 << 31	# do not draw blue halo around non-grown instance VIs


class LVSRData(RSRCStructure):
    # sizes mostly confirmed in lvrt
    _fields_ = [('version', c_uint32),	#0
                ('execFlags', c_uint32),	#4 see VI_EXEC_FLAGS
                ('viFlags2', c_uint32),	#8 see VI_FLAGS2
                ('field0C', c_uint32),	#12
                ('flags10', c_uint16),	#16
                ('field12', c_uint16),	#18
                ('buttonsHidden', c_uint16),	#20 set based on value of viType, see VI_BTN_HIDE_FLAGS
                ('frontpFlags', c_uint16),	#18 see VI_FP_FLAGS
                ('instrState', c_uint32),	#24 see VI_IN_ST_FLAGS
                ('execState', c_uint32),	#28 valid values under mask 0xF
                ('execPrio', c_uint16),	#32 priority of the VI when it runs in parallel with other tasks; expected values 0..4
                ('viType', c_uint16),	#34 type of VI
                ('field24', c_int32),	#36 signed
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
                ('field74', c_int32),	#116 signed
                ('field78_md5', c_ubyte * 16),	#120
                ('inlineStg', c_ubyte),	#136 inline setting, valid value 0..2
                ('inline_padding', c_ubyte * 3),	#137 
                ('field8C', c_uint32),	#140 
    ]

    def __init__(self, po):
        self.po = po
        pass


