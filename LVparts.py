# -*- coding: utf-8 -*-

""" LabView RSRC file format part definitions.

    Parts are placed on Front Panel and Block Diagram.
"""

# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.


import enum
from ctypes import *

import LVmisc

class PARTID(enum.IntEnum):
    """ Part identifiers
    """
    NO_PARTID	= 0
    COSMETIC	= 1
    INCREMENT	= 2
    DECREMENT	= 3
    LARGE_INCREMENT	= 4
    LARGE_DECREMENT	= 5
    PIXEL_INCREMENT	= 6
    PIXEL_DECREMENT	= 7
    HOUSING	= 8
    FRAME	= 9
    NUMERIC_TEXT	= 10
    TEXT	= 11
    RING_TEXT	= 12
    SCROLLBAR	= 13
    RING_PICTURE	= 14
    RADIX	= 15
    NAME_LABEL	= 16
    SCALE	= 17
    X_SCALE	= 18
    Y_SCALE	= 19
    OUT_OF_RANGE_BOX	= 20
    BOOLEAN_BUTTON	= 21
    BOOLEAN_TEXT	= 22
    SLIDER_NEEDL_THUMB	= 23
    SET_TO_DEFAULT	= 24
    DECORATION	= 25
    LIST_AREA	= 26
    SCALE_MARKER	= 27
    CONTENT_AREA	= 28
    DDO_FRAME	= 29
    INDEX_FRAME	= 30
    FILL	= 31
    GRAPH_LEGEND	= 32
    GRAPH_PALETTE	= 33
    X_FIT_BUTTON	= 34
    Y_FIT_BUTTON	= 35
    X_FIT_LOCK_BUTTON	= 36
    Y_FIT_LOCK_BUTTON	= 37
    X_SCROLLBAR	= 38
    Y_SCROLLBAR	= 39
    SCALE_TICK	= 40
    COLOR_AREA	= 41
    PALETTE_BACKGROUND	= 42
    CONTRL_INDCTR_SYM	= 43
    EXTRA_FRAME_PART	= 44
    SCALE_MIN_TICK	= 45
    PIX_MAP_PALETTE	= 46
    SELECT_BUTTON	= 47
    TEXT_BUTTON	= 48
    ERASE_BUTTON	= 49
    PEN_BUTTON	= 50
    SUCKER_BUTTON	= 51
    BUCKET_BUTTON	= 52
    LINE_BUTTON	= 53
    RECTANGLE_BUTTON	= 54
    FILLED_RECT_BUTTON	= 55
    OVAL_BUTTON	= 56
    FILLED_OVAL_BUTTON	= 57
    PATTERN	= 58
    FOREGROUND_COLOR	= 59
    BACKGROUND_COLOR	= 60
    PIX_MAP_PAL_EXTRA	= 61
    ZOOM_BAR	= 62
    BOOLEAN_TRUE_LABEL	= 63
    BOOLEAN_FALSE_LABEL	= 64
    UNIT_LABEL	= 65
    ANNEX	= 66
    OLD_GRAPH_CURSOR	= 67
    Z_SCALE	= 68
    COLOR_RAMP	= 69
    OUTPUT_INDICATOR	= 70
    X_SCALE_UNIT_LABEL	= 71
    Y_SCALE_UNIT_LABEL	= 72
    Z_SCALE_UNIT_LABEL	= 73
    GRAPH_MOVE_TOOL	= 74
    GRAPH_ZOOM_TOOL	= 75
    GRAPH_CURSOR_TOOL	= 76
    GRAPH_X_FORMAT	= 77
    GRAPH_Y_FORMAT	= 78
    COMBO_BOX_BUTTON	= 79
    DIAGRAM_IDENTIFIER	= 80
    MENU_TITLE_LABEL	= 81
    CAPTION	= 82
    REFNUM_SYMBOL	= 83
    KUNNAMED84	= 84
    FORMERLY_ANNEX2	= 85
    BOOLEAN_LIGHT	= 86
    BOOLEAN_GLYPH	= 87
    BOOLEAN_DIVOT	= 88
    BOOLEAN_SHADOW	= 89
    TAB	= 90
    PAGE_LIST_BUTTON	= 91
    TAB_CAPTION	= 92
    TAB__BACKGROUND	= 93
    SCALE_NAME	= 94
    SLIDE_CAP	= 95
    KUNNAMED96	= 96
    CONTAINED_DATA_TYPE	= 97
    POSITION_DATA_TYPE	= 98
    TAB_GLYPH	= 99
    GRID	= 100
    NUM_LABEL	= 101
    SPLIT_BAR	= 102
    MUTLI_Y_SCROLLBAR	= 103
    GRAPH_VIEWPORT	= 104
    GRAB_HANDLE	= 105
    GRAPH_SPLITTER_BAR	= 106
    GRAPH_LEGEND_AREA	= 107
    GRAPH_LEGEND_SCRLBAR = 108
    DATA_BINDING_STATUS	= 109
    TERNARY_TEXT	= 110
    TERNARY_BUTTON	= 111
    MULTISEG_PIPE_FLANGE = 112
    MULTISEG_PIPE_ELBOW	= 113
    MULTISEG_PIPE_PIPE	= 114
    GRAPH_LEGEND_FRAME	= 115
    SCENE_GRAPH_DISPLAY	= 116
    OVERFLOW_STATUS	= 117
    RADIX_SHADOW	= 118
    CUSTOM_COSMETIC	= 119
    TYPEDEF_CORNER	= 120
    NON_COLORABLE_DECAL	= 8000 # 121 ?
    DIGITAL_DISPLAY	= 8001
    ARRAY_INDEX	= 8002
    VARIANT_INDEX	= 8003
    LISTBOX_DISPLAY	= 8004
    DATA_DISPLAY	= 8005
    MEASURE_DATA	= 8006
    KNOTUSED4	= 8007
    TREE_LEGEND	= 8008
    COLOR_RAMP_ARRAY	= 8009
    TYPE_DEFS_CONTROL	= 8010
    CURSOR_BUTTONS	= 8011
    HIGH_COLOR	= 8012
    LOW_COLOR	= 8013
    GRAPH_CURSOR	= 8014
    GRAPH_SCALE_LEGEND	= 8015
    TABLE	= 8015
    IO_NAME_DISPLAY	= 8016
    TAB_CTRL_PAGE_SEL	= 8017
    BROWSE_BUTTON	= 8018
    GRAPH_PLOT_LEGEND	= 8019

