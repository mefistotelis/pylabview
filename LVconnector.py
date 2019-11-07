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
from types import SimpleNamespace
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
    Unknown = -1
    EnumValue =	-2


class CONNECTOR_CLUSTER_FORMAT(enum.IntEnum):
    TimeStamp =		6
    Digitaldata =	7
    Dynamicdata =	9


class CONNECTOR_REF_TYPE(enum.IntEnum):
    DataLogFile =	0x01
    Occurrence =	0x04
    TCPConnection =	0x05
    ControlRefnum =	0x08
    DataSocket =	0x0D
    UDPConnection =	0x10
    NotifierRefnum =	0x11
    Queue =				0x12
    IrDAConnection =	0x13
    Channel =			0x14
    SharedVariable =	0x15
    EventRegistration =	0x17
    UserEvent =			0x19
    Class =				0x1E
    BluetoothConnectn =	0x1F
    DataValueRef =	0x20
    FIFORefnum =	0x21


class ConnectorObject:

    def __init__(self, vi, bldata, idx, pos, obj_len, obj_flags, obj_type, po):
        """ Creates new Connector object, capable of handling generic Connector data.
        """
        self.vi = vi
        self.po = po
        self.index = idx
        self.pos = pos
        self.size = obj_len
        self.oflags = obj_flags
        self.otype = obj_type
        self.raw_data = bldata.read(obj_len)
        self.clients = []

    def parseData(self, bldata):
        if (self.po.verbose > 2):
            print("{:s}: Connector {:d} type 0x{:02x} data format isn't known; leaving raw only".format(self.po.input.name,self.index,self.otype))
        pass

    def needParseData(self):
        """ Returns if the connector did not had its data parsed yet

            After a call to parseData(), or after filling the data manually, this should
            return True. Otherwise, False.
        """
        return False

    def getData(self):
        bldata = BytesIO(self.raw_data)
        return bldata

    def checkSanity(self):
        ret = True
        return ret

    def mainType(self):
        if self.otype == 0x00:
            # Special case; if lower bits are non-zero, it is treated as int
            # But if the whole value is 0, then its just void
            return CONNECTOR_MAIN_TYPE.Void
        elif self.otype < 0:
            # Types internal to this parser - mapped without bitshift
            return CONNECTOR_MAIN_TYPE(self.otype)
        else:
            return CONNECTOR_MAIN_TYPE(self.otype >> 4)

    def fullType(self):
        if self.otype not in set(item.value for item in CONNECTOR_FULL_TYPE):
            return self.otype
        return CONNECTOR_FULL_TYPE(self.otype)

    def isNumber(self):
        return ( \
          (self.mainType() == CONNECTOR_MAIN_TYPE.Number) or \
          (self.mainType() == CONNECTOR_MAIN_TYPE.Unit) or \
          (self.fullType() == CONNECTOR_FULL_TYPE.ClusterNumFixPoint));

    def isString(self):
        return ( \
          (self.fullType() == CONNECTOR_FULL_TYPE.String));
        # looks like these are not counted as strings?
        #  (self.fullType() == CONNECTOR_FULL_TYPE.CString) or \
        #  (self.fullType() == CONNECTOR_FULL_TYPE.PascalString));

    def isPath(self):
        return ( \
          (self.fullType() == CONNECTOR_FULL_TYPE.Path));

    def hasClients(self):
        return (len(self.clients) > 0)

    def clientsEnumerate(self):
        VCTP = self.vi.get('VCTP')
        if VCTP is None:
            raise LookupError("Block {} not found in RSRC file.".format('VCTP'))
        out_enum = []
        for i, client in enumerate(self.clients):
            conn_obj = VCTP.content[client.index]
            out_enum.append( (i, client.index, conn_obj, client.flags, ) )
        return out_enum

    def getClientConnectorsByType(self):
        self.getData() # Make sure the block is parsed
        out_lists = { 'number': [], 'path': [], 'string': [], 'compound': [], 'other': [] }
        for cli_idx, conn_idx, conn_obj, conn_flags in self.clientsEnumerate():
            # We will need a list of clients, so ma might as well parse the connector now
            conn_obj.getData()
            if not conn_obj.checkSanity():
                if (self.po.verbose > 0):
                    eprint("{:s}: Warning: Connector {:d} type 0x{:02x} sanity check failed!".format(self.po.input.name,conn_obj.index,conn_obj.otype))
            # Add connectors of this Terminal to list
            if conn_obj.isNumber():
                out_lists['number'].append(conn_obj)
            elif conn_obj.isPath():
                out_lists['path'].append(conn_obj)
            elif conn_obj.isString():
                out_lists['string'].append(conn_obj)
            elif conn_obj.hasClients():
                out_lists['compound'].append(conn_obj)
            else:
                out_lists['other'].append(conn_obj)
            if (self.po.verbose > 2):
                keys = list(out_lists)
                print("enumerating: {}.{} idx={} flags={:09x} type={} connectors: {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d}"\
                      .format(self.index, cli_idx, conn_idx,  conn_flags, conn_obj.fullType().name if isinstance(conn_obj.fullType(), enum.IntEnum) else conn_obj.fullType(),\
                      keys[0],len(out_lists[keys[0]]),\
                      keys[1],len(out_lists[keys[1]]),\
                      keys[2],len(out_lists[keys[2]]),\
                      keys[3],len(out_lists[keys[3]]),\
                      keys[4],len(out_lists[keys[4]]),\
                      ))
            # Add sub-connectors the terminals within this connector
            if conn_obj.hasClients():
                sub_lists = conn_obj.getClientConnectorsByType()
                for k in out_lists:
                    out_lists[k].extend(sub_lists[k])
        return out_lists


