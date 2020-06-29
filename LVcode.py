# -*- coding: utf-8 -*-

""" LabView RSRC file format compile code support.

    Allows analysis of the compiled code.
"""

# Copyright (C) 2019-2020 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.


import enum
from ctypes import *

import LVmisc

class VICodePtrs_LV5(enum.IntEnum):
    """ List of VI Code Pointers from LV5

    These callbacks can be set from InitCodePtrsProc within VI compiled code.
    """
    GoProc		= 0
    RetryProc	= 1
    ResumeProc	= 2
    ResetProc	= 3
    DisposeProc	= 4
    InitProc	= 5
    LoadProc	= 6
    SaveProc	= 7
    ErrorStopProc = 8
    ConstantProc = 9
    RngChkProc	= 10
    DCODfltProc	= 11
    SetAllDfltsProc	= 12
    DCOCopyProc	= 13
    DCOCopyToOpProc	= 14
    DCOCopyFrOpProc	= 15
    RunCode		= 16
    InitCodePtrsProc = 17
    PrxyCallerInitCPProc = 18
    ReInitProc	= 19
    CRoutine	= 20


class VICodePtrs_LV6(enum.IntEnum):
    """ List of VI Code Pointers from LV6 before LV6.1

    These callbacks can be set from InitCodePtrsProc within VI compiled code.
    Since LV6.1 this no longer applies as one of the callbacks was renamed.
    """
    CRoutine		= 0
    RetryProc		= 1
    ResumeProc		= 2
    ResetProc		= 3
    DisposeProc		= 4
    InitProc		= 5
    LoadProc		= 6
    SaveProc		= 7
    ErrorStopProc	= 8
    ConstantProc	= 9
    RngChkProc		= 10
    DCODefaultProc	= 11
    SetAllDefaultProc = 12
    DCOCopyProc		= 13
    DCOCopyToOpProc = 14
    DCOCopyFrOpProc = 15
    RunProc			= 16
    InitCodePtrsProc = 17
    ReInitProc		= 18
    GoProc			= 19


class VICodePtrs_LV7(enum.IntEnum):
    """ List of VI Code Pointers from LV6.1-LV7

    These callbacks can be set from InitCodePtrsProc within VI compiled code.
    """
    CRoutine		= 0
    RetryProc		= 1
    ResumeProc		= 2
    ResetProc		= 3
    DisposeProc		= 4
    InitProc		= 5
    LoadProc		= 6
    SaveProc		= 7
    ErrorStopProc	= 8
    ConstantProc	= 9
    RngChkProc		= 10
    DCODefaultProc	= 11
    SetAllDefaultProc = 12
    DCOCopyProc		= 13
    DCOCopyToOpProc = 14
    DCOCopyFrOpProc = 15
    RunProc			= 16
    InitCodePtrsProc = 17
    ReserveUnReserveProc = 18
    GoProc			= 19


class VICodePtrs_LV8(enum.IntEnum):
    """ List of VI Code Pointers from LV8-LV11

    These callbacks can be set from InitCodePtrsProc within VI compiled code.
    """
    CRoutine		= 0
    RetryProc		= 1
    ResumeProc		= 2
    ResetProc		= 3
    DisposeProc		= 4
    InitProc		= 5
    LoadProc		= 6
    SaveProc		= 7
    ErrorStopProc	= 8
    ConstantProc	= 9
    CompareProc		= 10
    DCODefaultProc	= 11
    SetAllDefaultProc = 12
    DCOCopyProc		= 13
    DCOCopyToOpProc = 14
    DCOCopyFrOpProc = 15
    RunProc			= 16 # Calls the method received in parameter
    InitCodePtrsProc = 17
    ReserveUnReserveProc = 18
    GoProc			= 19
    AcquireDSProc	= 20 # The 4 entries added in LV10
    ReleaseDSProc	= 21
    AcquireDSStaticProc	= 22
    ReleaseDSStaticProc	= 23


class VICodePtrs_LV12(enum.IntEnum):
    """ List of VI Code Pointers from LV12

    These callbacks can be set from InitCodePtrsProc within VI compiled code.
    Pointers are either 32-bit or 64-bit, depending on architecture.
    """
    CRoutine		= 0
    RetryProc		= 1
    ResumeProc		= 2
    ResetProc		= 3
    DisposeProc		= 4
    InitProc		= 5
    LoadProc		= 6
    SaveProc		= 7
    ErrorStopProc	= 8
    ConstantProc	= 9
    CompareProc		= 10
    DCODefaultProc	= 11
    SetAllDefaultProc = 12
    DCOCopyProc		= 13
    DCOCopyToOpProc = 14
    DCOCopyFrOpProc = 15
    RunCodeProc		= 16 # Calls the method received in parameter
    InitCodePtrsProc = 17
    ReserveUnReserveProc = 18
    GoProc			= 19
    DSTMNeededProc	= 20
    GetDataSpaceSizeProc = 21
    InflateDataSpaceProc = 22
    DeflateDataSpaceProc = 23
    ShrinkDataSpaceProc = 24
    UnflattenDefaultsProc = 25
    CopyDefaultsProc = 26
    CodeDebugProc	= 27
    CodeErrHandlingProc = 28


class VICodePtrs_LV13(enum.IntEnum):
    """ List of VI Code Pointers from LV13-LV20

    These callbacks can be set from InitCodePtrsProc within VI compiled code.
    Pointers are either 32-bit or 64-bit, depending on architecture.
    """
    CRoutine		= 0
    RetryProc		= 1
    ResumeProc		= 2
    ResetProc		= 3
    DisposeProc		= 4
    InitProc		= 5
    LoadProc		= 6
    SaveProc		= 7
    ErrorStopProc	= 8
    ConstantProc	= 9
    CompareProc		= 10
    DCODefaultProc	= 11
    SetAllDefaultProc = 12
    DCOCopyProc		= 13
    DCOCopyToOpProc = 14
    DCOCopyFrOpProc = 15
    ReserveUnReserveProc = 16
    GoProc			= 17
    DSTMNeeded		= 18
    GetDataSpaceSizeProc = 19
    InflateDataSpaceProc = 20
    DeflateDataSpaceProc = 21
    ShrinkDataSpaceProc = 22
    UnflattenDefaultsProc= 23
    CopyDefaultsProc	= 24
    CodeDebugProc	= 25
    CodeErrHandlingProc = 26
    CopyConvertProcs = 27
    InitCodePtrsProc = 28
    nRunProcs		= 29
    RunPtrs			= 30