def partIdToEnum(partId):
    if partId not in set(item.value for item in PARTID):
        return partId
    return PARTID(partId)

class OBJ_FLAGS(enum.IntEnum):
    """ Part ObjFlags bits
    """
    OFFBit0 = 1 << 0	# isIndicator - indicator, input is disabled
    OFFBit1 = 1 << 1	# unknown
    OFFBit2 = 1 << 2	# unknown
    OFFBit3 = 1 << 3	# isHidden - part is not visible on screen
    OFFBit4 = 1 << 4	# unknown
    OFFBit5 = 1 << 5	# unknown
    OFFBit6 = 1 << 6	# unknown
    OFFBit7 = 1 << 7	# unknown
    OFFBit8 = 1 << 8	# unknown
    OFFBit9 = 1 << 9	# unknown
    OFFBit10 = 1 << 10	# unknown
    OFFBit11 = 1 << 11	# unknown
    OFFBit12 = 1 << 12	# unknown
    OFFBit13 = 1 << 13	# unknown
    OFFBit14 = 1 << 14	# unknown
    OFFBit15 = 1 << 15	# unknown
    OFFBit16 = 1 << 16	# unknown
    OFFBit17 = 1 << 17	# unknown
    OFFBit18 = 1 << 18	# unknown
    OFFBit19 = 1 << 19	# unknown
    OFFBit20 = 1 << 20	# unknown
    OFFBit21 = 1 << 21	# unknown
    OFFBit22 = 1 << 22	# unknown
    OFFBit23 = 1 << 23	# unknown
    OFFBit24 = 1 << 24	# unknown
    OFFBit25 = 1 << 25	# unknown
    OFFBit26 = 1 << 26	# unknown
    OFFBit27 = 1 << 27	# unknown
    OFFBit28 = 1 << 28	# unknown
    OFFBit29 = 1 << 29	# unknown
    OFFBit30 = 1 << 30	# unknown
    OFFBit31 = 1 << 31	# unknown