class ConnectorObjectNumber(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.prop1 = None

    def parseData(self, bldata):
        bldata.read(4)
        self.prop1 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        pass

    def needParseData(self):
        return (self.prop1 is None)

    def getData(self, *args):
        bldata = ConnectorObject.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def checkSanity(self):
        ret = True
        if (self.prop1 != 0):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} property1 {:d}, expected {:d}".format(self.po.input.name,self.index,self.otype,self.prop1,0))
            ret = False
        expsize = 4+1 # We do not parse the whole chunk; complete size is larger
        if len(self.raw_data) < expsize:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} data size {:d}, expected {:d}".format(self.po.input.name,self.index,self.otype,len(self.raw_data),expsize))
            ret = False
        return ret


class ConnectorObjectNumberPtr(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)

    def parseData(self, bldata):
        bldata.read(4)
        # No more known data inside
        pass

    def needParseData(self):
        return True

    def getData(self, *args):
        bldata = ConnectorObject.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def checkSanity(self):
        ret = True
        expsize = 4 # We do not parse the whole chunk; complete size is larger
        if len(self.raw_data) < expsize:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} data size {:d}, expected {:d}".format(self.po.input.name,self.index,self.otype,len(self.raw_data),expsize))
            ret = False
        return ret


class ConnectorObjectBlob(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.prop1 = None

    def parseData(self, bldata):
        bldata.read(4)
        self.prop1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        # No more known data inside
        pass

    def needParseData(self):
        return (self.prop1 is None)

    def getData(self, *args):
        bldata = ConnectorObject.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def checkSanity(self):
        ret = True
        if self.prop1 != 0xFFFFFFFF:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} property1 0x{:x}, expected 0x{:x}".format(self.po.input.name,self.index,self.otype,self.prop1,0xFFFFFFFF))
            ret = False
        expsize = 4 # We do not parse the whole chunk; complete size is larger
        if len(self.raw_data) < expsize:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} data size {:d}, expected {:d}".format(self.po.input.name,self.index,self.otype,len(self.raw_data),expsize))
            ret = False
        return ret


