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
    ShowScrollBar = ((1 << 0) | (1 << 1))	 # Indicates whether to display the scroll bars on the front panel. in LV14: Customize Window Apearence -> Show vertical/horizonal scroll bar
    ShowTitleBar = 1 << 2	# Indicates whether to display title bar in the VI FP window. in LV14: Customize Window Apearence -> Windows has title bar
    ToolBarVisible = 1 << 3	# Indicates whether to display the toolbar while the VI runs. in LV14: Customize Window Apearence -> Show toolbar when running
    ShowMenuBar = 1 << 4	# Indicates whether to display the menu bar on the front panel while the VI runs. in LV14: Customize Window Apearence -> Show menu bar
    AutoCenter = 1 << 5	# Sets initial position of the FP window on screen to be centered. in LV14: Window Run-Time Positiion -> Positiion; in LV19: marked as deprecated
    SizeToScreen = 1 << 6	# Sets initial position of the FP window on screen to be maximized. in LV14: Window Run-Time Positiion -> Positiion; in LV19: marked as deprecated
    NoRuntimePopUp = 1 << 7	# Indicates whether to display shortcut menus for front panel objects while the VI runs. in LV14: Customize Window Apearence -> Allow default run-time shortcut menus
    MarkReturnBtn = 1 << 8	# Indicates whether to highlight Boolean controls that have a shortcut key of <Enter>. in LV14: Customize Window Apearence -> Highlight Enter boolean
    ViFpBit9 = 1 << 9	# unknown
    ScaleProportn = 1 << 10	# Maintain proportions of window for different monitor resolutions.
    ViFpBit11 = 1 << 11	# unknown
    ViFpBit12 = 1 << 12	# unknown
    ViFpBit13 = 1 << 13	# unknown
    ViFpBit14 = 1 << 14	# unknown
    ViFpBit15 = 1 << 15	# unknown


class VI_BTN_HIDE_FLAGS(enum.Enum):
    """ VI Tool Bar Buttons Hidding flags
    """
    RunButton = 1 << 0	# Indicates whether to display the Run button on the toolbar while the VI runs.
    ViBhBit1 = 1 << 1	# unknown
    ViBhBit2 = 1 << 2	# unknown
    ViBhBit3 = 1 << 3	# unknown
    ViBhBit4 = 1 << 4	# unknown
    FreeRunButton = 1 << 5	# Indicates whether to display the Run Continuously button on the toolbar while the VI runs. in LV14: Customize Window Apearence -> Show Run Continuously button
    ViBhBit6 = 1 << 6	# unknown
    AbortButton = 1 << 7	# Indicates whether to display the Abort Execution button on the toolbar while the VI runs. in LV14: Customize Window Apearence -> Show Abort button
    ViBhBit8 = 1 << 8	# unknown
    ViBhBit9 = 1 << 9	# unknown
    ViBhBit10 = 1 << 10	# unknown
    ViBhBit11 = 1 << 11	# unknown
    ViBhBit12 = 1 << 12	# unknown
    ViBhBit13 = 1 << 13	# unknown
    ViBhBit14 = 1 << 14	# unknown
    ViBhBit15 = 1 << 15	# unknown


class VI_IN_ST_FLAGS(enum.Enum):
    """ VI Insrument State flags
    """
    InStBit0 = 1 << 0	# unknown
    InStBit1 = 1 << 1	# unknown
    InStBit2 = 1 << 2	# unknown
    InStBit3 = 1 << 3	# unknown
    InStBit4 = 1 << 4	# unknown
    InStBit5 = 1 << 5	# unknown
    InStBit6 = 1 << 6	# unknown
    InStBit7 = 1 << 7	# unknown
    InStBit8 = 1 << 8	# unknown
    DebugCapable = 1 << 9	# Whether you can use debugging tools on the VI. For example, you can set breakpoints, create probes, enable execution highlighting, and single-step through execution.
    InStBit10 = 1 << 10	# unknown
    InStBit11 = 1 << 11	# unknown
    InStBit12 = 1 << 12	# unknown
    InStBit13 = 1 << 13	# unknown
    InStBit14 = 1 << 14	# unknown
    PrintAfterExec = 1 << 15	# Print FP on Execution Complete. in LV14: Print Options -> Automatically print front panel every time VI completes execution
    InStBit16 = 1 << 16	# unknown
    InStBit17 = 1 << 17	# unknown
    InStBit18 = 1 << 18	# unknown
    InStBit19 = 1 << 19	# unknown
    InStBit20 = 1 << 20	# unknown
    InStBit21 = 1 << 21	# unknown
    InStBit22 = 1 << 22	# unknown
    InStBit23 = 1 << 23	# unknown
    InStBit24 = 1 << 24	# unknown
    InStBit25 = 1 << 25	# unknown
    InStBit26 = 1 << 26	# unknown
    InStBit27 = 1 << 27	# unknown
    InStBit28 = 1 << 28	# unknown
    InStBit29 = 1 << 29	# unknown
    InStBit30 = 1 << 30	# unknown
    InStBit31 = 1 << 31	# unknown