class DSINIT(enum.IntEnum):
    """ Dats Space Initialization metadata

    Stores values used for Data Space initialization, including references
    to TypeDesc used and location of instantiated data within the data space.

    The table contains few offsets to Invariant Data Space. This space
    is created by instantiating data for types in Type Map (DSTM/TM80 block).
    Part of the space is also covered by Default Fill (DFDS), though the data
    from DFDS are unflattened in Invariant Data Space, so sizes do not always
    match. Any varaible size items with size not defined in TypeDesc are
    represented within the Invariant Data Space as pointers, so that their
    size stays constant.

    The table also contains TMI index values. These contain some flag bits
    at top, and below there is an index on Type Map table of a related
    Type Descriptor.
    """
    # Amount of entries in the Hilite Table pointed by two values below
    # Hilite Table stores something related to highliting items on a FP?
    nHiliteTableEntries	= 0
    # Offset of the Hilite Table within Invariant Data Space
    hiliteTableOffset	= 1
    # Type Map Index which points to TypeDesc for Hilite Table
    hiliteTableTMI		= 2
    # Amount of entries in the Probe Table pointed by two values below
    # Probe Table is a Cluster which consists of another Cluster and then
    # connector types representing the Probe Points.
    nProbeTableEntries	= 3
    # Offset of the Probe Table within Invariant Data Space
    # Probe Table stores Probe Points in form of RepeatedBlock with two I32
    # values per entry.
    probeTableOffset	= 4
    # Type Map Index which points to TypeDesc for Probe Table
    probeTableTMI	= 5
    # Amount of Data Controller Object structures in the DCO Table pointed by two values below
    # DCO Table is a RepeatedBlock with Clusters inside, each represening a DCO.
    nDCOs			= 6
    # Offset of the DCO Table within Invariant Data Space
    fpdcoTableOfst	= 7
    # Type Map Index which points to TypeDesc for DCO Table
    fpdcoTableTMI	= 8
    # Amount of Clump QElement Allocations pointed by two values below
    nClumpQEs		= 9
    # Offset of the Clump QElement Alloc within Invariant Data Space
    clumpQEAllocOffset	= 10
    # Type Map Index which points to TypeDesc for Clump QElement Alloc
    clumpQEAllocTMI		= 11
    # Amount of Connection Port Connections
    # Probably used as size to some tables here, bit not for the ones just below.
    nConnections		= 12
    # Offset of the VI Param Table within Invariant Data Space
    viParamTableOffset	= 13
    # Type Map Index which points to TypeDesc for VI Param Table
    viParamTableTMI		= 14
    # Amount of entries in the Extra DCO Info pointed by two values below
    nExtraDCOInfoEntries = 15
    # Offset of the Extra DCO Info within Invariant Data Space
    extraDCOInfoOffset	= 16
    # Type Map Index which points to TypeDesc for Extra DCO Info
    extraDCOInfoTMI		= 17
    # Amount of index values within Local Input Connections List
    nLocalInputConnections	= 18
    # Offset of the Local Input Connections List within Invariant Data Space
    localInputConnIdxOffset	= 19
    # Type Map Index which points to TypeDesc for several Connections Lists
    # The TypeDesc stores Lists: Non-Local/Local Input Connections, Conditional
    # Indicators, Output Connections, Input Connections.
    localInputConnIdxTMI	= 20
    # Amount of index values within Non-Local Input Connections List
    nNonLocalInputConnections = 21
    # Offset of the Non-Local Input Connections List within Invariant Data Space
    nonLocalInputConnIdxOffset = 22
    # Amount of index values within Conditional Indicators List
    nCondIndicators		= 23
    # Offset of the Conditional Indicators List within Invariant Data Space
    condIndIdxOffset	= 24
    # Amount of index values within Output Connections List
    nOutputConnections	= 25
    nOutPutLocalGlobals	= 26
    # Offset of the Output Connections List within Invariant Data Space
    outputConnIdxOffset	= 27
    # Amount of index values within Input Connections List
    nInputConnections	= 28
    # Offset of the Input Connections List within Invariant Data Space
    inputConnIdxOffset	= 29
    # Amount of entries within Internal Hilite Table
    numInternalHiliteTableEntries = 30
    # Type Map Index which points to TypeDesc for Internal Hilite Table Handle and Pointers
    internalHiliteTableHandleAndPtrTMI = 31
    # Amount of index values in the Sync Displays List pointed by the value below
    nSyncDisplays		= 32
    # Offset of the Sync Displays Index List within Invariant Data Space
    syncDisplayIdxOffset = 33
    # Amount of entries in the subVI Patches Lists pointed by two values below
    nSubVIPatches		= 34
    # Type Map Index which points to TypeDesc for subVI Patch Tags
    subVIPatchTagsTMI	= 35
    # Type Map Index which points to TypeDesc for subVI Patch
    subVIPatchTMI		= 36
    enpdTdOffsetsDso	= 37
    # Type Map Index which points to TypeDesc for Enpd TD Offsets
    enpdTdOffsetsTMI	= 38
    # Amount of Data Display Object structures in the DDO Table pointed by two values below
    nDDOs				= 39
    # Offset of the DDO Table within Invariant Data Space
    spDDOTableOffset	= 40
    # Type Map Index which points to TypeDesc for DDO Table
    spDDOTableTMI		= 41
    # Amount of index values in the Step-Into Nodes List pointed by two values below
    nStepIntoNodes		= 42
    # Offset of the Step-Into Nodes List within Invariant Data Space
    stepIntoNodeIdxTableOffset = 43
    # Type Map Index which points to TypeDesc for Step-Into Nodes List
    stepIntoNodeIdxTableTMI = 44
    # Type Map Index which points to TypeDesc for Hilite Index Table
    hiliteIdxTableTMI	= 45
    # Amount of entries in the Generated Code Profile Result Table pointed by the value below
    numGeneratedCodeProfileResultTableEntries = 46
    # Type Map Index which points to TypeDesc for Generated Code Profile Result Table
    generatedCodeProfileResultTableTMI = 47
    lReRunPCOffset	= 48
    lResumePCOffset	= 49
    lRetryPCOffset	= 50