class ConnectorObjectTerminal(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)

    def parseData(self, bldata):
        vers = self.vi.get('vers')
        # Skip length, flags and type - these were set in constructor
        bldata.read(4)
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        self.clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            self.clients[i].index = cli_idx
        self.flags = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.pattern = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        if vers.verMajor() >= 8:
            self.padding1 = int.from_bytes(bldata.read(2), byteorder='big', signed=False) # don't know/padding
            for i in range(count):
                cli_flags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.clients[i].flags = cli_flags
        else: # vers.verMajor() < 8
            for i in range(count):
                cli_flags = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
                self.clients[i].flags = cli_flags
        pass

    def needParseData(self):
        return (len(self.clients) == 0)

    def getData(self, *args):
        bldata = ConnectorObject.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def checkSanity(self):
        ret = True
        vers = self.vi.get('vers')
        if (len(self.clients) > 125):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} property1 0x{:x}, expected 0x{:x}".format(self.po.input.name,self.index,self.otype,self.prop1,0xFFFFFFFF))
            ret = False
        if vers.verMajor() >= 8:
            expsize = 4 + 2 + 2 * len(self.clients) + 4 + 2 + 4 * len(self.clients)
        else:
            expsize = 4 + 2 + 2 * len(self.clients) + 4 + 2 * len(self.clients)
        if len(self.raw_data) != expsize:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Connector {:d} type 0x{:02x} data size {:d}, expected {:d}".format(self.po.input.name,self.index,self.otype,len(self.raw_data),expsize))
            ret = False
        return ret


