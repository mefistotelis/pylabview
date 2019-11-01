# -*- coding: utf-8 -*-

""" LabView RSRC file format - Connector objects inside VCTP block.


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
from ctypes import *

from LVmisc import *
from LVblock import *


class CONNECTOR_MAIN_TYPE(enum.IntEnum):
    Number = 0x0	# INT/DBL/complex/...
    Unit = 0x1		# INT+Format: Enum/Units
    Bool = 0x2		# only Boolean
    Blob = 0x3		# String/Path/...
    Array = 0x4		# Array
    Cluster = 0x5	# Struct (hard code [Timestamp] or flexibl)
    Unknown6 = 0x6	# ???
    Ref = 0x7		# Pointers
    NumberPointer = 0x8	# INT+Format: Enum/Units Pointer
    Terminal = 0xF	# like Cluser+Flags/Typdef
    # Custom / internal to this parser / not official
    Void = 0x100	# 0 is used for numbers
    Unknown = -1
    EnumValue = -2		# Entry for Enum


class CONNECTOR_FULL_TYPE(enum.IntEnum):
    Void =		0x00

    NumberI8 =	0x01
    NumberI16 =	0x02
    NumberI32 =	0x03
    NumberI64 =	0x04
    NumberU8 =	0x05
    NumberU16 =	0x06
    NumberU32 =	0x07
    NumberU64 =	0x08
    NumberSGL =	0x09
    NumberDBL =	0x0A
    NumberXTP =	0x0B
    NumberCSG =	0x0C
    NumberCDB =	0x0D
    NumberCXT =	0x0E

    UnitI8 =	0x11
    UnitI16 =	0x12
    UnitI32 =	0x13
    UnitI64 =	0x14
    UnitU8 =	0x15
    UnitU16 =	0x16
    UnitU32 =	0x17
    UnitU64 =	0x18
    UnitSGL =	0x19
    UnitDBL =	0x1A
    UnitXTP =	0x1B
    UnitCSG =	0x1C
    UnitCDB =	0x1D
    UnitCXT =	0x1E

    Bool =		0x21

    String =		0x30
    Path =			0x32
    Picture =		0x33
    CString =		0x34
    PascalString =	0x35
    DAQChannel =	0x37

    Array =				0x40

    Cluster =			0x50
    ClusterVariant =	0x53
    ClusterData =		0x54
    ClusterNumFixPoint = 0x5F

    Ref =				0x70

    PointerNumberXX =	0x80
    PointerNumberI8 =	0x81
    PointerNumberI16 =	0x82
    PointerNumberI32 =	0x83
    PointerNumberI64 =	0x84
    PointerNumberU8 =	0x85
    PointerNumberU16 =	0x86
    PointerNumberU32 =	0x87
    PointerNumberU64 =	0x88
    PointerNumberSGL =	0x89
    PointerNumberDBL =	0x8A
    PointerNumberXTP =	0x8B
    PointerNumberCSG =	0x8C
    PointerNumberCDB =	0x8D
    PointerNumberCXT =	0x8E

    Terminal =	0xF0
    TypeDef =	0xF1

    # Not official
    EnumValue =	-2


class ConnectorObject:

    def __init__(self, po, bldata, pos, obj_len, obj_flags, obj_type):
        self.po = po
        self.pos = pos
        self.size = obj_len
        self.oflags = obj_flags
        self.otype = obj_type
        self.raw_data = bldata.read(obj_len - 4)

    def check_sanity(self):
        ret = True
        return ret


class ConnectorObjectNumber(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
    # TODO

class ConnectorObjectNumberPtr(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
    # TODO


class ConnectorObjectBlob(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
    # TODO


class ConnectorObjectTerminal(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
    # TODO


class ConnectorObjectTypeDef(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
    # TODO


class ConnectorObjectArray(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
    # TODO


class ConnectorObjectUnit(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
    # TODO


class ConnectorObjectRef(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
    # TODO


class ConnectorObjectCluster(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
    # TODO


def newConnectorObjectMainTerminal(po, bldata, pos, obj_len, obj_flags, obj_type):
    """ Creates and returns new terminal object of main type 'Terminal'
    """
    ctor = {
        CONNECTOR_FULL_TYPE.Terminal: ConnectorObjectTerminal,
        CONNECTOR_FULL_TYPE.TypeDef: ConnectorObjectTypeDef,
    }.get(obj_type, ConnectorObject) # Void is the default type in case of no match
    return ctor(po, bldata, pos, obj_len, obj_flags, obj_type)


def newConnectorObject(po, bldata, pos, obj_len, obj_flags, obj_type):
    """ Creates and returns new terminal object with given parameters
    """
    obj_main_type = obj_type >> 4
    ctor = {
        CONNECTOR_MAIN_TYPE.Number: ConnectorObjectNumber,
        CONNECTOR_MAIN_TYPE.Unit: ConnectorObjectUnit,
        CONNECTOR_MAIN_TYPE.Bool: ConnectorObject, # No properties - basic type is enough
        CONNECTOR_MAIN_TYPE.Blob: ConnectorObjectBlob,
        CONNECTOR_MAIN_TYPE.Array: ConnectorObjectArray,
        CONNECTOR_MAIN_TYPE.Cluster: ConnectorObjectCluster,
        CONNECTOR_MAIN_TYPE.Unknown6: ConnectorObject,
        CONNECTOR_MAIN_TYPE.Ref: ConnectorObjectRef,
        CONNECTOR_MAIN_TYPE.NumberPointer: ConnectorObjectNumberPtr,
        CONNECTOR_MAIN_TYPE.Terminal: newConnectorObjectMainTerminal,
        CONNECTOR_MAIN_TYPE.Void: ConnectorObject, # No properties - basic type is enough
    }.get(obj_main_type, ConnectorObject) # Void is the default type in case of no match
    return ctor(po, bldata, pos, obj_len, obj_flags, obj_type)