def dsInitIdToEnum(dsInitId):
    if dsInitId not in set(item.value for item in DSINIT):
        return dsInitId
    return DSINIT(dsInitId)


class DCO(LVmisc.RSRCStructure):
    """ Data Controller Object type as stored within DFDS block.

    The definition of this struct is used to have
    names of elements, and to compare the types
    with TypeDesc stored within RSRC and so find this
    specific structure.
    It is not used for loading data.
    """
    _fields_ = [
      ('dcoIndex', c_int16),
      ('ipCon', c_uint16),
      ('syncDisplay', c_uint8),
      ('extraUsed', c_uint8),
      ('flat', c_uint8),
      ('conNum', c_int8),
      ('flagDSO', c_int32),
      ('flagTMI', c_int32),
      ('defaultDataTMI', c_int32),
      ('extraDataTMI', c_int32),
      ('dsSz', c_int32),
      ('ddoWriteCode', c_uint8),
      ('ddoNeedsSubVIStartup', c_uint8),
      ('isIndicator', c_uint8),
      ('isScalar', c_uint8),
      ('defaultDataOffset', c_int32),
      ('transferDataOffset', c_int32),
      ('extraDataOffset', c_int32),
      ('execDataPtrOffset', c_int32),
      ('eltDsSz', c_int32),
      ('copyReq', c_uint8),
      ('local', c_uint8),
      ('feo', c_uint8),
      ('nDims', c_uint8),
      ('copyProcIdx', c_uint8),
      ('copyFromRtnIdx', c_uint8),
      ('misclFlags', c_uint8),
      ('unusedFillerByte', c_uint8),
      ('subTypeDSO', c_int32), # Sub-Type Data Space Offset
      ('customCopyFromOffset', c_uint8 * 4),
      ('customCopyToOffset', c_uint8 * 4),
      ('customCopyOffset', c_uint8 * 4),
    ]

    def __init__(self, po):
        self.po = po
        pass

    def checkSanity(self):
        ret = True
        return ret