class VI_EXEC_FLAGS(enum.Enum):
    """ VI Execution flags
    """
    BadSignal =		1 << 0	# bad signal
    BadNode =		1 << 1	# bad node
    BadSubVILink =	1 << 2	# bad SubVI link
    BadSubVI =		1 << 3	# bad SubVI
    NotReservable =	1 << 4	# not reservable
    IsReentrant =	1 << 5	# Indicates whether a VI can be reentrant (multiple instances of it can execute in parallel).
    CloseAfterCall = 1 << 6	# Indicates whether to close the front panel after the VI runs (auto reclose). in LV14: Customize Window Apearence -> Close afterwards if originally closed
    PooledReentrancy = 1 << 7	# pooled Reentrancy
    LoadFP =		1 << 8	# load FP
    HasNoBD =		1 << 9	# BD not available
    ShowFPOnLoad =	1 << 10	# Indicates whether to show the front panel when the VI is loaded. in LV14: Customize Window Apearence -> Show front panel when loaded
    DynamicDispatch = 1 << 11	# fails to always call Parent VI (dynamic dispatching)
    HasSetBP =		1 << 12	# BreakPoint Set on the VI. in LV14: Execution -> Suspend when called
    LibProtected =	1 << 13	# The library which this VI is part of is protected(locked) from changes.
    RunOnOpen =		1 << 14	# Indicates whether to run the VI when it opens (load and go). in LV14: Execution -> Run when opened
    ShowFPOnCall =	1 << 15	# Indicates whether to show the front panel when the VI is called (Auto window). in LV14: Customize Window Apearence -> Show front panel when called
    BadCompile =	1 << 16	# Compile bad
    IsSubroutine =	1 << 17	# VI is Subroutine; this sets high priority.
    DSRecord =		1 << 18	# Record DS
    CompilerBug =	1 << 19	# Compiler Bug
    TypeDefVI =		1 << 20	# VI is typedef
    StrictTypeDefVI = 1 << 21	# VI is strict typedef
    BadDDO =		1 << 22	# Bad Data Display Object (control or indicator)
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
    ClearIndMask =		1 << 24	# Clear charts etc on call. in LV14: Execution -> Clear indicators when called
    DefaultGrownView =	1 << 25	# VI should be grown by default when dropped
    DoNotClone =		1 << 26	# do not clone this instance VI
    IsPrivateDataForUDClass = 1 << 27	# this ctl is private data for a LV class
    InstanceVI =		1 << 28	# instance VI (wizard-locked 'LabVIEW Blocks')
    DefaultErrorHandling = 1 << 29	# Integrates default error handling. in LV14: Execution -> Enable automatic error handling
    RemotePanel =		1 << 30	# VI is a remote panel VI
    SuppressInstanceHalo = 1 << 31	# do not draw blue halo around non-grown instance VIs