class ConnectorObjectTypeDef(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.flag1 = None
        self.labels = []

    def parseData(self, bldata):
        VCTP = self.vi.get('VCTP')
        # Skip length, flags and type - these were set in constructor
        bldata.read(4)
        self.flag1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.labels = [b"" for _ in range(count)]
        for i in range(count):
            label_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.labels[i] = bldata.read(label_len)
        # The underlying object is stored here directly, not as index in VCTP list
        # Let's add it to that list anyway, as keeping one flat list is simpler
        pos = bldata.tell()
        self.clients = [ SimpleNamespace() ]
        # In "Vi Explorer" code, the length value of this object is treated differently
        # (decreased by 4); not sure if this is correct and an issue here
        cli_idx, cli_len = VCTP.parseConnector(bldata, pos)
        cli_flags = 0
        self.clients[0].index = cli_idx
        self.clients[0].flags = cli_flags
        pass

    def needParseData(self):
        return (self.flag1 is None)

    def getData(self, *args):
        bldata = ConnectorObject.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata


class ConnectorObjectArray(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)

    def parseData(self, bldata):
        # Skip length, flags and type - these were set in constructor
        bldata.read(4)
        ndimensions = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.dimensions = [SimpleNamespace() for _ in range(ndimensions)]
        for i in range(ndimensions):
            flags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            if flags != 0xFFFFFFFF:
                if ((flags & 0x80000000) != 0):
                    # Array with fixed size
                    self.dimensions[i].flags = flags >> 24
                    self.dimensions[i].fixedSize = flags & 0x00FFFFFF
                else:
                    raise ValueError("Unexpected flags field in connector {:d}; fixed size flag not set in 0x{:08x}.".format(self.index,flags))
            else:
                # TODO No idea what to do here... it does happen
                self.dimensions[i].flags = flags >> 24
                self.dimensions[i].fixedSize = flags & 0x00FFFFFF
        self.clients = [ SimpleNamespace() ]
        cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        cli_flags = 0
        self.clients[0].index = cli_idx
        self.clients[0].flags = cli_flags

    def needParseData(self):
        return (len(self.clients) == 0)

    def getData(self, *args):
        bldata = ConnectorObject.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def checkSanity(self):
        ret = True
        if len(self.dimensions) > 64:
            ret = False
        if len(self.clients) != 1:
            ret = False
        if (self.dimensions[0].flags & 0x80) == 0:
            ret = False
        for client in self.clients:
            if client.index >= self.index:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: Connector {:d} type 0x{:02x} client {:d} is reference to higher index".format(self.po.input.name,self.index,self.otype,client.index))
                ret = False
        return ret


class ConnectorObjectUnit(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.values = []
        self.prop1 = None

    def parseData(self, bldata):
        # Skip length, flags and type - these were set in constructor
        bldata.read(4)
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False) # unit/item count

        isTextEnum = False
        if self.fullType() in [ CONNECTOR_FULL_TYPE.UnitU8, CONNECTOR_FULL_TYPE.UnitU16, CONNECTOR_FULL_TYPE.UnitU32 ]:
            isTextEnum = True

        # Create _separate_ empty namespace for each connector
        self.values = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            if isTextEnum:
                label_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
                self.values[i].label = bldata.read(label_len)
                self.values[i].intval = None
                self.values[i].size = label_len + 1
            else:
                label_val = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.values[i].label = "0x{:X}".format(label_val)
                self.values[i].intval = label_val
                self.values[i].size = 4
            self.values[i].otype = CONNECTOR_FULL_TYPE.EnumValue
            self.values[i].index = i
        if (bldata.tell() % 2) != 0:
            self.padding1 = bldata.read(1)
        else:
            self.padding1 = None
        self.prop1 = int.from_bytes(bldata.read(1), byteorder='big', signed=False) # Unknown
        pass

    def needParseData(self):
        return (self.prop1 is None)

    def getData(self, *args):
        bldata = ConnectorObject.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def checkSanity(self):
        ret = True
        if (self.padding1 is not None) and (self.padding1 != b'\0'):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Unit {:d} type 0x{:02x} padding1 {}, expected zeros".format(self.po.input.name,self.index,self.otype,self.padding1))
            ret = False
        if self.prop1 != 0:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: Unit {:d} type 0x{:02x} prop1 {:d}, expected {:d}".format(self.po.input.name,self.index,self.otype,self.prop1,0))
            ret = False
        if len(self.values) < 1:
            ret = False
        return ret


class ConnectorObjectRef(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.reftype = None

    def parseData(self, bldata):
        # Skip length, flags and type - these were set in constructor
        bldata.read(4)
        self.reftype = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        parseRefType = {
            CONNECTOR_REF_TYPE.DataLogFile: ConnectorObjectRef.parseRefQueue,
            CONNECTOR_REF_TYPE.Occurrence: None,
            CONNECTOR_REF_TYPE.TCPConnection: None,
            CONNECTOR_REF_TYPE.ControlRefnum: ConnectorObjectRef.parseRefControl,
            CONNECTOR_REF_TYPE.DataSocket: None,
            CONNECTOR_REF_TYPE.UDPConnection: None,
            CONNECTOR_REF_TYPE.NotifierRefnum: ConnectorObjectRef.parse_0Pre0Post,
            CONNECTOR_REF_TYPE.Queue: ConnectorObjectRef.parseRefQueue,
            CONNECTOR_REF_TYPE.IrDAConnection: None,
            CONNECTOR_REF_TYPE.Channel: None,
            CONNECTOR_REF_TYPE.SharedVariable: None,
            CONNECTOR_REF_TYPE.EventRegistration: ConnectorObjectRef.parseRefEventRegist,
            CONNECTOR_REF_TYPE.UserEvent: ConnectorObjectRef.parseRefQueue,
            CONNECTOR_REF_TYPE.Class: None,
            CONNECTOR_REF_TYPE.BluetoothConnectn: None,
            CONNECTOR_REF_TYPE.DataValueRef: ConnectorObjectRef.parseRefDataValue,
            CONNECTOR_REF_TYPE.FIFORefnum: ConnectorObjectRef.parse_0Pre0Post,
        }.get(self.refType(), None)
        if parseRefType is not None:
            parseRefType(self, bldata)
        pass

    def parseRefQueue(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        self.clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            self.clients[i].index = cli_idx
            self.clients[i].flags = cli_flags
        pass

    def parseRefControl(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        self.clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            self.clients[i].index = cli_idx
            self.clients[i].flags = cli_flags
        self.ctlflags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        pass

    def parse_0Pre0Post(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        self.clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            self.clients[i].index = cli_idx
            self.clients[i].flags = cli_flags
        pass

    def parseRefEventRegist(self, bldata):
        self.tmp1 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        self.clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            # dont know this data!
            tmp3 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            tmp4 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            tmp5 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            self.clients[i].index = cli_idx
            self.clients[i].flags = cli_flags
            self.clients[i].tmp3 = tmp3
            self.clients[i].tmp4 = tmp4
            self.clients[i].tmp5 = tmp5
        pass

    def parseRefDataValue(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        self.clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            # dont know this data!
            cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            cli_flags = 0
            self.clients[i].index = cli_idx
            self.clients[i].flags = cli_flags
        self.valflags = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        pass

    def needParseData(self):
        return (self.reftype is None)

    def getData(self, *args):
        bldata = ConnectorObject.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def checkSanity(self):
        ret = True
        if self.refType() in [ CONNECTOR_REF_TYPE.DataLogFile, \
           CONNECTOR_REF_TYPE.Queue, CONNECTOR_REF_TYPE.UserEvent,
           CONNECTOR_REF_TYPE.ControlRefnum, CONNECTOR_REF_TYPE.NotifierRefnum,
           CONNECTOR_REF_TYPE.DataValueRef, ]:
            if len(self.clients) > 1:
                ret = False
        elif self.refType() in [ CONNECTOR_REF_TYPE.EventRegistration ]:
            if self.tmp1 != 0:
                ret = False
            if len(self.clients) < 1:
                ret = False
            pass

        for client in self.clients:
            if client.index >= self.index:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: Connector {:d} type 0x{:02x} client {:d} is reference to higher index".format(self.po.input.name,self.index,self.otype,client.index))
                ret = False
        return ret

    def refType(self):
        if self.reftype not in set(item.value for item in CONNECTOR_REF_TYPE):
            return self.reftype
        return CONNECTOR_REF_TYPE(self.reftype)


class ConnectorObjectCluster(ConnectorObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.clusterFmt = None

    def parseData(self, bldata):
        # Skip length, flags and type - these were set in constructor
        bldata.read(4)

        if self.fullType() == CONNECTOR_FULL_TYPE.Cluster:
            count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            # Create _separate_ empty namespace for each connector
            self.clients = [SimpleNamespace() for _ in range(count)]
            for i in range(count):
                cli_idx = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
                cli_flags = 0
                self.clients[i].index = cli_idx
                self.clients[i].flags = cli_flags

        elif self.fullType() == CONNECTOR_FULL_TYPE.ClusterData:
            self.clusterFmt = int.from_bytes(bldata.read(2), byteorder='big', signed=False)

        else:
            if (self.po.verbose > 2):
                print("{:s}: Connector {:d} cluster type 0x{:02x} data format isn't known; leaving raw only".format(self.po.input.name,self.index,self.otype))
        pass

    def needParseData(self):
        if self.fullType() == CONNECTOR_FULL_TYPE.Cluster:
            return (len(self.clients) == 0)
        elif self.fullType() == CONNECTOR_FULL_TYPE.ClusterData:
            return (self.clusterFmt is None)
        return True

    def getData(self, *args):
        bldata = ConnectorObject.getData(self, *args)
        if self.needParseData():
            self.parseData(bldata)
            bldata.seek(0)
        return bldata

    def checkSanity(self):
        ret = True
        if self.fullType() == CONNECTOR_FULL_TYPE.Cluster:
            if len(self.clients) > 500:
                ret = False
        elif self.fullType() == CONNECTOR_FULL_TYPE.ClusterData:
            if self.clusterFmt > 127: # Not sure how many cluster formats are there
                ret = False
        return ret

    def clusterFormat(self):
        if self.clusterFmt not in set(item.value for item in CONNECTOR_CLUSTER_FORMAT):
            return self.clusterFmt
        return CONNECTOR_CLUSTER_FORMAT(self.clusterFmt)


def newConnectorObjectMainNumberOrVoid(vi, bldata, idx, pos, obj_len, obj_flags, obj_type, po):
    """ Creates and returns new terminal object of main type 'Terminal'
    """
    ctor = {
        CONNECTOR_FULL_TYPE.Void: ConnectorObject,
    }.get(obj_type, ConnectorObjectNumber) # Number is the default type in case of no match
    return ctor(vi, bldata, idx, pos, obj_len, obj_flags, obj_type, po)


def newConnectorObjectMainTerminal(vi, bldata, idx, pos, obj_len, obj_flags, obj_type, po):
    """ Creates and returns new terminal object of main type 'Terminal'
    """
    ctor = {
        CONNECTOR_FULL_TYPE.Terminal: ConnectorObjectTerminal,
        CONNECTOR_FULL_TYPE.TypeDef: ConnectorObjectTypeDef,
    }.get(obj_type, ConnectorObject) # Void is the default type in case of no match
    return ctor(vi, bldata, idx, pos, obj_len, obj_flags, obj_type, po)


def newConnectorObject(vi, bldata, idx, pos, obj_len, obj_flags, obj_type, po):
    """ Creates and returns new terminal object with given parameters
    """
    obj_main_type = obj_type >> 4
    ctor = {
        CONNECTOR_MAIN_TYPE.Number: newConnectorObjectMainNumberOrVoid,
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
    return ctor(vi, bldata, idx, pos, obj_len, obj_flags, obj_type, po)

