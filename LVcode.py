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
from LVheap import ENUM_TAGS

class VICodePtrs_LV5(ENUM_TAGS):
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


class VICodePtrs_LV6(ENUM_TAGS):
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


class VICodePtrs_LV7(ENUM_TAGS):
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


class VICodePtrs_LV8(ENUM_TAGS):
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


class VICodePtrs_LV12(ENUM_TAGS):
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


class VICodePtrs_LV13(ENUM_TAGS):
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
    RunProc			= 30
    RunProc2		= 31
    RunProc3		= 32
    RunProc4		= 33
    RunProc5		= 34
    RunProc6		= 35
    RunProc7		= 36
    RunProc8		= 37
    RunProc9		= 38
    RunProc10		= 39
    RunProc11		= 40
    RunProc12		= 41
    RunProc13		= 42
    RunProc14		= 43
    RunProc15		= 44


class CodeArch(ENUM_TAGS):
    i386_pc_win32		= 'i386' # Windows 32-bit; used for Windows 3.x with Watcom Win386 extender, then reused for later 32-bit Windowses
    x86_64_pc_win32		= 'wx64'
    i386_pc_unix		= 'ux86' # Linux, previously was also used for Solaris
    x86_64_pc_linux_gnu	= 'ux64'
    i386_apple_darwin	= 'm386'
    x86_64_apple_darwin	= 'mx64'
    motorola680xx_mac	= 'M86K'
    pa_risc_hpunix 		= 'PA  '
    powerpc_pc_eabi		= 'POWE'
    powerpc_linux		= 'PLIN'
    powerpc_win			= 'POWX'
    powerpc_winnt		= 'PWNT'
    sparc_solaris		= 'sprc'
    alphaaxp_winnt		= 'axwn'
    alphaaxp_linux		= 'axlx'
    alphaaxp_du			= 'axdu'
    arm_cortex_eabi		= 'ARM '


def mangleDataName(eName, eKind):
    """ Prepare symbol name for MAP file.

    Uses name mangling from MsVS. Not that I like it, it's just the most
    popular ATM - disassembler will read them.
    """
    eArr = "PA" if  eKind.endswith("[]") else ""
    if eKind.startswith("i8"):
        fullName = "?{}@@3{}CA".format(eName, eArr)
    elif eKind.startswith("i16"):
        fullName = "?{}@@3{}FA".format(eName, eArr)
    elif eKind.startswith("i32"):
        fullName = "?{}@@3{}HA".format(eName, eArr)
    elif eKind.startswith("i64"):
        fullName = "?{}@@3{}_JA".format(eName, eArr)
    elif eKind.startswith("u8"):
        fullName = "?{}@@3{}EA".format(eName, eArr)
    elif eKind.startswith("u16"):
        fullName = "?{}@@3{}GA".format(eName, eArr)
    elif eKind.startswith("u32"):
        fullName = "?{}@@3{}IA".format(eName, eArr)
    elif eKind.startswith("u64"):
        fullName = "?{}@@3{}_KA".format(eName, eArr)
    else:
        fullName = "{}".format(eName)
    return fullName

def symbolStartFromLowCase(iName):
    oName = iName[0].lower()
    for i in range(1,len(iName)-1):
        if not (iName[i].isupper() and iName[i+1].isupper()):
            break
        oName += iName[i].lower()
    oName += iName[i:]
    return oName