class VI_FLAGS0C(enum.Enum):
    """ VI Flags dword at 0x0C
    """
    ViCBit0 = 1 << 0	# unknown
    ViCBit1 = 1 << 1	# unknown
    AutoHndlMenus = 1 << 2	# Automatically handle menu selections when you open and run the VI. in LV14: Execution -> Auto handle menus at launch
    ViCBit3 = 1 << 3	# unknown
    ViCBit4 = 1 << 4	# unknown
    ViCBit5 = 1 << 5	# unknown
    ViCBit6 = 1 << 6	# unknown
    ViCBit7 = 1 << 7	# unknown
    ViCBit8 = 1 << 8	# unknown
    ViCBit9 = 1 << 9	# unknown
    ViCBit10 = 1 << 10	# unknown
    ViCBit11 = 1 << 11	# unknown
    ViCBit12 = 1 << 12	# unknown
    ViCBit13 = 1 << 13	# unknown
    ViCBit14 = 1 << 14	# unknown
    ViCBit15 = 1 << 15	# unknown
    ViCBit16 = 1 << 16	# unknown
    ViCBit17 = 1 << 17	# unknown
    ViCBit18 = 1 << 18	# unknown
    ViCBit19 = 1 << 19	# unknown
    ViCBit20 = 1 << 20	# unknown
    ViCBit21 = 1 << 21	# unknown
    ViCBit22 = 1 << 22	# unknown
    ViCBit23 = 1 << 23	# unknown
    ViCBit24 = 1 << 24	# unknown
    ViCBit25 = 1 << 25	# unknown
    ViCBit26 = 1 << 26	# unknown
    ViCBit27 = 1 << 27	# unknown
    ViCBit28 = 1 << 28	# unknown
    ViCBit29 = 1 << 29	# unknown
    ViCBit30 = 1 << 30	# unknown
    ViCBit31 = 1 << 31	# unknown


class VI_FLAGS12(enum.Enum):
    """ VI Flags dword at 0x12
    """
    WndBit0 = 1 << 0	# unknown
    WndFloatUnk1 = 1 << 1	# Window is Floating or Hide window when LV not active
    WndBit2 = 1 << 2	# unknown
    WndCanClose = 1 << 3	# Indicates whether the VI FP window can be closed. in LV14: Customize Window Apearence -> Allow user to close window
    WndCanResize = 1 << 4	# Indicates whether the VI FP window can be resized. in LV14: Customize Window Apearence -> Allow user to resize window
    WndCanMinimize = 1 << 5	# Indicates whether the VI FP window can be minimized. in LV14: Customize Window Apearence -> Allow user to minimize window
    WndTransparent = 1 << 6	# Indicates whether the VI FP window has transparency. 'pctTransparent' should be defined in FP. in LV14: Customize Window Apearence -> Window runs transparently
    WndBit7 = 1 << 7	# unknown
    WndBit8 = 1 << 8	# unknown
    WndFloatUnk9 = 1 << 9	# Window is Floating or Hide window when LV not active
    WndBit10 = 1 << 10	# unknown
    WndBit11 = 1 << 11	# unknown
    WndBit12 = 1 << 12	# unknown
    WndBit13 = 1 << 13	# unknown
    WndBit14 = 1 << 14	# unknown
    WndBit15 = 1 << 15	# unknown


class LVSRData(RSRCStructure):
    # sizes mostly confirmed in lvrt
    _fields_ = [('version', c_uint32),	#0
                ('execFlags', c_uint32),	#4 see VI_EXEC_FLAGS
                ('viFlags2', c_uint32),	#8 see VI_FLAGS2
                ('field0C', c_uint32),	#12 see VI_FLAGS0C
                ('flags10', c_uint16),	#16
                ('field12', c_uint16),	#18 see VI_FLAGS12
                ('buttonsHidden', c_uint16),	#20 set based on value of viType, see VI_BTN_HIDE_FLAGS
                ('frontpFlags', c_uint16),	#18 see VI_FP_FLAGS
                ('instrState', c_uint32),	#24 see VI_IN_ST_FLAGS
                ('execState', c_uint32),	#28 valid values under mask 0xF
                ('execPrio', c_uint16),	#32 priority of the VI when it runs in parallel with other tasks; expected values 0..4
                ('viType', c_uint16),	#34 type of VI
                ('prefExecSyst', c_int32),	#36 signed; Preferred execution system: -1=same as caller, 3=data acquisition
                ('field28', c_uint32),	#40 linked value 1/3
                ('field2C', c_uint32),	#44 linked value 2/3
                ('field30', c_uint32),	#48 linked value 3/3
                ('viSignature', c_ubyte * 16),	#52 A hash identifying the VI file; used by LV while registering for events
                ('alignGridFP', c_uint32),	#68 Alignment Grid Size for Front Panel
                ('alignGridBD', c_uint32),	#72 Alignment Grid Size for Block Diagram
                ('field4C', c_uint16),	#76
                ('ctrlIndStyle', c_uint16),	#78 Visual style of FP controls and indicators: 0=modern, 1=classic, 2=system, 3=silver. in LV14: Editor Options -> Control Style for Create Control/Indicator
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