def getVICodeProcName(viCodeItem):
    if not isinstance(viCodeItem, ENUM_TAGS):
        return "Unkn{:02d}Proc".format(int(viCodeItem))
    iName = viCodeItem.name
    if viCodeItem in (VICodePtrs_LV5.ResetProc,\
      VICodePtrs_LV6.ResetProc,VICodePtrs_LV7.ResetProc,\
      VICodePtrs_LV8.ResetProc,VICodePtrs_LV12.ResetProc,\
      VICodePtrs_LV13.ResetProc,):
        fullName = str(len(iName)+1)+"_"+iName
        fullName = "__ZL"+fullName+"P8DSHeaderP8QElement"
    elif viCodeItem in (VICodePtrs_LV5.InitProc,\
      VICodePtrs_LV6.InitProc,VICodePtrs_LV7.InitProc,\
      VICodePtrs_LV8.InitProc,VICodePtrs_LV12.InitProc,\
      VICodePtrs_LV13.InitProc,):
        fullName = str(len(iName)+1)+"_"+iName
        fullName = "__ZL"+fullName+"P8DSHeader"
    elif viCodeItem in (VICodePtrs_LV5.ErrorStopProc,\
      VICodePtrs_LV6.ErrorStopProc,VICodePtrs_LV7.ErrorStopProc,\
      VICodePtrs_LV8.ErrorStopProc,VICodePtrs_LV12.ErrorStopProc,\
      VICodePtrs_LV13.ErrorStopProc,):
        fullName = str(len(iName)+1)+"_"+iName
        fullName = "__ZL"+fullName+"P8DSHeaderllP17VirtualInstrument"
    elif viCodeItem in (VICodePtrs_LV5.DCOCopyToOpProc,\
      VICodePtrs_LV6.DCOCopyToOpProc,VICodePtrs_LV7.DCOCopyToOpProc,\
      VICodePtrs_LV8.DCOCopyToOpProc,VICodePtrs_LV12.DCOCopyToOpProc,\
      VICodePtrs_LV13.DCOCopyToOpProc,):
        fullName = str(len(iName)+1)+"_"+iName
        fullName = "__ZL"+fullName+"P8DSHeaderlPvlb"
    elif viCodeItem in (VICodePtrs_LV5.DCOCopyFrOpProc,\
      VICodePtrs_LV6.DCOCopyFrOpProc,VICodePtrs_LV7.DCOCopyFrOpProc,\
      VICodePtrs_LV8.DCOCopyFrOpProc,VICodePtrs_LV12.DCOCopyFrOpProc,\
      VICodePtrs_LV13.DCOCopyFrOpProc,):
        fullName = str(len(iName)+1)+"_"+iName
        fullName = "__ZL"+fullName+"P8DSHeaderlll"
    elif viCodeItem in (VICodePtrs_LV5.InitCodePtrsProc,\
      VICodePtrs_LV6.InitCodePtrsProc,VICodePtrs_LV7.InitCodePtrsProc,\
      VICodePtrs_LV8.InitCodePtrsProc,VICodePtrs_LV12.InitCodePtrsProc,\
      VICodePtrs_LV13.InitCodePtrsProc,):
        fullName = str(len(iName)+1)+"_"+iName
        fullName = "_Z"+fullName+"PP13VICodePtrsRec"
    elif viCodeItem in (\
      VICodePtrs_LV6.RunProc,VICodePtrs_LV7.RunProc,\
      VICodePtrs_LV8.RunProc,VICodePtrs_LV12.RunCodeProc,\
      VICodePtrs_LV13.RunProc,VICodePtrs_LV13.RunProc2,
      VICodePtrs_LV13.RunProc3,VICodePtrs_LV13.RunProc4,
      VICodePtrs_LV13.RunProc5,VICodePtrs_LV13.RunProc6,
      VICodePtrs_LV13.RunProc7,VICodePtrs_LV13.RunProc8,
      VICodePtrs_LV13.RunProc9,VICodePtrs_LV13.RunProc10,
      VICodePtrs_LV13.RunProc11,VICodePtrs_LV13.RunProc12,
      VICodePtrs_LV13.RunProc13,VICodePtrs_LV13.RunProc14,
      VICodePtrs_LV13.RunProc15,):
        fullName = str(len(iName)+1)+"_"+iName
        fullName = "_ZL"+fullName+"P8DSHeaderP8QElementl"
    else:
        fullName = "_"+iName
    return fullName

def getVICodePtrs(ver):
    from LVmisc import isGreaterOrEqVersion
    if isGreaterOrEqVersion(ver, 13,0,0,0):
        return VICodePtrs_LV13
    elif isGreaterOrEqVersion(ver, 12,0,0,0):
        return VICodePtrs_LV12
    elif isGreaterOrEqVersion(ver, 8,0,0,0):
        return VICodePtrs_LV8
    elif isGreaterOrEqVersion(ver, 6,1,0,0):
        return VICodePtrs_LV7
    elif isGreaterOrEqVersion(ver, 6,0,0,0):
        return VICodePtrs_LV6
    elif isGreaterOrEqVersion(ver, 5,0,0,0):
        return VICodePtrs_LV5
    return None

def getProcPtrShiftVICode(procPtrShift,addrLen,ver):
    procPos = procPtrShift // addrLen
    VICodePtrs = getVICodePtrs(ver)
    if VICodePtrs is None:
        return procPos
    if not VICodePtrs.has_value(procPos):
        return procPos
    viCodeItem = VICodePtrs(procPos)
    return viCodeItem
